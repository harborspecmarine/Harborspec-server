"""
HarborSPEC™ Order Server
Receives orders directly from cart.html via POST.
Also polls Gmail via IMAP every 5 minutes as fallback.
Sends invoices via SendGrid API (HTTPS — no SMTP port issues).
"""

from flask import Flask, request, jsonify
from invoice import generate_invoice
import json
import os
import re
import threading
import time
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import urllib.request
import urllib.parse

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

# ── CONFIG ──
ORDERS_EMAIL     = os.environ.get('ORDERS_EMAIL',     'harborspecmarineorders@gmail.com')
SMTP_USER        = os.environ.get('SMTP_USER',        '')
SMTP_PASS        = os.environ.get('SMTP_PASS',        '')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
WEBHOOK_TOKEN    = os.environ.get('WEBHOOK_TOKEN',    '')
COUNTER_FILE     = '/tmp/hs_counter.txt'

def next_invoice_number():
    try:
        n = int(open(COUNTER_FILE).read().strip()) + 1
    except:
        n = 1
    open(COUNTER_FILE, 'w').write(str(n))
    return f'HS-{n:04d}'


# ── SENDGRID EMAIL ──
def send_via_sendgrid(to_email, subject, body_text, pdf_path=None, invoice_num=None):
    """Send email via SendGrid HTTPS API."""
    if not SENDGRID_API_KEY:
        print("  No SendGrid API key configured")
        return False

    import base64

    attachments = []
    if pdf_path and invoice_num:
        try:
            with open(pdf_path, 'rb') as f:
                pdf_data = base64.b64encode(f.read()).decode()
            attachments = [{
                'content': pdf_data,
                'type': 'application/pdf',
                'filename': f'invoice_{invoice_num}.pdf',
                'disposition': 'attachment'
            }]
        except Exception as e:
            print(f"  PDF attach error: {e}")

    payload = {
        'personalizations': [{'to': [{'email': to_email}]}],
        'from': {'email': ORDERS_EMAIL, 'name': 'HarborSPEC'},
        'reply_to': {'email': ORDERS_EMAIL},
        'subject': subject,
        'content': [{'type': 'text/plain', 'value': body_text}],
    }
    if attachments:
        payload['attachments'] = attachments

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=data,
        headers={
            'Authorization': f'Bearer {SENDGRID_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  SendGrid sent to {to_email}: {resp.status}")
            return True
    except Exception as e:
        print(f"  SendGrid error: {e}")
        return False


def send_invoice_email(order, pdf_path, invoice_num):
    """Send invoice to orders inbox and customer."""
    items_lines = '\n'.join(
        f"  • {i['name']} x{i['qty']} | {i['color']}{'(+$5)' if i.get('colorExtra') else ''} | {i['mounting']}"
        for i in order.get('items', [])
    )

    # Email to you
    owner_body = f"""New HarborSPEC order received.

Invoice:  {invoice_num}
Customer: {order.get('name','')}
Company:  {order.get('company','N/A')}
Email:    {order.get('email','')}
Phone:    {order.get('phone','N/A')}
Vessel:   {order.get('vessel','N/A')}
Ship to:  {order.get('address','')} {order.get('city','')} {order.get('state','')} {order.get('zip','')}
{('County: ' + order['county']) if order.get('county') else ''}

Items:
{items_lines}

Notes: {order.get('notes','None')}

Invoice PDF attached. Reply to reach customer: {order.get('email','')}
"""
    send_via_sendgrid(
        ORDERS_EMAIL,
        f"New Order — Invoice {invoice_num} — {order.get('name','')}",
        owner_body, pdf_path, invoice_num
    )

    # Email to customer
    customer_email = order.get('email', '').strip()
    if customer_email:
        first_name = order.get('name','').split()[0] if order.get('name') else 'Captain'
        customer_body = f"""Thank you for your order, {first_name}.

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
HarborSPEC™
harborspecmarine.com
"""
        send_via_sendgrid(
            customer_email,
            f"Your HarborSPEC Order — Invoice {invoice_num}",
            customer_body, pdf_path, invoice_num
        )


def process_order(order):
    """Generate invoice and send emails for an order dict."""
    invoice_num = next_invoice_number()
    order['invoice_num'] = invoice_num
    pdf_path = f'/tmp/invoice_{invoice_num}.pdf'
    generate_invoice(order, output_path=pdf_path)
    send_invoice_email(order, pdf_path, invoice_num)
    print(f"  Processed: {invoice_num} — {order.get('name','?')}")
    return invoice_num


# ── DIRECT ORDER ENDPOINT ──
@app.route('/order', methods=['POST'])
def receive_order():
    """Receive order directly from cart.html."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400

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

        invoice_num = process_order(order)
        return jsonify({'status': 'ok', 'invoice': invoice_num}), 200

    except Exception as e:
        print(f"  Order error: {e}")
        return jsonify({'error': str(e)}), 500


# ── GMAIL POLLING (fallback) ──
def parse_order_from_body(body):
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
            nq = parts[0]
            qm = re.search(r'x(\d+)$', nq)
            qty = int(qm.group(1)) if qm else 1
            name = re.sub(r'\s*x\d+$', '', nq).strip()
            cr = parts[1]
            color_extra = '+$5' in cr
            color = cr.replace('(+$5)', '').replace('+$5', '').strip()
            mounting  = parts[2] if len(parts) > 2 else ''
            text_type = parts[3] if len(parts) > 3 else 'standard'
            pm = re.search(r'\$([\d.]+)', parts[-1]) if len(parts) > 4 else None
            line_total = float(pm.group(1)) if pm else 0
            unit_full  = (line_total / qty) if qty else 0
            base_price = unit_full - (5 if color_extra else 0)
            order['items'].append({
                'name': name, 'price': base_price, 'qty': qty,
                'color': color, 'colorExtra': color_extra,
                'mounting': mounting, 'textType': text_type,
            })
    if not order['items']:
        order['items'] = [{'name':'See order','price':0,'qty':1,'color':'TBD','colorExtra':False,'mounting':'TBD','textType':'standard'}]
    return order


def check_gmail():
    if not SMTP_USER or not SMTP_PASS:
        return
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking Gmail...")
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(SMTP_USER, SMTP_PASS)
        mail.select('inbox')
        _, msgs = mail.search(None, '(UNSEEN FROM "formspree")')
        ids = msgs[0].split()
        if not ids or ids == [b'']:
            print(f"  No new orders")
            mail.logout()
            return
        for eid in ids:
            try:
                _, data = mail.fetch(eid, '(RFC822)')
                msg = email.message_from_bytes(data[0][1])
                body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                order = parse_order_from_body(body)
                process_order(order)
                mail.store(eid, '+FLAGS', '\\Seen')
            except Exception as e:
                print(f"  Error: {e}")
        mail.logout()
    except Exception as e:
        print(f"  IMAP error: {e}")


def polling_loop():
    time.sleep(15)
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
        'sendgrid': bool(SENDGRID_API_KEY),
        'smtp': bool(SMTP_USER and SMTP_PASS),
    })

@app.route('/check-now')
def check_now():
    if WEBHOOK_TOKEN and request.args.get('token') != WEBHOOK_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    check_gmail()
    return jsonify({'status': 'checked'})


_thread = threading.Thread(target=polling_loop, daemon=True)
_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
