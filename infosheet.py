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
        'Standard emergency procedures will be used unless you specify custom content below.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'TEXT PREFERENCE')
    for label, val in [('Use standard loss of steering procedures', 'standard'),
                       ('Use custom text (enter below)', 'custom')]:
        c.setFillColor(HexColor('#f9f9f9'))
        c.setStrokeColor(HexColor('#cccccc'))
        c.rect(0.5*inch, y - 0.18*inch, 0.18*inch, 0.18*inch, fill=1, stroke=1)
        acro.checkbox(name=f'choice_{val}', tooltip=label,
                      x=0.5*inch, y=y - 0.18*inch, size=0.18*inch,
                      checked=(val == 'standard'),
                      borderColor=HexColor('#cccccc'), fillColor=None)
        c.setFillColor(HexColor('#111111'))
        c.setFont('Helvetica', 8.5)
        c.drawString(0.5*inch + 0.25*inch, y - 0.13*inch, label)
        y -= 0.28*inch
    y -= 0.05*inch
    y = draw_section_title(c, y, 'CUSTOM TEXT (if applicable)')
    y = draw_field(c, acro, y, 'Enter your custom loss of steering procedures',
                   'custom_text', height=2.0*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'STEERING SYSTEM DETAILS (optional)')
    y = draw_field(c, acro, y, 'Describe your steering system (e.g. hydraulic ram, tiller arm, etc.)',
                   'steering_system', height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_bnwas(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'BNWAS Panel', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Standard BNWAS text will be used unless you need custom content.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'TEXT PREFERENCE')
    for label, val in [('Use standard BNWAS panel text', 'standard'),
                       ('Use custom text (enter below)', 'custom')]:
        c.setFillColor(HexColor('#f9f9f9'))
        c.setStrokeColor(HexColor('#cccccc'))
        c.rect(0.5*inch, y - 0.18*inch, 0.18*inch, 0.18*inch, fill=1, stroke=1)
        acro.checkbox(name=f'choice_{val}', tooltip=label,
                      x=0.5*inch, y=y - 0.18*inch, size=0.18*inch,
                      checked=(val == 'standard'),
                      borderColor=HexColor('#cccccc'), fillColor=None)
        c.setFillColor(HexColor('#111111'))
        c.setFont('Helvetica', 8.5)
        c.drawString(0.5*inch + 0.25*inch, y - 0.13*inch, label)
        y -= 0.28*inch
    y -= 0.05*inch
    y = draw_section_title(c, y, 'CUSTOM TEXT (if applicable)')
    y = draw_field(c, acro, y, 'Enter custom BNWAS panel text',
                   'custom_text', height=1.5*inch, multiline=True)
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional requests', 'notes', height=0.6*inch, multiline=True)
    draw_footer(c, invoice_num, 1, 1)


def sheet_tow_wire(c, acro, item, invoice_num, order_date):
    draw_header(c, invoice_num, 'Tow Wire / Capacities', order_date)
    y = PAGE_H - 1.65*inch
    y = draw_instructions(c, y,
        'Provide either wire layer/length data OR vessel capacity data — whichever applies to your vessel.')
    y = draw_section_title(c, y, 'VESSEL INFO')
    y = draw_field(c, acro, y, 'Vessel Name', 'vessel_name')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'WIRE LENGTH TABLE (center to center on drum)')
    c.setFillColor(HexColor('#111111'))
    c.setFont('Helvetica', 8)
    c.drawString(0.5*inch, y, 'Fill in layer/length pairs as applicable:')
    y -= 0.22*inch
    pairs = [('0.5', '1'), ('1.5', '2'), ('2.5', '3'), ('3.5', '4'),
             ('4.5', '5'), ('5.5', '6'), ('6.5', '7'), ('7.5', '8')]
    col_w = (PAGE_W - inch) / 4
    headers = ['Layer', 'Length (ft)', 'Layer', 'Length (ft)']
    for i, h in enumerate(headers):
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(NAVY)
        c.drawString(0.5*inch + i * col_w + 4, y, h)
    y -= 0.18*inch
    for row in range(4):
        for col in range(2):
            idx = row + col * 4
            if idx >= len(pairs): break
            layer_lbl, len_lbl = pairs[idx]
            bx = 0.5*inch + col * 2 * col_w
            # Layer (pre-filled label)
            c.setFillColor(HexColor('#eef2f5'))
            c.setStrokeColor(HexColor('#cccccc'))
            c.rect(bx, y - 0.22*inch, col_w - 4, 0.22*inch, fill=1, stroke=1)
            c.setFillColor(HexColor('#555'))
            c.setFont('Helvetica', 8)
            c.drawCentredString(bx + (col_w - 4)/2, y - 0.15*inch, layer_lbl)
            # Length field
            c.setFillColor(HexColor('#f9f9f9'))
            c.rect(bx + col_w, y - 0.22*inch, col_w - 4, 0.22*inch, fill=1, stroke=1)
            acro.textfield(name=f'wire_len_{layer_lbl.replace(".", "_")}',
                           tooltip=f'Layer {layer_lbl} length',
                           x=bx + col_w + 2, y=y - 0.20*inch,
                           width=col_w - 8, height=0.18*inch,
                           fontName='Helvetica', fontSize=8,
                           borderColor=None, fillColor=None,
                           textColor=HexColor('#111'), forceBorder=False)
        y -= 0.28*inch

    y -= 0.1*inch
    y = draw_section_title(c, y, 'OR — VESSEL CAPACITIES')
    y = draw_two_fields(c, acro, y, 'Fuel (gal)', 'cap_fuel', 'Water (gal)', 'cap_water')
    y = draw_two_fields(c, acro, y, 'Lube Oil (gal)', 'cap_lube', 'Other', 'cap_other')
    y -= 0.1*inch
    y = draw_section_title(c, y, 'NOTES')
    y = draw_field(c, acro, y, 'Additional details', 'notes', height=0.5*inch, multiline=True)
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
        safe_name = item.get('name', f'item_{idx}').replace(' ', '_').replace('/', '-')[:40]
        filename  = f'infosheet_{invoice_num}_{idx+1}_{safe_name}.pdf'
        path      = os.path.join(output_dir, filename)
        try:
            generate_info_sheet(item, invoice_num, path)
            sheets.append((item.get('name', 'Product'), path))
        except Exception as e:
            print(f'  Info sheet error for {item.get("name")}: {e}')

    return sheets
