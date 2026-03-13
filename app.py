"""
HarborSPEC™ Order Automation Server
Receives Formspree webhook → generates invoice PDF → emails to orders inbox
"""

from flask import Flask, request, jsonify
from invoice import generate_invoice
import smtplib
import os
import json
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

app = Flask(__name__)

# ── CONFIG (set as environment variables on Railway) ──
ORDERS_EMAIL  = os.environ.get('ORDERS_EMAIL',  'harborspecmarineorders@gmail.com')
SMTP_USER     = os.environ.get('SMTP_USER',     '')   # your Gmail address
SMTP_PASS     = os.environ.get('SMTP_PASS',     '')   # Gmail App Password
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN', '')   # secret token to verify requests

# ── INVOICE COUNTER ──
COUNTER_FILE = '/tmp/invoice_counter.txt'

def next_invoice_number():
    try:
        n = int(open(COUNTER_FILE).read().strip()) + 1
    except:
        n = 1
    open(COUNTER_FILE, 'w').write(str(n))
    return f'HS-{n:04d}'


# ── PARSE ORDER FROM FORMSPREE PAYLOAD ──
def parse_order(data):
    """
    Formspree posts form fields as flat key/value pairs.
    The cart posts: name, email, phone, vessel, address, city, state, zip,
                    county, notes, order_summary, order_total, item_count
    We reconstruct the items list from order_summary text.
    """
    order = {
        'name':    data.get('name', ''),
        'email':   data.get('email', ''),
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

    # Parse items from the order_summary text block
    # Format per cart.js: "Name xQTY | Color(+$5?) | Mounting | textType | $total"
    summary = data.get('order_summary', '')
    for line in summary.split('\n'):
        line = line.strip()
        if not line or line.startswith('ITEMS') or line.startswith('Subtotal') \
           or line.startswith('Shipping') or line.startswith('Tax') \
           or line.startswith('TOTAL') or line.startswith('CUSTOMER') \
           or line.startswith('Name:') or line.startswith('Email:') \
           or line.startswith('Phone:') or line.startswith('Vessel:') \
           or line.startswith('Address:') or line.startswith('County:') \
           or line.startswith('Notes:'):
            continue

        # Parse: "Pilot Card x1 | Black | 2-Screw Holes | standard | $60.00"
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 5:
            continue

        # Name and qty: "Pilot Card x1"
        name_qty = parts[0].strip()
        qty_match = re.search(r'x(\d+)$', name_qty)
        qty = int(qty_match.group(1)) if qty_match else 1
        name = re.sub(r'\s*x\d+$', '', name_qty).strip()

        # Color: "Black" or "Ocean Blue (+$5)"
        color_raw = parts[1].strip()
        color_extra = '(+$5)' in color_raw
        color = color_raw.replace('(+$5)', '').strip()

        mounting  = parts[2].strip()
        text_type = parts[3].strip()

        # Unit price from line total / qty
        price_match = re.search(r'\$([\d.]+)', parts[4])
        line_total = float(price_match.group(1)) if price_match else 0
        unit_full = line_total / qty if qty else 0
        base_price = unit_full - (5 if color_extra else 0)

        order['items'].append({
            'name':       name,
            'price':      base_price,
            'qty':        qty,
            'color':      color,
            'colorExtra': color_extra,
            'mounting':   mounting,
            'textType':   text_type,
        })

    return order


# ── SEND EMAIL WITH PDF ATTACHMENT ──
def send_invoice_email(order, pdf_path, invoice_num):
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured — skipping email send")
        return False

    msg = MIMEMultipart()
    msg['From']    = SMTP_USER
    msg['To']      = ORDERS_EMAIL
    msg['Subject'] = f"New Order — {invoice_num} — {order['name']} — {order.get('order_total','')}"

    # Body
    body = f"""New HarborSPEC order received.

Invoice: {invoice_num}
Customer: {order['name']}
Email: {order['email']}
Phone: {order.get('phone','N/A')}
Vessel: {order.get('vessel','N/A')}
Ship to: {order['address']}, {order['city']}, {order['state']} {order['zip']}
{('County: ' + order['county']) if order.get('county') else ''}

Items:
{chr(10).join(f"  • {i['name']} x{i['qty']} — {i['color']}{'(+$5)' if i.get('colorExtra') else ''} — {i['mounting']}" for i in order['items'])}

Notes: {order.get('notes','None')}

Invoice PDF is attached.
Reply to this email to reach the customer.
"""
    msg.attach(MIMEText(body, 'plain'))

    # Attach PDF
    with open(pdf_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(pdf_path)}"')
        msg.attach(part)

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ORDERS_EMAIL, msg.as_string())
        print(f"Invoice emailed to {ORDERS_EMAIL}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


# ── WEBHOOK ENDPOINT ──
@app.route('/webhook/order', methods=['POST'])
def handle_order():
    # Optional token check
    token = request.headers.get('X-Webhook-Token', '')
    if WEBHOOK_TOKEN and token != WEBHOOK_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401

    # Accept JSON or form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

    print(f"Order received: {data.get('name','?')} — {data.get('order_total','?')}")

    # Parse order
    order = parse_order(data)
    if not order['items']:
        # Fallback: create a single generic line item from order_total
        total_str = data.get('order_total', '$0')
        try:
            total_val = float(total_str.replace('$',''))
        except:
            total_val = 0
        order['items'] = [{
            'name': f"Order ({data.get('item_count','?')} items — see vessel info sheet)",
            'price': total_val,
            'qty': 1,
            'color': 'See order',
            'colorExtra': False,
            'mounting': 'See order',
            'textType': 'standard',
        }]

    # Generate invoice number and PDF
    invoice_num = next_invoice_number()
    order['invoice_num'] = invoice_num
    pdf_path = f'/tmp/invoice_{invoice_num}.pdf'
    generate_invoice(order, output_path=pdf_path)

    # Email it
    sent = send_invoice_email(order, pdf_path, invoice_num)

    return jsonify({
        'status': 'ok',
        'invoice': invoice_num,
        'emailed': sent
    }), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'HarborSPEC Order Server'}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
