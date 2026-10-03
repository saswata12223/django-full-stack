import os
import urllib.request
from io import BytesIO
from datetime import date
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

from .smart_spending import generate_smart_insights
from .spending_experiment import get_experiment_context
from .spending_dna import generate_spending_dna

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
    styles.add(ParagraphStyle(name='CustomTitle', fontName='Roboto-Bold', fontSize=24, textColor=colors.HexColor('#2563EB'), spaceAfter=20))
    styles.add(ParagraphStyle(name='CustomHeading1', fontName='Roboto-Bold', fontSize=16, textColor=colors.HexColor('#0F172A'), spaceAfter=10, spaceBefore=20))
    styles.add(ParagraphStyle(name='CustomHeading2', fontName='Roboto-Bold', fontSize=12, textColor=colors.HexColor('#0F172A'), spaceAfter=6, spaceBefore=10))
    styles.add(ParagraphStyle(name='CustomBody', fontName='Roboto', fontSize=10, textColor=colors.HexColor('#334155'), spaceAfter=6, leading=14))
    styles.add(ParagraphStyle(name='CustomMutedBody', fontName='Roboto', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=6))
    
    elements = []

    # Gather data securely scoped to `user`
    insights_data = generate_smart_insights(user)
    experiment_data = get_experiment_context(user)
    dna_data = generate_spending_dna(user)

    is_empty = insights_data.get('is_empty', True)
    summary = insights_data.get('summary', {})
    insights = insights_data.get('insights', [])
    breakdown = insights_data.get('breakdown', [])
    recent_expenses = insights_data.get('recent_expenses', [])

    # Header
    elements.append(Paragraph("DHANTRACK", styles['CustomTitle']))
    elements.append(Paragraph("Comprehensive Financial Audit", styles['CustomHeading1']))
    elements.append(Paragraph(f"<b>Analysis period:</b> {summary.get('period', 'Current Month')}", styles['CustomBody']))
    elements.append(Paragraph(f"<b>Generated:</b> {date.today().strftime('%B %d, %Y')}", styles['CustomBody']))
    elements.append(Paragraph(f"<b>User:</b> {user.username}", styles['CustomBody']))
    elements.append(Spacer(1, 20))

    if is_empty:
        elements.append(Paragraph("1. FINANCIAL SNAPSHOT", styles['CustomHeading1']))
        data = [
            ['Total Income', '₹0.00'],
            ['Total Expenses', '₹0.00'],
            ['Current Balance', '₹0.00'],
        ]
        t = Table(data, colWidths=[200, 150])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("No financial activity has been recorded yet.", styles['CustomMutedBody']))
        doc.build(elements)
        return

    # 1. FINANCIAL SNAPSHOT
    elements.append(Paragraph("1. FINANCIAL SNAPSHOT", styles['CustomHeading1']))
    
    data = [
        ['Total Income', format_currency(summary.get('income', 0))],
        ['Total Expenses', format_currency(summary.get('expenses', 0))],
        ['Current Balance', format_currency(summary.get('balance', 0))],
    ]
    t = Table(data, colWidths=[250, 150])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'Roboto', 11),
        ('FONT', (1,0), (1,-1), 'Roboto-Bold', 11),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # 2. SPENDING BREAKDOWN
    elements.append(Paragraph("2. SPENDING BREAKDOWN", styles['CustomHeading1']))
    if breakdown:
        data = [['Category', 'Total Spent', 'Share', 'Tx Count']]
        for item in breakdown:
            data.append([
                item['category'], 
                format_currency(item['amount']), 
                f"{float(item['percentage']):.1f}%",
                "" # Will fill from DNA if available, but breakdown alone doesn't have count. DNA has it.
            ])
        
        # Merge Tx Count from DNA if possible
        if dna_data and 'category_behavior' in dna_data:
            cat_counts = {cat['category']: cat['count'] for cat in dna_data['category_behavior']}
            for i, row in enumerate(data[1:], start=1):
                data[i][3] = str(cat_counts.get(row[0], '-'))

        t = Table(data, colWidths=[180, 100, 70, 70])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Bold', 10),
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("Insufficient recorded data for this analysis.", styles['CustomMutedBody']))
    
    elements.append(Spacer(1, 15))

    # 3. SMART INSIGHTS
    elements.append(Paragraph("3. SMART INSIGHTS", styles['CustomHeading1']))
    if insights:
        for insight in insights:
            elements.append(Paragraph(f"{insight.get('title')}", styles['CustomHeading2']))
            text = insight.get('explanation', '')
            if insight.get('value'):
                text += f" <b>{insight.get('value')}</b>"
            elements.append(Paragraph(text, styles['CustomBody']))
    else:
        elements.append(Paragraph("Insufficient recorded data for this analysis.", styles['CustomMutedBody']))
    
    elements.append(Spacer(1, 15))

    # 4. SPENDING DNA
    elements.append(Paragraph("4. SPENDING DNA", styles['CustomHeading1']))
    if dna_data and 'summary' in dna_data:
        d_sum = dna_data['summary']
        data = [
            ['Total transactions', str(d_sum.get('total_transactions', 0))],
            ['Average transaction', format_currency(d_sum.get('average_transaction', 0))],
            ['Largest transaction', format_currency(d_sum.get('largest_transaction', 0))],
            ['Categories used', str(d_sum.get('categories_used', 0))],
        ]
        t = Table(data, colWidths=[200, 150])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), 'Roboto', 10),
            ('FONT', (1,0), (1,-1), 'Roboto-Bold', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("Insufficient recorded data for this analysis.", styles['CustomMutedBody']))

    elements.append(Spacer(1, 15))

    # 5. SPENDING PATTERNS
    elements.append(Paragraph("5. SPENDING PATTERNS", styles['CustomHeading1']))
    if dna_data:
        # Micro Outflows
        if dna_data.get('money_leak'):
            leak = dna_data['money_leak']
            elements.append(Paragraph("Small Purchases / Money Leak", styles['CustomHeading2']))
            elements.append(Paragraph(f"{leak['count']} purchases under {format_currency(leak['limit'])}. Totaling {format_currency(leak['total'])} ({leak['share_percentage']}% of spending).", styles['CustomBody']))
        
        # Repeat Spending
        if dna_data.get('repeated_spending'):
            elements.append(Paragraph("Repeat Spending", styles['CustomHeading2']))
            for rep in dna_data['repeated_spending'][:3]:
                elements.append(Paragraph(f"• {rep['description']}: {rep['count']} tx totaling {format_currency(rep['total'])} ({format_currency(rep['average'])} avg)", styles['CustomBody']))
        
        # Large Transaction
        if dna_data.get('large_transaction'):
            large = dna_data['large_transaction']
            elements.append(Paragraph("Large Transaction", styles['CustomHeading2']))
            elements.append(Paragraph(f"{format_currency(large['amount'])} in {large['category']} ({large['multiple']}x average)", styles['CustomBody']))
            
        # Weekday vs Weekend
        if dna_data.get('weekend_pattern'):
            wp = dna_data['weekend_pattern']
            elements.append(Paragraph("Weekday vs Weekend", styles['CustomHeading2']))
            elements.append(Paragraph(f"Weekdays: {format_currency(wp['weekday_total'])} ({wp['weekday_count']} tx)", styles['CustomBody']))
            elements.append(Paragraph(f"Weekends: {format_currency(wp['weekend_total'])} ({wp['weekend_count']} tx)", styles['CustomBody']))
    else:
        elements.append(Paragraph("Insufficient recorded data for this analysis.", styles['CustomMutedBody']))

    elements.append(Spacer(1, 15))

    # 6. SPENDING EXPERIMENT
    elements.append(Paragraph("6. SPENDING EXPERIMENT", styles['CustomHeading1']))
    if experiment_data and experiment_data.get('has_active'):
        exp = experiment_data['experiment']
        data = [
            ['Category', exp.category],
            ['Target', format_currency(exp.target_amount)],
            ['Current Spending', format_currency(experiment_data.get('current_spending', 0))],
            ['Status', 'Target Exceeded' if experiment_data.get('is_exceeded') else f"Remaining: {format_currency(experiment_data.get('remaining', 0))}"],
            ['Progress', f"{float(experiment_data.get('progress_raw', 0)):.1f}%"],
            ['Days Remaining', str(experiment_data.get('days_remaining', 0))],
        ]
        t = Table(data, colWidths=[150, 200])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), 'Roboto', 10),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No active spending experiment.", styles['CustomMutedBody']))
        
    elements.append(Spacer(1, 15))

    # 7. RECENT ACTIVITY
    elements.append(Paragraph("7. RECENT ACTIVITY", styles['CustomHeading1']))
    if recent_expenses:
        data = [['Date', 'Description', 'Category', 'Amount']]
        for exp in recent_expenses[:15]:
            data.append([
                exp.date.strftime("%Y-%m-%d"),
                exp.description[:30],
                exp.category,
                format_currency(exp.amount)
            ])
        t = Table(data, colWidths=[70, 150, 120, 80])
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Bold', 10),
            ('FONT', (0,1), (-1,-1), 'Roboto', 9),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No recent activity.", styles['CustomMutedBody']))

    # Generate PDF
    doc.build(elements)
