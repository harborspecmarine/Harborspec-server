"""
HarborSPEC™ Order Server
Polls Gmail via IMAP every 5 minutes for Formspree order emails.
Generates invoice PDF and emails it to orders inbox automatically.
No OAuth required — uses Gmail App Password only.
"""

from flask import Flask, request, jsonify
from invoice import generate_invoice
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import json
import os
import re
import threading
import time
from datetime import datetime

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/order', methods=['OPTIONS'])
def order_preflight():
    return '', 204

ORDERS_EMAIL = os.environ.get('ORDERS_EMAIL', 'harborspecmarineorders@gmail.com')
SMTP_USER    = os.environ.get('SMTP_USER',    '')
SMTP_PASS    = os.environ.get('SMTP_PASS',    '')
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN', '')

COUNTER_FILE = '/tmp/hs_counter.txt'

def next_invoice_number():
    try:
        n = int(open(COUNTER_FILE).read().strip()) + 1
    except:
        n = 1
    open(COUNTER_FILE, 'w').write(str(n))
    return f'HS-{n:04d}'


def parse_order_from_body(body):
    """Parse a Formspree notification email body into an order dict."""
    data = {}
    for line in body.split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, val = line.partition(':')
            data[key.strip().lower().replace(' ', '_')] = val.strip()

    order = {
        'name':    data.get('name', ''),
        'email':   data.get('email', data.get('_replyto', '')),
        'phone':   data.get('phone', ''),
        'vessel':  data.get('vessel', ''),
        'address': data.get('address', ''),
        'city':    data.get('city', ''),
        'state':   data.get('state', ''),
        'zip':     data.get('zip', ''),
        'county':  data.get('county', ''),
        'notes':   data.get('notes', ''),
        'items':   [],
    }

    # Parse line items from ITEMS block in order_summary
    if 'ITEMS' in body:
        block = body[body.find('ITEMS') + 5:]
        if 'CUSTOMER' in block:
            block = block[:block.find('CUSTOMER')]
        for line in block.split('\n'):
            line = line.strip().lstrip('•').strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                continue
            # Name + qty: "Pilot Card x1"
            nq = parts[0]
            qm = re.search(r'x(\d+)$', nq)
            qty = int(qm.group(1)) if qm else 1
            name = re.sub(r'\s*x\d+$', '', nq).strip()
            # Color
            cr = parts[1]
            color_extra = '+$5' in cr
            color = cr.replace('(+$5)', '').replace('+$5', '').strip()
            mounting  = parts[2] if len(parts) > 2 else ''
            text_type = parts[3] if len(parts) > 3 else 'standard'
            # Price
            pm = re.search(r'\$([\d.]+)', parts[-1]) if len(parts) > 4 else None
            line_total = float(pm.group(1)) if pm else 0
            unit_full  = (line_total / qty) if qty else 0
            base_price = unit_full - (5 if color_extra else 0)

            order['items'].append({
                'name': name, 'price': base_price, 'qty': qty,
                'color': color, 'colorExtra': color_extra,
                'mounting': mounting, 'textType': text_type,
            })

    # Fallback if parsing failed
    if not order['items']:
        order['items'] = [{
            'name': 'See order — vessel info sheet required',
            'price': 0, 'qty': 1, 'color': 'TBD',
            'colorExtra': False, 'mounting': 'TBD', 'textType': 'standard',
        }]

    return order


def get_email_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                return part.get_payload(decode=True).decode('utf-8', errors='ignore')
    return msg.get_payload(decode=True).decode('utf-8', errors='ignore')


def attach_pdf(msg, pdf_path, invoice_num):
    """Attach invoice PDF to a MIMEMultipart message."""
    try:
        with open(pdf_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="invoice_{invoice_num}.pdf"')
            msg.attach(part)
    except Exception as e:
        print(f"  PDF attach error: {e}")


def send_invoice_email(order, pdf_path, invoice_num):
    """Send invoice PDF to orders inbox AND customer."""

    items_lines = '\n'.join(
        f"  • {i['name']} x{i['qty']} | {i['color']}{'(+$5)' if i.get('colorExtra') else ''} | {i['mounting']}"
        for i in order.get('items', [])
    )

    # ── EMAIL TO YOU (internal copy) ──────────────────────────────
    owner_msg = MIMEMultipart()
    owner_msg['From']    = SMTP_USER
    owner_msg['To']      = ORDERS_EMAIL
    owner_msg['Subject'] = f"New Order — Invoice {invoice_num} — {order.get('name', '')}"

    owner_body = f"""New HarborSPEC order received.

Invoice:  {invoice_num}
Customer: {order.get('name','')}
Email:    {order.get('email','')}
Phone:    {order.get('phone','N/A')}
Vessel:   {order.get('vessel','N/A')}
Ship to:  {order.get('address','')} {order.get('city','')} {order.get('state','')} {order.get('zip','')}
{('County: ' + order['county']) if order.get('county') else ''}

Items:
{items_lines}

Notes: {order.get('notes','None')}

Invoice PDF attached. Customer has received their copy.
Reply to this email to contact: {order.get('email','')}
"""
    owner_msg.attach(MIMEText(owner_body, 'plain'))
    attach_pdf(owner_msg, pdf_path, invoice_num)

    # ── EMAIL TO CUSTOMER ─────────────────────────────────────────
    customer_email = order.get('email', '').strip()
    customer_msg = None
    if customer_email:
        customer_msg = MIMEMultipart()
        customer_msg['From']    = SMTP_USER
        customer_msg['To']      = customer_email
        customer_msg['Reply-To'] = ORDERS_EMAIL
        customer_msg['Subject'] = f"Your HarborSPEC Order — Invoice {invoice_num}"

        customer_body = f"""Thank you for your order, {order.get('name','').split()[0] if order.get('name') else 'Captain'}.

Your order confirmation and invoice are attached. Please review and keep for your records.

INVOICE:  {invoice_num}
VESSEL:   {order.get('vessel','N/A')}

ITEMS ORDERED:
{items_lines}

SHIP TO:
{order.get('address','')}
{order.get('city','')+', ' if order.get('city') else ''}{order.get('state','')} {order.get('zip','')}
{('County: ' + order['county']) if order.get('county') else ''}

NOTES: {order.get('notes','None')}

---
PAYMENT
We will be in touch shortly to process payment. You can also reply to this email or call us at any time to provide payment.

Payment is due within 7 days. Production begins after payment is received.
Standard lead time is 2 weeks from payment. Rush orders (+25%) available on request.

---
QUESTIONS?
Reply to this email or contact us at {ORDERS_EMAIL}

Thank you for your business.
HarborSPEC\u2122
harborspecmarine.com
"""
        customer_msg.attach(MIMEText(customer_body, 'plain'))
        attach_pdf(customer_msg, pdf_path, invoice_num)

    # ── SEND BOTH ─────────────────────────────────────────────────
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ORDERS_EMAIL, owner_msg.as_string())
            print(f"  Invoice {invoice_num} sent to {ORDERS_EMAIL}")
            if customer_msg and customer_email:
                server.sendmail(SMTP_USER, customer_email, customer_msg.as_string())
                print(f"  Invoice {invoice_num} sent to customer: {customer_email}")
        return True
    except Exception as e:
        print(f"  SMTP error: {e}")
        return False


def check_gmail():
    """Connect to Gmail via IMAP and process unread Formspree emails."""
    if not SMTP_USER or not SMTP_PASS:
        print("No credentials configured")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking Gmail...")
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(SMTP_USER, SMTP_PASS)
        mail.select('inbox')

        # Find unread emails from Formspree
        _, msgs = mail.search(None, '(UNSEEN FROM "formspree")')
        ids = msgs[0].split()

        if not ids or ids == [b'']:
            print(f"  No new orders")
            mail.logout()
            return

        print(f"  {len(ids)} new order email(s) found")

        for eid in ids:
            try:
                _, data = mail.fetch(eid, '(RFC822)')
                msg = email.message_from_bytes(data[0][1])
                body = get_email_body(msg)
                order = parse_order_from_body(body)

                invoice_num = next_invoice_number()
                order['invoice_num'] = invoice_num
                pdf_path = f'/tmp/invoice_{invoice_num}.pdf'

                generate_invoice(order, output_path=pdf_path)
                send_invoice_email(order, pdf_path, invoice_num)

                # Mark as read so we don't process it again
                mail.store(eid, '+FLAGS', '\\Seen')
                print(f"  Done: {invoice_num} — {order.get('name','?')}")

            except Exception as e:
                print(f"  Error on email {eid}: {e}")

        mail.logout()

    except Exception as e:
        print(f"  IMAP error: {e}")


def polling_loop():
    """Background thread — checks Gmail every 5 minutes."""
    time.sleep(15)  # Let gunicorn finish starting
    while True:
        try:
            check_gmail()
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(300)


# ── ROUTES ──
@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'HarborSPEC Order Server',
        'smtp': bool(SMTP_USER and SMTP_PASS),
    })

@app.route('/order', methods=['POST'])
def receive_order():
    """Receive order directly from cart.html and generate invoice immediately."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400

        # Parse items from JSON string
        items = []
        try:
            raw_items = json.loads(data.get('items', '[]'))
            for i in raw_items:
                items.append({
                    'name':       i.get('name', ''),
                    'price':      float(i.get('price', 0)),
                    'qty':        int(i.get('qty', 1)),
                    'color':      i.get('color', ''),
                    'colorExtra': i.get('colorExtra', False),
                    'mounting':   i.get('mounting', ''),
                    'textType':   i.get('textType', 'standard'),
                })
        except Exception as e:
            print(f"  Item parse error: {e}")

        if not items:
            items = [{'name':'See order details','price':0,'qty':1,'color':'TBD','colorExtra':False,'mounting':'TBD','textType':'standard'}]

        order = {
            'name':    data.get('customer_name', data.get('name', '')),
            'email':   data.get('customer_email', data.get('email', '')),
            'phone':   data.get('phone', ''),
            'company': data.get('company', ''),
            'vessel':  data.get('vessel', ''),
            'address': data.get('address', ''),
            'city':    data.get('city', ''),
            'state':   data.get('state', ''),
            'zip':     data.get('zip', ''),
            'county':  data.get('county', ''),
            'notes':   data.get('notes', ''),
            'items':   items,
        }

        invoice_num = next_invoice_number()
        order['invoice_num'] = invoice_num
        pdf_path = f'/tmp/invoice_{invoice_num}.pdf'

        generate_invoice(order, output_path=pdf_path)
        send_invoice_email(order, pdf_path, invoice_num)

        print(f"  Direct order processed: {invoice_num} — {order.get('name','?')}")
        return jsonify({'status': 'ok', 'invoice': invoice_num}), 200

    except Exception as e:
        print(f"  Order error: {e}")
        return jsonify({'error': str(e)}), 500



def check_now():
    """Manually trigger a check — test with /check-now?token=harbor2025"""
    if WEBHOOK_TOKEN and request.args.get('token') != WEBHOOK_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    check_gmail()
    return jsonify({'status': 'checked'})


# Start polling thread (works with both direct run and gunicorn)
_thread = threading.Thread(target=polling_loop, daemon=True)
_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
