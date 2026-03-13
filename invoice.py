#!/usr/bin/env python3
"""
HarborSPEC™ Invoice Generator
Generates a branded PDF invoice from order data.
Usage: python3 generate_invoice.py  (uses sample data)
Or: import and call generate_invoice(order) from your own code.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from datetime import datetime, timedelta
import os

# ── BRAND COLORS ──
NAVY      = HexColor('#0d1b2a')
BRASS     = HexColor('#c49a2e')
BRASS_LT  = HexColor('#e8be5a')
FOG       = HexColor('#8fa8be')
STEEL     = HexColor('#2e4a62')
WHITE     = HexColor('#ffffff')
LIGHT     = HexColor('#d4e3ef')
CHARCOAL  = HexColor('#1a2f45')

PAGE_W, PAGE_H = letter  # 612 x 792 pt

def draw_header(c, invoice_num, date_str, due_str):
    """Draw the branded header band."""
    # Navy background band
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 1.6*inch, PAGE_W, 1.6*inch, fill=1, stroke=0)

    # Brass accent bar
    c.setFillColor(BRASS)
    c.rect(0, PAGE_H - 1.6*inch - 4, PAGE_W, 4, fill=1, stroke=0)

    # Logo text — HARBOR
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 26)
    c.drawString(0.5*inch, PAGE_H - 0.7*inch, 'HARBOR')

    # SPEC in brass
    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 26)
    harbor_w = c.stringWidth('HARBOR', 'Helvetica-Bold', 26)
    c.drawString(0.5*inch + harbor_w, PAGE_H - 0.7*inch, 'SPEC')

    # TM superscript
    tm_x = 0.5*inch + harbor_w + c.stringWidth('SPEC', 'Helvetica-Bold', 26) + 2
    c.setFont('Helvetica-Bold', 10)
    c.drawString(tm_x, PAGE_H - 0.52*inch, 'TM')

    # Tagline
    c.setFillColor(FOG)
    c.setFont('Helvetica', 8)
    c.drawString(0.5*inch, PAGE_H - 0.95*inch, 'Professional Bridge Reference Systems')

    # INVOICE label
    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 20)
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 0.65*inch, 'INVOICE')

    # Invoice number + dates (right side)
    c.setFillColor(FOG)
    c.setFont('Helvetica', 8)
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 0.88*inch, f'Invoice #  {invoice_num}')
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 1.02*inch, f'Date:  {date_str}')
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 1.16*inch, f'Due:   {due_str}')


def draw_addresses(c, order):
    """Draw FROM and TO address blocks."""
    y = PAGE_H - 2.1*inch

    # FROM
    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(0.5*inch, y, 'FROM')
    y -= 0.18*inch

    c.setFillColor(LIGHT)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(0.5*inch, y, 'HarborSPEC™')
    y -= 0.17*inch

    c.setFillColor(FOG)
    c.setFont('Helvetica', 8.5)
    from_lines = [
        'Suffolk County, New York',
        'harborspecmarineorders@gmail.com',
        'harborspecmarine.com',
    ]
    for line in from_lines:
        c.drawString(0.5*inch, y, line)
        y -= 0.16*inch

    # TO
    y = PAGE_H - 2.1*inch
    right_x = PAGE_W / 2

    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(right_x, y, 'BILL / SHIP TO')
    y -= 0.18*inch

    c.setFillColor(LIGHT)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(right_x, y, order.get('name', ''))
    y -= 0.17*inch

    c.setFillColor(FOG)
    c.setFont('Helvetica', 8.5)
    to_lines = [
        order.get('address', ''),
        f"{order.get('city','')}, {order.get('state','')} {order.get('zip','')}",
        order.get('email', ''),
    ]
    if order.get('phone'):
        to_lines.append(order['phone'])
    if order.get('vessel'):
        to_lines.append(f"Vessel: {order['vessel']}")

    for line in to_lines:
        if line.strip():
            c.drawString(right_x, y, line)
            y -= 0.16*inch


def draw_items_table(c, items, start_y):
    """Draw the line items table. Returns y position after table."""
    col_x = {
        'item':   0.5*inch,
        'color':  3.2*inch,
        'mount':  4.1*inch,
        'qty':    5.0*inch,
        'unit':   5.4*inch,
        'total':  6.1*inch,
    }
    row_h = 0.28*inch
    y = start_y

    # Header row background
    c.setFillColor(STEEL)
    c.rect(0.4*inch, y - row_h + 4, PAGE_W - 0.8*inch, row_h, fill=1, stroke=0)

    # Header labels
    c.setFillColor(BRASS_LT)
    c.setFont('Helvetica-Bold', 7.5)
    headers = [
        ('item',  'ITEM / DESCRIPTION'),
        ('color', 'COLOR'),
        ('mount', 'MOUNTING'),
        ('qty',   'QTY'),
        ('unit',  'UNIT'),
        ('total', 'TOTAL'),
    ]
    for key, label in headers:
        if key in ('qty', 'unit', 'total'):
            # right-align numbers
            x = col_x[key] + (0.55*inch if key != 'total' else 0.5*inch)
            c.drawCentredString(col_x[key] + 0.2*inch, y - row_h + 10, label)
        else:
            c.drawString(col_x[key], y - row_h + 10, label)
    y -= row_h

    # Item rows
    for i, item in enumerate(items):
        row_bg = HexColor('#0f2336') if i % 2 == 0 else HexColor('#0d1b2a')
        c.setFillColor(row_bg)
        c.rect(0.4*inch, y - row_h + 4, PAGE_W - 0.8*inch, row_h, fill=1, stroke=0)

        unit_price = item['price'] + (5 if item.get('colorExtra') else 0)
        line_total = unit_price * item['qty']
        text_note = ' (Custom)' if item.get('textType') == 'custom' else ''

        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(col_x['item'], y - row_h + 10, item['name'] + text_note)

        c.setFillColor(LIGHT)
        c.setFont('Helvetica', 8)
        color_str = item.get('color','') + ('+$5' if item.get('colorExtra') else '')
        c.drawString(col_x['color'], y - row_h + 10, color_str)
        c.drawString(col_x['mount'], y - row_h + 10, item.get('mounting','')[:16])
        c.drawCentredString(col_x['qty'] + 0.2*inch, y - row_h + 10, str(item['qty']))

        c.setFillColor(FOG)
        c.drawCentredString(col_x['unit'] + 0.2*inch, y - row_h + 10, f'${unit_price:.2f}')

        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawRightString(col_x['total'] + 0.45*inch, y - row_h + 10, f'${line_total:.2f}')

        y -= row_h

    # Bottom border
    c.setStrokeColor(STEEL)
    c.setLineWidth(0.5)
    c.line(0.4*inch, y + 4, PAGE_W - 0.4*inch, y + 4)

    return y


def draw_totals(c, subtotal, shipping, tax_rate, tax_amount, total, county, y):
    """Draw the totals block at bottom right."""
    right_edge = PAGE_W - 0.5*inch
    label_x    = PAGE_W - 3.2*inch
    y -= 0.15*inch

    def total_row(label, amount, bold=False, color=None):
        nonlocal y
        c.setFillColor(color or FOG)
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', 8.5 if not bold else 9)
        c.drawString(label_x, y, label)
        c.setFillColor(color or (WHITE if bold else LIGHT))
        c.drawRightString(right_edge, y, amount)
        y -= 0.22*inch

    total_row('Subtotal', f'${subtotal:.2f}')
    total_row('Shipping', 'FREE' if shipping == 0 else f'${shipping:.2f}')
    if tax_rate > 0:
        county_display = county.title() if county else 'NY'
        total_row(f'NY Sales Tax — {county_display} County', '')
        total_row(f'  Rate: {tax_rate*100:.3f}%', f'${tax_amount:.2f}')
    else:
        total_row('Sales Tax', 'N/A — Outside NY')

    # Divider
    y -= 0.05*inch
    c.setStrokeColor(BRASS)
    c.setLineWidth(1)
    c.line(label_x, y + 4, right_edge, y + 4)
    y -= 0.1*inch

    total_row('TOTAL DUE', f'${total:.2f}', bold=True, color=BRASS)


def draw_footer(c, invoice_num, notes=''):
    """Draw footer with payment instructions."""
    y = 1.4*inch

    # Brass line
    c.setStrokeColor(BRASS)
    c.setLineWidth(1)
    c.line(0.5*inch, y, PAGE_W - 0.5*inch, y)
    y -= 0.22*inch

    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(0.5*inch, y, 'PAYMENT')
    y -= 0.18*inch

    c.setFillColor(FOG)
    c.setFont('Helvetica', 8)
    payment_lines = [
        'Payment is due upon receipt of invoice. A payment link will be sent separately.',
        'Lead time is approximately 2 weeks from receipt of your completed vessel info sheet.',
        'Questions? Email harborspecmarineorders@gmail.com',
    ]
    if notes:
        payment_lines.insert(0, f'Order Notes: {notes}')

    for line in payment_lines:
        c.drawString(0.5*inch, y, line)
        y -= 0.16*inch

    # Invoice number at very bottom
    c.setFillColor(STEEL)
    c.setFont('Helvetica', 7)
    c.drawCentredString(PAGE_W / 2, 0.6*inch, f'HarborSPEC™  |  Invoice {invoice_num}  |  harborspecmarine.com')


def generate_invoice(order, output_path=None):
    """
    Generate a HarborSPEC invoice PDF.

    order = {
        'invoice_num': 'HS-0001',          # auto-generated if not provided
        'name': 'John Smith',
        'email': 'john@example.com',
        'phone': '555-000-0000',           # optional
        'vessel': 'MV Some Vessel',        # optional
        'address': '123 Harbor Drive',
        'city': 'Bay Shore',
        'state': 'NY',
        'zip': '11706',
        'county': 'Suffolk',               # for NY tax
        'notes': '',                       # optional
        'items': [
            {
                'name': 'Pilot Card',
                'price': 60,
                'qty': 1,
                'color': 'Black',
                'colorExtra': False,
                'mounting': '2-Screw Holes',
                'textType': 'standard',
            },
            ...
        ]
    }
    """
    # Auto invoice number from timestamp if not supplied
    if not order.get('invoice_num'):
        order['invoice_num'] = 'HS-' + datetime.now().strftime('%Y%m%d%H%M')

    inv_num  = order['invoice_num']
    today    = datetime.now()
    due_date = today + timedelta(days=7)
    date_str = today.strftime('%B %d, %Y')
    due_str  = due_date.strftime('%B %d, %Y')

    if not output_path:
        safe_name = inv_num.replace('/', '-')
        output_path = f'/mnt/user-data/outputs/invoice_{safe_name}.pdf'

    # ── CALCULATE TOTALS ──
    items    = order.get('items', [])
    subtotal = sum((it['price'] + (5 if it.get('colorExtra') else 0)) * it['qty'] for it in items)
    shipping = 0 if subtotal >= 100 else 9.95

    # NY tax
    NY_TAX = {
        'albany':0.08,'allegany':0.085,'bronx':0.08875,'broome':0.08,'cattaraugus':0.08,
        'cayuga':0.08,'chautauqua':0.08,'chemung':0.08,'chenango':0.08,'clinton':0.08,
        'columbia':0.08,'cortland':0.08,'delaware':0.08,'dutchess':0.08375,'erie':0.08,
        'essex':0.08,'franklin':0.08,'fulton':0.085,'genesee':0.08,'greene':0.08,
        'hamilton':0.08,'herkimer':0.085,'jefferson':0.08,'kings':0.08875,'lewis':0.08,
        'livingston':0.08,'madison':0.08,'manhattan':0.08875,'monroe':0.08,'montgomery':0.085,
        'nassau':0.08625,'niagara':0.08,'oneida':0.08,'onondaga':0.08,'ontario':0.08,
        'orange':0.08375,'orleans':0.08,'oswego':0.08,'otsego':0.08,'putnam':0.08375,
        'queens':0.08875,'rensselaer':0.08,'richmond':0.08875,'rockland':0.08375,
        'saratoga':0.08,'schenectady':0.08,'schoharie':0.08,'schuyler':0.08,
        'seneca':0.08,'st. lawrence':0.08,'steuben':0.08,'suffolk':0.08625,
        'sullivan':0.08,'tioga':0.08,'tompkins':0.08,'ulster':0.08,'warren':0.08,
        'washington':0.08,'wayne':0.08,'westchester':0.08375,'wyoming':0.08,'yates':0.08,
        'brooklyn':0.08875, 'staten island':0.08875,
    }
    state  = order.get('state','').strip().upper()
    county = order.get('county','').strip().lower()
    county = county.replace(' county','').replace(' (brooklyn)','').replace(' (manhattan)','').replace(' (staten island)','')
    tax_rate = NY_TAX.get(county, 0) if state == 'NY' else 0
    tax_amt  = subtotal * tax_rate
    total    = subtotal + shipping + tax_amt

    # ── BUILD PDF ──
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setTitle(f'HarborSPEC Invoice {inv_num}')
    c.setAuthor('HarborSPEC')

    # Dark page background
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    draw_header(c, inv_num, date_str, due_str)
    draw_addresses(c, order)

    # Section label
    table_start_y = PAGE_H - 3.2*inch
    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(0.5*inch, table_start_y + 0.18*inch, 'ORDER ITEMS')

    after_table_y = draw_items_table(c, items, table_start_y)

    draw_totals(c, subtotal, shipping, tax_rate, tax_amt, total,
                order.get('county',''), after_table_y)

    draw_footer(c, inv_num, order.get('notes',''))

    c.save()
    print(f'Invoice generated: {output_path}')
    print(f'  Invoice #: {inv_num}')
    print(f'  Customer:  {order.get("name","")}')
    print(f'  Total:     ${total:.2f}')
    return output_path

