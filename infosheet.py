#!/usr/bin/env python3
"""
HarborSPEC™ Vessel Info Sheet Generator
Creates fillable PDF info sheets for each ordered product.
Customer fills out and emails back — one PDF per product.
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from datetime import datetime
import os

# ── Brand colors ──
NAVY     = HexColor('#0d1b2a')
BRASS    = HexColor('#c49a2e')
BRASS_LT = HexColor('#e8be5a')
FOG      = HexColor('#8fa8be')
STEEL    = HexColor('#2e4a62')
WHITE    = HexColor('#ffffff')
LIGHT    = HexColor('#d4e3ef')
CHARCOAL = HexColor('#1a2f45')

PAGE_W, PAGE_H = letter  # 612 x 792


# ── Product type detection ─────────────────────────────────────────────────────
def detect_product_type(item_name):
    """Map item name to a product type key."""
    n = item_name.lower()
    if 'pilot card' in n:                          return 'pilot_card'
    if 'steering procedure' in n:                  return 'steering_procedures'
    if 'loss of steering' in n:                    return 'loss_of_steering'
    if 'bnwas' in n:                               return 'bnwas'
    if 'tow wire' in n or 'capacit' in n:          return 'tow_wire'
    if 'compass' in n:                             return 'compass_frame'
    if 'custom plaque' in n:                       return 'custom_plaque'
    if 'dust cover' in n:                          return 'dust_cover'
    if 'multi-switch' in n or 'switch panel' in n: return 'multi_switch'
    if 'gang' in n or 'outlet' in n or 'plate' in n or 'cover' in n:
        return 'wall_plate'
    if any(x in n for x in ['general alarm', 'muster station', 'life jacket',
                              'watertight', 'off watch', 'crew sleeping',
                              'smoking area', 'visitor sign']):
        return 'safety_fixed'
    if 'emergency contact' in n:                   return 'emergency_contacts'
    if 'standing order' in n:                      return 'standing_orders'
    return 'generic'


# ── Drawing helpers ────────────────────────────────────────────────────────────
def draw_header(c, invoice_num, item_name, order_date):
    """Draw branded header on each info sheet."""
    # Navy band
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 1.3*inch, PAGE_W, 1.3*inch, fill=1, stroke=0)
    # Brass accent
    c.setFillColor(BRASS)
    c.rect(0, PAGE_H - 1.3*inch - 3, PAGE_W, 3, fill=1, stroke=0)

    # Logo
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 22)
    c.drawString(0.5*inch, PAGE_H - 0.62*inch, 'HARBOR')
    c.setFillColor(BRASS)
    hw = c.stringWidth('HARBOR', 'Helvetica-Bold', 22)
    c.drawString(0.5*inch + hw, PAGE_H - 0.62*inch, 'SPEC')
    tm_x = 0.5*inch + hw + c.stringWidth('SPEC', 'Helvetica-Bold', 22) + 2
    c.setFont('Helvetica-Bold', 8)
    c.drawString(tm_x, PAGE_H - 0.47*inch, 'TM')

    c.setFillColor(FOG)
    c.setFont('Helvetica', 7.5)
    c.drawString(0.5*inch, PAGE_H - 0.82*inch, 'Vessel Info Sheet — Complete and email to orders@harborspecmarine.com')

    # Right side
    c.setFillColor(BRASS)
    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 0.52*inch, item_name.upper())
    c.setFillColor(FOG)
    c.setFont('Helvetica', 7.5)
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 0.70*inch, f'Invoice: {invoice_num}')
    c.drawRightString(PAGE_W - 0.5*inch, PAGE_H - 0.84*inch, f'Date: {order_date}')


def draw_instructions(c, y, text):
    """Draw a grey instruction box."""
    c.setFillColor(HexColor('#f0f4f8'))
    c.rect(0.5*inch, y - 0.32*inch, PAGE_W - inch, 0.32*inch, fill=1, stroke=0)
    c.setFillColor(HexColor('#2e4a62'))
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(0.6*inch, y - 0.2*inch, text)
    return y - 0.5*inch


def draw_section_title(c, y, title):
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(0.5*inch, y, title)
    c.setStrokeColor(BRASS)
    c.setLineWidth(0.75)
    c.line(0.5*inch, y - 3, PAGE_W - 0.5*inch, y - 3)
    return y - 0.22*inch


def draw_field(c, acro, y, label, field_name, height=0.3*inch, multiline=False, value=''):
    """Draw a labelled field with optional AcroForm input."""
    field_y = y - height
    field_w = PAGE_W - inch

    # Label
    c.setFillColor(HexColor('#333333'))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(0.5*inch, y - 0.01*inch, label)

    # Field box
    c.setFillColor(HexColor('#f9f9f9'))
    c.setStrokeColor(HexColor('#cccccc'))
    c.setLineWidth(0.5)
    c.rect(0.5*inch, field_y, field_w, height, fill=1, stroke=1)

    # AcroForm text field
    if multiline:
        acro.textfield(
            name=field_name,
            tooltip=label,
            x=0.5*inch + 2,
            y=field_y + 2,
            width=field_w - 4,
            height=height - 4,
            value=value,
            fontName='Helvetica',
            fontSize=9,
            borderColor=None,
            fillColor=None,
            textColor=HexColor('#111111'),
            forceBorder=False,
            fieldFlags='multiline',
        )
    else:
        acro.textfield(
            name=field_name,
            tooltip=label,
            x=0.5*inch + 2,
            y=field_y + 2,
            width=field_w - 4,
            height=height - 4,
            value=value,
            fontName='Helvetica',
            fontSize=9,
            borderColor=None,
            fillColor=None,
            textColor=HexColor('#111111'),
            forceBorder=False,
        )

    return field_y - 0.15*inch


def draw_two_fields(c, acro, y, label1, name1, label2, name2, height=0.3*inch):
    """Draw two fields side by side."""
    field_y = y - height
    half_w = (PAGE_W - inch - 0.15*inch) / 2

    for i, (lbl, nm) in enumerate([(label1, name1), (label2, name2)]):
        x = 0.5*inch + i * (half_w + 0.15*inch)
        c.setFillColor(HexColor('#333333'))
        c.setFont('Helvetica-Bold', 8)
        c.drawString(x, y - 0.01*inch, lbl)
        c.setFillColor(HexColor('#f9f9f9'))
        c.setStrokeColor(HexColor('#cccccc'))
        c.setLineWidth(0.5)
        c.rect(x, field_y, half_w, height, fill=1, stroke=1)
        acro.textfield(
            name=nm, tooltip=lbl,
            x=x + 2, y=field_y + 2,
            width=half_w - 4, height=height - 4,
            fontName='Helvetica', fontSize=9,
            borderColor=None, fillColor=None,
            textColor=HexColor('#111111'), forceBorder=False,
        )

    return field_y - 0.15*inch


def draw_footer(c, invoice_num, page_num, total_pages):
    c.setStrokeColor(BRASS)
    c.setLineWidth(0.5)
    c.line(0.5*inch, 0.65*inch, PAGE_W - 0.5*inch, 0.65*inch)
    c.setFillColor(FOG)
    c.setFont('Helvetica', 7)
    c.drawString(0.5*inch, 0.45*inch,
        f'HarborSPEC™  |  Invoice {invoice_num}  |  orders@harborspecmarine.com  |  harborspecmarine.com')
    c.drawRightString(PAGE_W - 0.5*inch, 0.45*inch, f'Page {page_num} of {total_pages}')


# ── Product-specific sheet builders ───────────────────────────────────────────

def sheet_pilot_card(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Pilot Card', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Fill in all vessel particulars exactly as they should appear on your pilot card.')
    y = draw_section_title(c, y, 'VESSEL PARTICULARS')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y = draw_two_fields(c, acro, y, 'Official Number', 'official_num', 'Call Sign', 'call_sign')
    y = draw_two_fields(c, acro, y, 'Length (ft)', 'length', 'Breadth (ft)', 'breadth')
    y = draw_two_fields(c, acro, y, 'Depth (ft)', 'depth', 'Air Draft (ft)', 'air_draft')
    y = draw_two_fields(c, acro, y, 'GRT', 'grt', 'NRT', 'nrt')
    y = draw_field(c, acro, y, 'Phone Number', 'phone')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'ADDITIONAL NOTES (optional)')
    y = draw_field(c, acro, y, 'Any additional info or special requests', 'notes',
                   height=0.75*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_steering_procedures(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Steering Procedures', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Standard regulatory text will be used unless you specify custom procedures below.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'TEXT PREFERENCE')

    # Checkboxes for standard vs custom
    for label, val in [('Use standard regulatory steering procedures text', 'standard'),
                       ('Use custom text (enter below)', 'custom')]:
        c.setFillColor(HexColor('#f9f9f9'))
        c.setStrokeColor(HexColor('#cccccc'))
        c.rect(0.5*inch, y - 0.18*inch, 0.18*inch, 0.18*inch, fill=1, stroke=1)
        acro.checkbox(name=f'choice_{val}', tooltip=label,
                      x=0.5*inch, y=y - 0.18*inch,
                      size=0.18*inch, checked=(val == 'standard'),
                      borderColor=HexColor('#cccccc'), fillColor=None)
        c.setFillColor(HexColor('#111111'))
        c.setFont('Helvetica', 8.5)
        c.drawString(0.5*inch + 0.25*inch, y - 0.13*inch, label)
        y -= 0.28*inch

    y -= 0.05*inch
    y = draw_section_title(c, y, 'CUSTOM TEXT (if applicable)')
    y = draw_field(c, acro, y, 'Enter your custom steering procedures text',
                   'custom_text', height=2.2*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'ADDITIONAL NOTES (optional)')
    y = draw_field(c, acro, y, 'Additional requests', 'notes', height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_loss_of_steering(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Loss of Steering', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Select the preset that best matches your vessel, or choose Custom and enter your own text.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.12*inch
    y = draw_section_title(c, y, 'SELECT LOSS OF STEERING PROCEDURE')

    # Option text — shown in preview boxes inside each card
    opt1_lines = [
        'IF ON AUTO PILOT, PUSH STBY AND SWITCH',
        'SELECTOR TO NFU. IF ABOVE FAILS OR ON NFU,',
        'SWITCH STEERING PUMPS.',
        'TOTAL LOSS: NOTIFY CREW / SOUND GENERAL ALARM /',
        'IF NEEDED, OPERATE FROM ENGINE ROOM.',
        'IF MOVING A MANNED BARGE, NOTIFY CREW AND',
        'HAVE THEM READY TO DROP ANCHOR.',
        'NOTIFY ALL TRAFFIC IN THE AREA AND DISPLAY',
        'PROPER LIGHTS OR DAY SHAPES.',
        'CAPTAIN AND ENGINEER MUST BE ADVISED.',
    ]
    opt2_lines = [
        'SOUND GENERAL ALARM',
        '1  SWITCH TO AUXILIARY STEERING PUMP',
        '2  ALERT THE MASTER AND ENGINEER',
        '3  TAKE WAY OFF THE TOW',
        '4  NOTE IN LOGS — POSITION, SET AND DRIFT',
        '5  ALERT ALL VESSELS IN VICINITY',
        '6  CONTACT VTS AND USCG',
        '7  DISPLAY PROPER LIGHTS OR DAY SHAPES',
    ]

    cell_w = PAGE_W - inch
    cell_h = 1.72*inch
    gap    = 0.12*inch

    def draw_preset_card(cx, cy, name, title, lines, checked=False):
        # Card
        c.setFillColor(HexColor('#f0f4f8'))
        c.setStrokeColor(HexColor('#c0cfd8'))
        c.setLineWidth(0.75)
        c.roundRect(cx, cy - cell_h, cell_w, cell_h, 5, fill=1, stroke=1)
        # Checkbox
        cb_size = 0.17*inch
        acro.checkbox(name=name, tooltip=title,
                      x=cx + 0.12*inch, y=cy - 0.28*inch,
                      size=cb_size, checked=checked,
                      borderColor=HexColor('#aaaaaa'), fillColor=HexColor('#ffffff'))
        # Title
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(cx + 0.12*inch + cb_size + 0.08*inch, cy - 0.22*inch, title)
        # Divider
        c.setStrokeColor(HexColor('#c0cfd8'))
        c.setLineWidth(0.5)
        c.line(cx + 0.12*inch, cy - 0.33*inch, cx + cell_w - 0.12*inch, cy - 0.33*inch)
        # Preview text
        c.setFillColor(HexColor('#333333'))
        c.setFont('Helvetica', 6.8)
        for li, line in enumerate(lines):
            if cy - 0.44*inch - li * 0.115*inch < cy - cell_h + 0.1*inch:
                break
            c.drawString(cx + 0.15*inch, cy - 0.44*inch - li * 0.115*inch, line)

    draw_preset_card(0.5*inch, y, 'opt_autopilot',
                     'OPTION 1 — AUTOPILOT / NFU VESSEL', opt1_lines)
    y -= cell_h + gap

    draw_preset_card(0.5*inch, y, 'opt_numbered',
                     'OPTION 2 — NUMBERED STEPS (TUG/TOW)', opt2_lines)
    y -= cell_h + gap

    # Custom card — half width pair
    half_w = (cell_w - gap) / 2
    small_h = 0.55*inch

    # Custom checkbox card
    c.setFillColor(HexColor('#f0f4f8'))
    c.setStrokeColor(HexColor('#c0cfd8'))
    c.setLineWidth(0.75)
    c.roundRect(0.5*inch, y - small_h, half_w, small_h, 5, fill=1, stroke=1)
    cb_size = 0.17*inch
    acro.checkbox(name='opt_custom', tooltip='Custom text',
                  x=0.5*inch + 0.12*inch, y=y - 0.28*inch,
                  size=cb_size, checked=False,
                  borderColor=HexColor('#aaaaaa'), fillColor=HexColor('#ffffff'))
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(0.5*inch + 0.12*inch + cb_size + 0.08*inch, y - 0.22*inch, 'CUSTOM')
    c.setFillColor(HexColor('#555555'))
    c.setFont('Helvetica', 7.5)
    c.drawString(0.5*inch + 0.15*inch, y - 0.40*inch, 'None of the above — enter below.')

    y -= small_h + gap

    y = draw_section_title(c, y, 'CUSTOM TEXT (required if Custom selected above)')
    y = draw_field(c, acro, y,
                   'Enter your complete loss of steering procedure exactly as you want it to appear',
                   'custom_text', height=1.0*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_bnwas(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'BNWAS Panel', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Check the option that matches your vessel, or select Custom and enter your own text.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.12*inch
    y = draw_section_title(c, y, 'SELECT ACTIVATION TYPE')

    options = [
        ('opt_manual',   'MANUAL ACTIVATION',
         ['System must be turned on manually', 'prior to getting underway.']),
        ('opt_engines',  'AUTO — ENGINES IN GEAR',
         ['Do not power off — system will activate', 'automatically while engines are in gear.']),
        ('opt_steering', 'AUTO — STEERING PUMP',
         ['Do not power off — system will activate', 'automatically while steering pump is running.']),
        ('opt_custom',   'CUSTOM',
         ['None of the above apply — enter your', 'vessel’s specific procedure below.']),
    ]

    cell_w  = (PAGE_W - inch - 0.15*inch) / 2
    cell_h  = 1.05*inch
    gap     = 0.15*inch
    start_y = y

    for i, (name, title, body_lines) in enumerate(options):
        col = i % 2
        row = i // 2
        cx  = 0.5*inch + col * (cell_w + gap)
        cy  = start_y - row * (cell_h + gap)

        c.setFillColor(HexColor('#f0f4f8'))
        c.setStrokeColor(HexColor('#c0cfd8'))
        c.setLineWidth(0.75)
        c.roundRect(cx, cy - cell_h, cell_w, cell_h, 5, fill=1, stroke=1)

        cb_size = 0.17*inch
        cb_x = cx + 0.12*inch
        cb_y = cy - 0.28*inch
        acro.checkbox(name=name, tooltip=title,
                      x=cb_x, y=cb_y, size=cb_size, checked=False,
                      borderColor=HexColor('#aaaaaa'), fillColor=HexColor('#ffffff'))

        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(cb_x + cb_size + 0.1*inch, cb_y + 0.03*inch, title)

        c.setFillColor(HexColor('#333333'))
        c.setFont('Helvetica', 7.5)
        for li, line in enumerate(body_lines):
            c.drawString(cx + 0.12*inch, cy - 0.52*inch - li * 0.17*inch, line)

    y = start_y - 2 * (cell_h + gap) - 0.15*inch

    y = draw_section_title(c, y, 'CUSTOM TEXT (required if Custom selected above)')
    y = draw_field(c, acro, y, 'Enter your custom BNWAS panel text exactly as you want it to appear',
                   'custom_text', height=1.1*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional requests', 'notes', height=0.5*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_tow_wire(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Tow Wire / Capacities', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Use the Wire Length Calculator at harborspecmarine.com/wire-calculator.html to get your values, then fill in below.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'WIRE LENGTH TABLE (center to center on drum)')

    # 16 rows, split into 2 columns of 8 (each column = Layer | Length)
    # 4 printed columns: Layer | Length (ft) | Layer | Length (ft)
    ROWS = 16
    col_w  = (PAGE_W - inch) / 4   # width of each of the 4 columns
    row_h  = 0.215*inch

    # Column headers
    headers = ['Layer', 'Length (ft)', 'Layer', 'Length (ft)']
    for i, h in enumerate(headers):
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(NAVY)
        c.drawString(0.5*inch + i * col_w + 4, y, h)
    y -= 0.18*inch

    for row in range(ROWS // 2):          # 8 rows printed per side
        for col_pair in range(2):         # left half (rows 1-8) and right half (rows 9-16)
            row_num  = row + col_pair * (ROWS // 2) + 1   # 1-based row label
            base_x   = 0.5*inch + col_pair * 2 * col_w

            # Layer field (blank)
            c.setFillColor(HexColor('#f9f9f9'))
            c.setStrokeColor(HexColor('#cccccc'))
            c.setLineWidth(0.5)
            c.rect(base_x, y - row_h, col_w - 4, row_h, fill=1, stroke=1)
            acro.textfield(name=f'layer_{row_num}',
                           tooltip=f'Row {row_num} layer',
                           x=base_x + 2, y=y - row_h + 2,
                           width=col_w - 8, height=row_h - 4,
                           fontName='Helvetica', fontSize=8,
                           borderColor=None, fillColor=None,
                           textColor=HexColor('#111'), forceBorder=False)

            # Length field (blank)
            lx = base_x + col_w
            c.setFillColor(HexColor('#f9f9f9'))
            c.rect(lx, y - row_h, col_w - 4, row_h, fill=1, stroke=1)
            acro.textfield(name=f'length_{row_num}',
                           tooltip=f'Row {row_num} length (ft)',
                           x=lx + 2, y=y - row_h + 2,
                           width=col_w - 8, height=row_h - 4,
                           fontName='Helvetica', fontSize=8,
                           borderColor=None, fillColor=None,
                           textColor=HexColor('#111'), forceBorder=False)

        y -= row_h + 2

    y -= 0.15*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y,
                   'Additional details, wire size, or drum specs. Questions? Email orders@harborspecmarine.com',
                   'notes', height=0.45*inch, multiline=True)

    # Calculator callout box
    c.setFillColor(HexColor('#eaf2f8'))
    c.setStrokeColor(HexColor('#b0cde0'))
    c.setLineWidth(0.75)
    box_y = y - 0.55*inch
    c.roundRect(0.5*inch, box_y, PAGE_W - inch, 0.45*inch, 4, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(0.65*inch, box_y + 0.28*inch, 'ℹ  Wire Length Calculator:')
    c.setFont('Helvetica', 8)
    c.drawString(0.65*inch, box_y + 0.13*inch,
        'harborspecmarine.com/wire-calculator.html  —  or email orders@harborspecmarine.com for help')
    draw_footer(c, invoice_num, 1, 1)


def sheet_compass_frame(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Compass Card Frame', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'No text is required for the compass frame — just confirm your vessel name and color preference.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name (for our records)', 'vessel_name')
    y = draw_field(c, acro, y, 'Color (confirm or change from order)', 'color',
                   value=item.get('color', ''))
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Any additional requests', 'notes', height=0.75*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_custom_plaque(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Custom Plaque', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Enter all text exactly as you want it to appear. Include line breaks where needed.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name (for our records)', 'vessel_name')
    y -= 0.05*inch
    y = draw_section_title(c, y, 'PLAQUE CONTENT')
    y = draw_field(c, acro, y,
                   'Enter all text for the plaque — title, body text, line by line as you want it',
                   'plaque_text', height=3.0*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'LAYOUT NOTES (optional)')
    y = draw_field(c, acro, y,
                   'Any specific layout instructions, font size preferences, or emphasis notes',
                   'layout_notes', height=0.75*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_wall_plate(c, acro, item, invoice_num, order_date):
    """Wall plates — single, 2-gang, 3-gang, 4-gang, outlet covers."""
    name = item.get('name', '')
    # Detect number of positions
    positions = 1
    if '2-gang' in name.lower() or '2 gang' in name.lower() or 'double' in name.lower():
        positions = 2
    elif '3-gang' in name.lower() or '3 gang' in name.lower():
        positions = 3
    elif '4-gang' in name.lower() or '4 gang' in name.lower():
        positions = 4

    draw_header(c, invoice_num, name, order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Provide the plate title and a circuit label for each switch/outlet position.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name (for our records)', 'vessel_name')
    y -= 0.05*inch
    y = draw_section_title(c, y, 'PLATE LABELS')
    y = draw_field(c, acro, y, 'Plate Title (appears at top of plate)', 'plate_title',
                   value=item.get('textType','') if item.get('textType','') not in ('standard','custom') else '')
    y -= 0.05*inch
    for i in range(1, positions + 1):
        y = draw_field(c, acro, y, f'Position {i} — Circuit Label', f'circuit_{i}')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Cutout type, any special requests', 'notes',
                   height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_multi_switch(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Multi-Switch Panel', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'List switch labels in order — left column top to bottom, then right column top to bottom.')
    y = draw_section_title(c, y, 'VESSEL & PANEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y = draw_two_fields(c, acro, y, 'Panel Title (top banner)', 'panel_title',
                        'Panel Footer (bottom banner, e.g. OFF / ON)', 'panel_footer')
    y = draw_two_fields(c, acro, y, 'Panel Width (inches)', 'panel_width',
                        'Panel Height (inches)', 'panel_height')
    y -= 0.05*inch
    y = draw_section_title(c, y, 'SWITCH LABELS (in order)')
    # 14 positions in two columns
    col_labels = ['LEFT COLUMN (top to bottom)', 'RIGHT COLUMN (top to bottom)']
    positions_per_col = 7
    col_w = (PAGE_W - inch - 0.2*inch) / 2
    for col in range(2):
        cx = 0.5*inch + col * (col_w + 0.2*inch)
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(cx, y, col_labels[col])
        cy = y - 0.15*inch
        for pos in range(1, positions_per_col + 1):
            field_num = pos + col * positions_per_col
            # Label
            c.setFillColor(HexColor('#333'))
            c.setFont('Helvetica', 7.5)
            c.drawString(cx, cy - 0.01*inch, f'{field_num}.')
            # Field
            c.setFillColor(HexColor('#f9f9f9'))
            c.setStrokeColor(HexColor('#cccccc'))
            c.setLineWidth(0.5)
            c.rect(cx + 0.18*inch, cy - 0.22*inch, col_w - 0.22*inch, 0.22*inch, fill=1, stroke=1)
            acro.textfield(name=f'switch_{field_num}',
                           tooltip=f'Switch {field_num} label',
                           x=cx + 0.20*inch, y=cy - 0.20*inch,
                           width=col_w - 0.28*inch, height=0.18*inch,
                           fontName='Helvetica', fontSize=8,
                           borderColor=None, fillColor=None,
                           textColor=HexColor('#111'), forceBorder=False)
            cy -= 0.3*inch
    y = min(y - positions_per_col * 0.3*inch - 0.3*inch,
            y - positions_per_col * 0.3*inch - 0.3*inch)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional details or special requests',
                   'notes', height=0.5*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_dust_cover(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Custom Dust Cover', order_date)
    y = PAGE_H - 1.65*inch
    measurements = item.get('measurements', item.get('textType', ''))
    y = draw_instructions(c, y,
        'Measurements were captured at checkout. Please confirm below and provide vessel name for labeling.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y = draw_field(c, acro, y, 'Confirm Dimensions (L × W × D in inches)',
                   'dimensions', value=measurements)
    y = draw_field(c, acro, y,
                   'Equipment being covered (e.g. engine controls, throttle, electronics panel)',
                   'equipment', height=0.6*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional requests', 'notes', height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_generic(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, item.get('name', 'Custom Product'), order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y, 'Please provide vessel information and any custom text for this product.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'CUSTOM TEXT / DETAILS')
    y = draw_field(c, acro, y, 'Enter all text or details needed for this product',
                   'custom_text', height=2.5*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional requests', 'notes', height=0.75*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_emergency_contacts(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Emergency Contacts', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Provide the contact numbers for your vessel. We will engrave them permanently into the plaque.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'CONTACT NUMBERS')
    y = draw_field(c, acro, y, 'USCG Sector (name and number)', 'uscg_sector')
    y = draw_field(c, acro, y, 'VTS (Vessel Traffic Service)', 'vts')
    y = draw_field(c, acro, y, 'Designated Person Ashore (name and number)', 'dpa')
    y = draw_field(c, acro, y, 'Port Captain (name and number)', 'port_captain')
    y = draw_field(c, acro, y, '24 Hour Dispatch', 'dispatch')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES (optional)')
    y = draw_field(c, acro, y, 'Additional contacts or special instructions',
                   'notes', height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_standing_orders(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, "Master's Standing Orders", order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Enter your standing orders exactly as you want them to appear. We will format and lay out the plaque.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.05*inch
    y = draw_section_title(c, y, 'STANDING ORDERS TEXT')
    c.setFillColor(HexColor('#f0f4f8'))
    c.setStrokeColor(HexColor('#b0cde0'))
    c.setLineWidth(0.5)
    ref_h = 1.55*inch
    ref_y = y - ref_h
    c.roundRect(0.5*inch, ref_y, PAGE_W - inch, ref_h, 4, fill=1, stroke=1)
    c.setFillColor(HexColor('#2e4a62'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(0.65*inch, y - 0.18*inch, 'STANDARD FORMAT (for reference):')
    std_lines = [
        'NOTIFY CAPTAIN IMMEDIATELY IN THE FOLLOWING SITUATIONS:',
        '1. Restricted visibility is encountered or expected',
        '2. Traffic conditions or other vessels cause concern',
        '3. Difficulty maintaining course or speed',
        '4. Heavy weather or possibility of damage',
        '5. Problem with engines, steering or nav equipment',
        '6. Vessel meets any hazard to navigation',
        '7. Unexpected change in orders affecting voyage plan',
        '8. Any emergency or situation of doubt',
    ]
    c.setFont('Helvetica', 6.8)
    for li, line in enumerate(std_lines):
        c.drawString(0.65*inch, y - 0.33*inch - li * 0.125*inch, line)
    y = ref_y - 0.15*inch
    y = draw_field(c, acro, y,
                   'Enter your complete standing orders (or confirm standard format above)',
                   'orders_text', height=1.8*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


# ── Sheet dispatcher ───────────────────────────────────────────────────────────
SHEET_BUILDERS = {
    'pilot_card':           sheet_pilot_card,
    'steering_procedures':  sheet_steering_procedures,
    'loss_of_steering':     sheet_loss_of_steering,
    'bnwas':                sheet_bnwas,
    'tow_wire':             sheet_tow_wire,
    'compass_frame':        sheet_compass_frame,
    'custom_plaque':        sheet_custom_plaque,
    'wall_plate':           sheet_wall_plate,
    'multi_switch':         sheet_multi_switch,
    'dust_cover':           sheet_dust_cover,
    'generic':              sheet_generic,
    'emergency_contacts':   sheet_emergency_contacts,
    'standing_orders':      sheet_standing_orders,
}


def generate_info_sheet(item, invoice_num, output_path):
    """
    Generate a fillable PDF info sheet for a single order item.
    Returns the output_path on success.
    """
    product_type = detect_product_type(item.get('name', ''))
    builder      = SHEET_BUILDERS.get(product_type, sheet_generic)
    order_date   = datetime.now().strftime('%B %d, %Y')

    c    = canvas.Canvas(output_path, pagesize=letter)
    acro = c.acroForm

    c.setTitle(f'HarborSPEC Info Sheet — {item.get("name", "")} — {invoice_num}')
    c.setAuthor('HarborSPEC')

    # White page background
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    builder(c, acro, item, invoice_num, order_date)

    c.save()
    print(f'  Info sheet: {output_path}')
    return output_path


def generate_all_info_sheets(order, invoice_num, output_dir='/tmp'):
    """
    Generate one info sheet PDF per line item in the order.
    Returns list of (item_name, pdf_path) tuples.
    """
    sheets = []
    items  = order.get('items', [])

    for idx, item in enumerate(items):
        # Skip fixed-text safety placards — no customer input needed
        if detect_product_type(item.get('name', '')) == 'safety_fixed':
            continue
        safe_name = item.get('name', f'item_{idx}').replace(' ', '_').replace('/', '-')[:40]
        filename  = f'infosheet_{invoice_num}_{idx+1}_{safe_name}.pdf'
        path      = os.path.join(output_dir, filename)
        try:
            generate_info_sheet(item, invoice_num, path)
            sheets.append((item.get('name', 'Product'), path))
        except Exception as e:
            print(f'  Info sheet error for {item.get("name")}: {e}')

    return sheets
