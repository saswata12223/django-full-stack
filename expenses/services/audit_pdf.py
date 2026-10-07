import os
import urllib.request
from io import BytesIO
from datetime import date
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

from .smart_spending import generate_smart_insights
from .spending_experiment import get_experiment_context
from .spending_dna import generate_spending_dna
from .reports import get_report_data

def _ensure_font():
    """Downloads and registers Roboto font to support the Rupee symbol (₹)."""
    font_dir = os.path.join(settings.BASE_DIR, 'expenses', 'static', 'fonts')
    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, 'Roboto-Regular.ttf')
    bold_font_path = os.path.join(font_dir, 'Roboto-Bold.ttf')

    if not os.path.exists(font_path):
        url = 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf'
        urllib.request.urlretrieve(url, font_path)
    if not os.path.exists(bold_font_path):
        url_bold = 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf'
        urllib.request.urlretrieve(url_bold, bold_font_path)

    pdfmetrics.registerFont(TTFont('Roboto', font_path))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', bold_font_path))
    pdfmetrics.registerFontFamily('Roboto', normal='Roboto', bold='Roboto-Bold')

def format_currency(value):
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return f"₹0.00"

def generate_audit_pdf(user, output_stream):
    """Generates a PDF audit report for the given user, saving to output_stream."""
    _ensure_font()

    doc = SimpleDocTemplate(
        output_stream,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CustomTitle', fontName='Roboto-Bold', fontSize=26, textColor=colors.HexColor('#DDA751'), spaceAfter=20))
    styles.add(ParagraphStyle(name='CustomHeading1', fontName='Roboto-Bold', fontSize=16, textColor=colors.HexColor('#111827'), spaceAfter=10, spaceBefore=20))
    styles.add(ParagraphStyle(name='CustomHeading2', fontName='Roboto-Bold', fontSize=12, textColor=colors.HexColor('#111827'), spaceAfter=6, spaceBefore=10))
    styles.add(ParagraphStyle(name='CustomBody', fontName='Roboto', fontSize=10, textColor=colors.HexColor('#374151'), spaceAfter=6, leading=14))
    styles.add(ParagraphStyle(name='CustomMutedBody', fontName='Roboto', fontSize=9, textColor=colors.HexColor('#6B7280'), spaceAfter=6))
    
    elements = []

    # Gather data securely scoped to `user`
    rep = get_report_data(user, 'current_month')

    # Header
    elements.append(Paragraph("Money<font color='#111827'>Mitra</font>", styles['CustomTitle']))
        
    elements.append(Paragraph("Comprehensive Financial Audit", styles['CustomHeading1']))
    elements.append(Paragraph(f"<b>Reporting period:</b> {rep['period_label']} ({rep['start_date'].strftime('%b %d, %Y')} - {rep['end_date'].strftime('%b %d, %Y')})", styles['CustomBody']))
    elements.append(Paragraph(f"<b>Generated:</b> {date.today().strftime('%B %d, %Y')}", styles['CustomBody']))
    elements.append(Paragraph(f"<b>User:</b> {user.username}", styles['CustomBody']))
    elements.append(Spacer(1, 20))

    if rep['expense_count'] == 0 and rep['income_count'] == 0:
        elements.append(Paragraph("1. ACTUAL MONEY", styles['CustomHeading1']))
        elements.append(Paragraph("No financial activity has been recorded yet.", styles['CustomMutedBody']))
        doc.build(elements)
        return

    # 1. ACTUAL MONEY
    elements.append(Paragraph("1. ACTUAL MONEY", styles['CustomHeading1']))
    
    data = [
        ['Total Income', format_currency(rep['total_income'])],
        ['Total Expenses', format_currency(rep['total_expense'])],
        ['Net Cash Flow', format_currency(rep['net_cash_flow'])],
    ]
    t = Table(data, colWidths=[250, 150])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'Roboto', 11),
        ('FONT', (1,0), (1,-1), 'Roboto-Bold', 11),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor('#DDA751')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # 2. EXPENSE CATEGORY BREAKDOWN
    elements.append(Paragraph("2. EXPENSE CATEGORY BREAKDOWN", styles['CustomHeading1']))
    if rep['category_breakdown']:
        data = [['Category', 'Total Spent', 'Share']]
        for item in rep['category_breakdown']:
            data.append([
                item['category'], 
                format_currency(item['amount']), 
                f"{float(item['percentage']):.1f}%"
            ])

        t = Table(data, colWidths=[180, 100, 70])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Bold', 10),
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F9FAFB')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#DDA751')),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No expense data for this period.", styles['CustomMutedBody']))
    
    elements.append(Spacer(1, 15))

    # 3. EXPENSE INTENT BREAKDOWN
    elements.append(Paragraph("3. EXPENSE INTENT BREAKDOWN", styles['CustomHeading1']))
    if rep['intent_breakdown']:
        data = [['Intent', 'Total Spent', 'Share']]
        for item in rep['intent_breakdown']:
            data.append([
                item['intent'], 
                format_currency(item['amount']), 
                f"{float(item['percentage']):.1f}%"
            ])

        t = Table(data, colWidths=[180, 100, 70])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Bold', 10),
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F9FAFB')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#DDA751')),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No expense intent data for this period.", styles['CustomMutedBody']))
    
    elements.append(Spacer(1, 15))

    # 4. INCOME TYPE BREAKDOWN
    elements.append(Paragraph("4. INCOME TYPE BREAKDOWN", styles['CustomHeading1']))
    if rep['income_type_breakdown']:
        data = [['Income Type', 'Total Received', 'Share']]
        for item in rep['income_type_breakdown']:
            data.append([
                item['income_type'], 
                format_currency(item['amount']), 
                f"{float(item['percentage']):.1f}%"
            ])

        t = Table(data, colWidths=[180, 100, 70])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Bold', 10),
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F9FAFB')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#DDA751')),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No income type data for this period.", styles['CustomMutedBody']))
    
    elements.append(Spacer(1, 15))
    
    # 5. LARGEST EXPENSE
    elements.append(Paragraph("5. LARGEST EXPENSE", styles['CustomHeading1']))
    if rep['largest_expense']:
        le = rep['largest_expense']
        elements.append(Paragraph(f"{format_currency(le.amount)} for '{le.description}' on {le.date.strftime('%B %d, %Y')} (Category: {le.category}, Intent: {le.intent})", styles['CustomBody']))
    else:
        elements.append(Paragraph("No expenses recorded.", styles['CustomMutedBody']))
        
    elements.append(Spacer(1, 15))

    # 6. EXPECTED / PLANNED RECURRING MONEY
    elements.append(Paragraph("6. EXPECTED / PLANNED", styles['CustomHeading1']))
    elements.append(Paragraph("Expected recurring cash flow based on active recurring rules:", styles['CustomBody']))
    rsum = rep['recurring_summary']
    data = [
        ['Expected Monthly Inflow', format_currency(rsum['expected_monthly_inflow'])],
        ['Expected Monthly Outflow', format_currency(rsum['expected_monthly_outflow'])],
    ]
    t = Table(data, colWidths=[250, 150])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'Roboto', 10),
        ('FONT', (1,0), (1,-1), 'Roboto-Bold', 10),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # 7. TARGET (GOALS)
    elements.append(Paragraph("7. TARGETS (GOALS)", styles['CustomHeading1']))
    gsum = rep['goals_summary']
    if gsum['active_count'] > 0 or gsum['completed_count'] > 0:
        data = [
            ['Active Goals', str(gsum['active_count'])],
            ['Total Target Amount', format_currency(gsum['total_target'])],
            ['Total Accumulated', format_currency(gsum['total_current'])],
        ]
        t = Table(data, colWidths=[250, 150])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), 'Roboto', 10),
            ('FONT', (1,0), (1,-1), 'Roboto-Bold', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#111827')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No active or completed goals.", styles['CustomMutedBody']))
        
    elements.append(Spacer(1, 15))
    
    # 8. FORECAST
    elements.append(Paragraph("8. PROJECTED (FORECAST)", styles['CustomHeading1']))
    elements.append(Paragraph("To see your expected trajectory, please visit the Forecast timeline view within your dashboard.", styles['CustomBody']))

    # Generate PDF
    doc.build(elements)
