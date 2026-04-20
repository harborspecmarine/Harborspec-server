"""
HarborSPEC™ Order Server
Receives orders directly from cart.html via POST.
Also polls Gmail via IMAP every 5 minutes as fallback.
Sends invoices via SendGrid API (HTTPS — no SMTP port issues).
"""

from flask import Flask, request, jsonify
from invoice import generate_invoice
from infosheet import generate_all_info_sheets
import json
import os
import re
import threading
import time
import imaplib
import email
import hmac
import hashlib
import uuid
from email.header import decode_header
from datetime import datetime
import urllib.request
import urllib.parse

app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://harborspecmarine.com')

@app.after_request
def add_cors(response):
    origin = request.headers.get('Origin', '')
    # Allow harborspecmarine.com for cart POSTs
    # Allow CyberSource domains for payment notification POSTs
    if origin == ALLOWED_ORIGIN or 'cybersource.com' in origin:
        response.headers['Access-Control-Allow-Origin']  = origin
    else:
        response.headers['Access-Control-Allow-Origin']  = ALLOWED_ORIGIN
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/order', methods=['OPTIONS'])
def order_preflight():
    return '', 204

@app.route('/payment-complete', methods=['OPTIONS'])
def payment_complete_preflight():
    return '', 204


# ── CONFIG ────────────────────────────────────────────────────────────────────
ORDERS_EMAIL     = os.environ.get('ORDERS_EMAIL',     'orders@harborspecmarine.com')
SMTP_USER        = os.environ.get('SMTP_USER',        '')
SMTP_PASS        = os.environ.get('SMTP_PASS',        '')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
WEBHOOK_TOKEN    = os.environ.get('WEBHOOK_TOKEN',    '')

# INVOICE_START lets you bump the starting number after a restart if needed.
# Set this env var in Railway to any number (e.g. 100) to avoid collisions.
INVOICE_START    = int(os.environ.get('INVOICE_START', 0))

COUNTER_FILE     = '/tmp/hs_counter.txt'

# ── CYBERSOURCE SECURE ACCEPTANCE ──────────────────────────────────────────────
SA_PROFILE_ID = os.environ.get('SA_PROFILE_ID', '')
SA_ACCESS_KEY = os.environ.get('SA_ACCESS_KEY', '')
SA_SECRET_KEY = os.environ.get('SA_SECRET_KEY', '')
# Set SA_TEST_MODE=false in Railway env vars when ready to go live
SA_TEST_MODE  = os.environ.get('SA_TEST_MODE', 'true').lower() != 'false'
SA_ENDPOINT   = ('https://testsecureacceptance.cybersource.com/pay'
                 if SA_TEST_MODE else
                 'https://secureacceptance.cybersource.com/pay')


# ── INVOICE COUNTER ────────────────────────────────────────────────────────────
# Uses a date-prefixed format: HS-260405-001
# The counter resets to 1 each day, which is fine because the date prefix makes
# every number unique. Even if Railway restarts mid-day, the chance of a same-
# date/same-sequence collision is negligible for order volumes at this scale.
def next_invoice_number():
    today = datetime.now().strftime('%y%m%d')   # e.g. 260405
    try:
        raw = open(COUNTER_FILE).read().strip()
        stored_date, stored_seq = raw.split(':')
        if stored_date == today:
            seq = int(stored_seq) + 1
        else:
            # New day — reset sequence
            seq = INVOICE_START + 1
    except Exception:
        # File missing (fresh deploy/restart) — start fresh for today
        seq = INVOICE_START + 1

    open(COUNTER_FILE, 'w').write(f'{today}:{seq}')
    return f'HS-{today}-{seq:03d}'   # e.g. HS-260405-001


# ── SENDGRID EMAIL ────────────────────────────────────────────────────────────
def send_via_sendgrid(to_email, subject, body_text, pdf_path=None, invoice_num=None, extra_attachments=None):
    """Send email via SendGrid HTTPS API. extra_attachments = list of (filename, path) tuples."""
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
                'content':     pdf_data,
                'type':        'application/pdf',
                'filename':    f'invoice_{invoice_num}.pdf',
                'disposition': 'attachment'
            }]
        except Exception as e:
            print(f"  PDF attach error: {e}")

    # Attach any extra PDFs (info sheets)
    if extra_attachments:
        for fname, fpath in extra_attachments:
            try:
                with open(fpath, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                attachments.append({
                    'content':     data,
                    'type':        'application/pdf',
                    'filename':    fname,
                    'disposition': 'attachment'
                })
            except Exception as e:
                print(f"  Extra attach error ({fname}): {e}")

    payload = {
        'personalizations': [{'to': [{'email': to_email}]}],
        'from':     {'email': ORDERS_EMAIL, 'name': 'HarborSPEC'},
        'reply_to': {'email': ORDERS_EMAIL},
        'subject':  subject,
        'content':  [{'type': 'text/plain', 'value': body_text}],
    }
    if attachments:
        payload['attachments'] = attachments

    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=data,
        headers={
            'Authorization': f'Bearer {SENDGRID_API_KEY}',
            'Content-Type':  'application/json',
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


# ── ITEM DETAIL LINE ──────────────────────────────────────────────────────────
def format_item_line(i):
    """
    Build a single human-readable line for an order item.
    Includes measurements/notes when present (e.g. dust cover dimensions).
    """
    color_str = i['color'] + (' (+$5)' if i.get('colorExtra') else '')
    line = f"  \u2022 {i['name']} x{i['qty']} | {color_str} | {i['mounting']}"

    # Append textType notes when they carry real content
    tt = i.get('textType', 'standard')
    if tt and tt not in ('standard', 'custom'):
        line += f"\n      \u2514 {tt}"
    elif tt == 'custom':
        line += " | Custom text"

    return line


# ── EMAIL SENDING ─────────────────────────────────────────────────────────────
def send_invoice_email(order, pdf_path, invoice_num, info_sheets=None):
    """Send invoice to orders inbox and customer. info_sheets = [(name, path), ...]"""
    items_lines = '\n'.join(format_item_line(i) for i in order.get('items', []))

    # Email to you (Paddy) — invoice only, no info sheets needed
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
        f"New Order \u2014 Invoice {invoice_num} \u2014 {order.get('name','')}",
        owner_body, pdf_path, invoice_num
    )

    # Email to customer — invoice + all info sheets attached
    customer_email = order.get('email', '').strip()
    if customer_email:
        first_name = order.get('name','').split()[0] if order.get('name') else 'Captain'
        n_sheets   = len(info_sheets) if info_sheets else 0
        sheet_note = (
            f'\n\nVESSEL INFO SHEETS\n'
            f'{n_sheets} info sheet(s) are attached — one for each product. '
            f'Fill out each PDF digitally or print and complete by hand, '
            f'then email back to {ORDERS_EMAIL}. '
            f'Production begins once we receive your completed sheets.'
        ) if n_sheets else ''

        customer_body = f"""Thank you for your order, {first_name}.

Your invoice and vessel info sheets are attached. The invoice is your record of purchase. Please complete the info sheet(s) and email them back so we can begin production.

INVOICE:  {invoice_num}
VESSEL:   {order.get('vessel','N/A')}

ITEMS ORDERED:
{items_lines}

SHIP TO:
{order.get('address','')}
{order.get('city','')+', ' if order.get('city') else ''}{order.get('state','')} {order.get('zip','')}
{('County: ' + order['county']) if order.get('county') else ''}

NOTES: {order.get('notes','None')}
{sheet_note}

---
QUESTIONS?
Reply to this email or contact us at {ORDERS_EMAIL}

Thank you for your business.
HarborSPEC\u2122
harborspecmarine.com
"""
        # Build extra attachments list for info sheets
        extra = []
        if info_sheets:
            for sheet_name, sheet_path in info_sheets:
                safe = sheet_name.replace(' ', '_').replace('/', '-')[:40]
                extra.append((f'InfoSheet_{safe}.pdf', sheet_path))

        send_via_sendgrid(
            customer_email,
            f"Your HarborSPEC Order \u2014 Invoice {invoice_num}",
            customer_body, pdf_path, invoice_num,
            extra_attachments=extra if extra else None
        )


def sign_sa_request(fields):
    """Generate HMAC-SHA256 signature for CyberSource Secure Acceptance.
    CyberSource requires Base64-encoded HMAC-SHA256, not hex."""
    import base64
    signed_field_names = fields.get('signed_field_names', '')
    values = ','.join(f'{f}={fields.get(f, "")}' for f in signed_field_names.split(','))
    mac = hmac.new(
        SA_SECRET_KEY.encode('utf-8'),
        values.encode('utf-8'),
        hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode('utf-8')


def build_sa_params(order, invoice_num, amount):
    """Build signed CyberSource Secure Acceptance form fields."""
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    ref = invoice_num  # use invoice number as reference

    fields = {
        'access_key':          SA_ACCESS_KEY,
        'profile_id':          SA_PROFILE_ID,
        'transaction_uuid':    str(uuid.uuid4()),
        'signed_date_time':    now,
        'locale':              'en-us',
        'transaction_type':    'sale',
        'reference_number':    ref,
        'amount':              str(amount),
        'currency':            'USD',
        'payment_method':      'card',
        'bill_to_forename':    order.get('name','').split()[0] if order.get('name') else '',
        'bill_to_surname':     ' '.join(order.get('name','').split()[1:]) if len(order.get('name','').split()) > 1 else order.get('name',''),
        'bill_to_email':       order.get('email', ''),
        'bill_to_address_line1': order.get('address', ''),
        'bill_to_address_city':  order.get('city', ''),
        'bill_to_address_state': order.get('state', ''),
        'bill_to_address_country': 'US',
        'bill_to_address_postal_code': order.get('zip', ''),
        'unsigned_field_names': '',
    }

    # Fields to sign — order matters
    signed = [
        'access_key','profile_id','transaction_uuid','signed_field_names',
        'unsigned_field_names','signed_date_time','locale','transaction_type',
        'reference_number','amount','currency','payment_method',
        'bill_to_forename','bill_to_surname','bill_to_email',
        'bill_to_address_line1','bill_to_address_city','bill_to_address_state',
        'bill_to_address_country','bill_to_address_postal_code',
    ]
    fields['signed_field_names'] = ','.join(signed)
    fields['signature'] = sign_sa_request(fields)

    return fields


def process_order(order):
    """Generate invoice, info sheets, and send emails for an order dict."""
    invoice_num          = next_invoice_number()
    order['invoice_num'] = invoice_num
    pdf_path             = f'/tmp/invoice_{invoice_num}.pdf'

    generate_invoice(order, output_path=pdf_path)

    # Generate one info sheet per line item
    try:
        info_sheets = generate_all_info_sheets(order, invoice_num, output_dir='/tmp')
    except Exception as e:
        print(f"  Info sheet generation error: {e}")
        info_sheets = []

    send_invoice_email(order, pdf_path, invoice_num, info_sheets=info_sheets)
    print(f"  Processed: {invoice_num} \u2014 {order.get('name','?')} \u2014 {len(info_sheets)} info sheet(s)")
    return invoice_num


# ── DIRECT ORDER ENDPOINT ─────────────────────────────────────────────────────
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
                item = {
                    'name':         i.get('name', ''),
                    'price':        float(i.get('price', 0)),
                    'qty':          int(i.get('qty', 1)),
                    'color':        i.get('color', ''),
                    'colorExtra':   i.get('colorExtra', False),
                    'mounting':     i.get('mounting', ''),
                    'textType':     i.get('textType', 'standard'),
                    'measurements': i.get('measurements', ''),
                    'coverSize':    i.get('coverSize', ''),
                    'depthOver2':   i.get('depthOver2', False),
                }
                items.append(item)
        except Exception as e:
            print(f"  Item parse error: {e}")

        if not items:
            items = [{'name':'See order details','price':0,'qty':1,'color':'TBD',
                      'colorExtra':False,'mounting':'TBD','textType':'standard',
                      'measurements':'','coverSize':'','depthOver2':False}]

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

        # Build CyberSource Secure Acceptance signed params if configured
        sa_params = None
        if SA_PROFILE_ID and SA_ACCESS_KEY and SA_SECRET_KEY:
            try:
                amount = float(data.get('amount', 0))
                if amount <= 0:
                    # Recalculate from items if not provided
                    amount = sum((i['price'] + (5 if i.get('colorExtra') else 0)) * i['qty'] for i in items)
                sa_fields = build_sa_params(order, invoice_num, round(amount, 2))
                sa_params = {
                    'endpoint': SA_ENDPOINT,
                    'fields':   sa_fields
                }
            except Exception as e:
                print(f"  SA params error: {e}")

        response = {'status': 'ok', 'invoice': invoice_num}
        if sa_params:
            response['sa_params'] = sa_params

        return jsonify(response), 200

    except Exception as e:
        print(f"  Order error: {e}")
        return jsonify({'error': str(e)}), 500


# ── PAYMENT COMPLETE (CyberSource notification) ───────────────────────────────
@app.route('/payment-complete', methods=['POST', 'GET'])
def payment_complete():
    """
    Receives POST notification from CyberSource after payment is processed.
    Logs the result and sends a payment confirmation email.
    """
    try:
        if request.method == 'POST':
            data = request.form.to_dict()
        else:
            data = request.args.to_dict()

        decision       = data.get('decision', 'UNKNOWN')
        reason_code    = data.get('reason_code', '')
        # CyberSource prefixes request fields with req_ in the notification
        invoice_num    = data.get('req_reference_number', data.get('reference_number', 'N/A'))
        amount         = data.get('auth_amount', data.get('req_amount', data.get('amount', 'N/A')))
        card_last4     = data.get('req_card_number', '')[-4:] if data.get('req_card_number') else 'XXXX'
        customer_email = data.get('req_bill_to_email', data.get('bill_to_email', ''))
        customer_name  = (data.get('req_bill_to_forename', '') + ' ' + data.get('req_bill_to_surname', '')).strip()

        print(f"  Payment notification: {decision} | {invoice_num} | ${amount} | {customer_email}")
        print(f"  All fields: {list(data.keys())}")

        if decision == 'ACCEPT':
            # Send payment confirmed email to owner
            body = f"""Payment received for HarborSPEC order.

Invoice:   {invoice_num}
Customer:  {customer_name.strip()}
Email:     {customer_email}
Amount:    ${amount}
Card:      ending {card_last4}
Decision:  {decision}
Reason:    {reason_code}

Order is confirmed. Begin production.
"""
            send_via_sendgrid(
                ORDERS_EMAIL,
                f'Payment Confirmed \u2014 {invoice_num} \u2014 ${amount}',
                body
            )

            # Notify customer payment was received
            if customer_email:
                customer_body = f"""Hi {customer_name.strip().split()[0] if customer_name.strip() else 'Captain'},

Your payment of ${amount} has been received for HarborSPEC order {invoice_num}.

Production will begin shortly. Standard lead time is 2 weeks from payment.

Thank you for your business.
HarborSPEC\u2122
harborspecmarine.com
"""
                send_via_sendgrid(
                    customer_email,
                    f'Payment Received \u2014 HarborSPEC Order {invoice_num}',
                    customer_body
                )

        elif decision in ('DECLINE', 'ERROR', 'REVIEW'):
            body = f"""Payment {decision} for HarborSPEC order.

Invoice:  {invoice_num}
Customer: {customer_name.strip()}
Email:    {customer_email}
Amount:   ${amount}
Decision: {decision}
Reason:   {reason_code}

Follow up with customer if needed.
"""
            send_via_sendgrid(
                ORDERS_EMAIL,
                f'Payment {decision} \u2014 {invoice_num}',
                body
            )

        return jsonify({'status': 'received', 'decision': decision}), 200

    except Exception as e:
        print(f"  Payment complete error: {e}")
        return jsonify({'error': str(e)}), 500


# ── GMAIL POLLING (fallback) ──────────────────────────────────────────────────
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
            line = line.strip().lstrip('\u2022').strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                continue
            nq  = parts[0]
            qm  = re.search(r'x(\d+)$', nq)
            qty = int(qm.group(1)) if qm else 1
            name      = re.sub(r'\s*x\d+$', '', nq).strip()
            cr        = parts[1]
            color_extra = '+$5' in cr
            color       = cr.replace('(+$5)', '').replace('+$5', '').strip()
            mounting    = parts[2] if len(parts) > 2 else ''
            text_type   = parts[3] if len(parts) > 3 else 'standard'
            pm          = re.search(r'\$([\d.]+)', parts[-1]) if len(parts) > 4 else None
            line_total  = float(pm.group(1)) if pm else 0
            unit_full   = (line_total / qty) if qty else 0
            base_price  = unit_full - (5 if color_extra else 0)
            order['items'].append({
                'name': name, 'price': base_price, 'qty': qty,
                'color': color, 'colorExtra': color_extra,
                'mounting': mounting, 'textType': text_type,
                'measurements': '', 'coverSize': '', 'depthOver2': False,
            })
    if not order['items']:
        order['items'] = [{'name':'See order','price':0,'qty':1,'color':'TBD',
                           'colorExtra':False,'mounting':'TBD','textType':'standard',
                           'measurements':'','coverSize':'','depthOver2':False}]
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
                msg  = email.message_from_bytes(data[0][1])
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


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route('/debug-sa', methods=['GET'])
def debug_sa():
    """Temporary debug endpoint — shows what SA params would be generated."""
    if not WEBHOOK_TOKEN or request.args.get('token') != WEBHOOK_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    test_order = {
        'name': 'Test User', 'email': 'test@test.com',
        'address': '123 Test St', 'city': 'Bay Shore',
        'state': 'NY', 'zip': '11706', 'county': 'Suffolk'
    }
    fields = build_sa_params(test_order, 'HS-TEST-001', 60.00)
    return jsonify({
        'endpoint':           SA_ENDPOINT,
        'profile_id':         SA_PROFILE_ID,
        'access_key':         SA_ACCESS_KEY[:8] + '...' if SA_ACCESS_KEY else 'MISSING',
        'secret_key':         'SET' if SA_SECRET_KEY else 'MISSING',
        'signed_field_names': fields.get('signed_field_names'),
        'signature_length':   len(fields.get('signature', '')),
        'test_mode':          SA_TEST_MODE,
    })


@app.route('/health')
def health():
    return jsonify({
        'status':   'ok',
        'service':  'HarborSPEC Order Server',
        'sendgrid': bool(SENDGRID_API_KEY),
        'smtp':     bool(SMTP_USER and SMTP_PASS),
        'payments': bool(SA_PROFILE_ID and SA_ACCESS_KEY and SA_SECRET_KEY),
        'test_mode': SA_TEST_MODE,
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
