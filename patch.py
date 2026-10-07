import re

with open(r'c:\Users\souvi\OneDrive\Desktop\django-full-stack\expenses\services\audit_pdf.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Colors
content = content.replace(\"'#2563EB'\", \"'#DDA751'\") # Title -> Gold
content = content.replace(\"'#0F172A'\", \"'#FFFFFF'\") # Headings/Text -> White
content = content.replace(\"'#334155'\", \"'#D4D4D8'\") # Body -> Light Grey
content = content.replace(\"'#64748B'\", \"'#A1A1AA'\") # Muted -> Grey
content = content.replace(\"'#E2E8F0'\", \"'#2A2A2D'\") # Borders -> Dark Border

# Add Image import
content = content.replace('from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle', 'from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image')

# Inject logo
header_code = \"\"\"
    # Header
    logo_path = os.path.join(settings.BASE_DIR, 'expenses', 'static', 'expenses', 'images', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2*inch, height=0.5*inch, kind='proportional')
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 10))
\"\"\"
content = re.sub(r'# Header\s*elements\.append\(Paragraph\(\"MONEYMITRA\".*?\)\)', header_code, content, flags=re.DOTALL)

# Inject background callback
bg_code = \"\"\"
def draw_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#030405'))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.restoreState()

def generate_audit_pdf(user, output_stream):
\"\"\"
content = content.replace(\"def generate_audit_pdf(user, output_stream):\", bg_code)

# Update doc.build
build_code = \"\"\"
    if rep['expense_count'] == 0 and rep['income_count'] == 0:
        elements.append(Paragraph("1. ACTUAL MONEY", styles['CustomHeading1']))
        elements.append(Paragraph("No financial activity has been recorded yet.", styles['CustomMutedBody']))
        doc.build(elements, onFirstPage=draw_bg, onLaterPages=draw_bg)
        return
\"\"\"
content = re.sub(r\"if rep\['expense_count'\].*?return\", build_code.strip(), content, flags=re.DOTALL)

content = content.replace(\"doc.build(elements)\", \"doc.build(elements, onFirstPage=draw_bg, onLaterPages=draw_bg)\")

with open(r'c:\Users\souvi\OneDrive\Desktop\django-full-stack\expenses\services\audit_pdf.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(\"Patched!\")
