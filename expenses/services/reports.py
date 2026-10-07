import datetime
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Max
from django.utils import timezone
from ..models import Expense, Income, Goal, RecurringTransaction

def get_report_data(user, period='current_month'):
    """Generates financial report aggregations scoped purely to the requested user."""
    now = timezone.now().date()
    
    if period == 'current_month':
        start_date = now.replace(day=1)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = next_month - datetime.timedelta(days=1)
        
        if start_date.month == 1:
            prev_start_date = start_date.replace(year=start_date.year - 1, month=12, day=1)
        else:
            prev_start_date = start_date.replace(month=start_date.month - 1, day=1)
        prev_end_date = start_date - datetime.timedelta(days=1)
        
    elif period == 'previous_month':
        if now.month == 1:
            start_date = now.replace(year=now.year - 1, month=12, day=1)
        else:
            start_date = now.replace(month=now.month - 1, day=1)
        end_date = now.replace(day=1) - datetime.timedelta(days=1)
        
        if start_date.month == 1:
            prev_start_date = start_date.replace(year=start_date.year - 1, month=12, day=1)
        else:
            prev_start_date = start_date.replace(month=start_date.month - 1, day=1)
        prev_end_date = start_date - datetime.timedelta(days=1)
        
    elif period == 'last_3_months':
        m = now.month - 2
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        start_date = now.replace(year=y, month=m, day=1)
        end_date = now
        
        pm = start_date.month - 3
        py = start_date.year
        if pm <= 0:
            pm += 12
            py -= 1
        prev_start_date = start_date.replace(year=py, month=pm, day=1)
        prev_end_date = start_date - datetime.timedelta(days=1)
        
    elif period == 'current_year':
        start_date = now.replace(month=1, day=1)
        end_date = now.replace(month=12, day=31)
        prev_start_date = start_date.replace(year=start_date.year - 1)
        prev_end_date = end_date.replace(year=end_date.year - 1)
        
    else: 
        period = 'current_month'
        start_date = now.replace(day=1)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = next_month - datetime.timedelta(days=1)
        
        if start_date.month == 1:
            prev_start_date = start_date.replace(year=start_date.year - 1, month=12, day=1)
        else:
            prev_start_date = start_date.replace(month=start_date.month - 1, day=1)
        prev_end_date = start_date - datetime.timedelta(days=1)
        
    # ACTUAL MONEY
    expenses = Expense.objects.filter(user=user, date__gte=start_date, date__lte=end_date)
    incomes = Income.objects.filter(user=user, date__gte=start_date, date__lte=end_date)
    
    total_expense = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_income = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    net_cash_flow = total_income - total_expense
    
    expense_count = expenses.count()
    income_count = incomes.count()
    average_expense = expenses.aggregate(Avg('amount'))['amount__avg'] or Decimal('0.00')
    largest_expense = expenses.order_by('-amount').first()
    
    # BREAKDOWNS
    categories = expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    category_breakdown = []
    for c in categories:
        pct = (c['total'] / total_expense) * 100 if total_expense > 0 else 0
        category_breakdown.append({
            'category': c['category'],
            'amount': c['total'],
            'percentage': round(pct, 1)
        })
        
    intents = expenses.values('intent').annotate(total=Sum('amount')).order_by('-total')
    intent_breakdown = []
    for i in intents:
        pct = (i['total'] / total_expense) * 100 if total_expense > 0 else 0
        intent_breakdown.append({
            'intent': i['intent'],
            'amount': i['total'],
            'percentage': round(pct, 1)
        })
        
    income_types = incomes.values('income_type').annotate(total=Sum('amount')).order_by('-total')
    income_type_breakdown = []
    for it in income_types:
        pct = (it['total'] / total_income) * 100 if total_income > 0 else 0
        income_type_breakdown.append({
            'income_type': it['income_type'],
            'amount': it['total'],
            'percentage': round(pct, 1)
        })
        
    # MONTH COMPARISON
    prev_expenses = Expense.objects.filter(user=user, date__gte=prev_start_date, date__lte=prev_end_date)
    prev_incomes = Income.objects.filter(user=user, date__gte=prev_start_date, date__lte=prev_end_date)
    
    prev_total_expense = prev_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    prev_total_income = prev_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    exp_diff = total_expense - prev_total_expense
    inc_diff = total_income - prev_total_income
    
    exp_pct_change = None
    if prev_total_expense > 0:
        exp_pct_change = (exp_diff / prev_total_expense) * 100
        
    inc_pct_change = None
    if prev_total_income > 0:
        inc_pct_change = (inc_diff / prev_total_income) * 100
        
    # TARGET: GOALS
    active_goals = Goal.objects.filter(user=user, status='Active')
    completed_goals = Goal.objects.filter(user=user, status='Completed')
    total_target = Goal.objects.filter(user=user, status__in=['Active', 'Completed']).aggregate(Sum('target_amount'))['target_amount__sum'] or Decimal('0.00')
    total_current = Goal.objects.filter(user=user, status__in=['Active', 'Completed']).aggregate(Sum('current_amount'))['current_amount__sum'] or Decimal('0.00')
    
    goals_summary = {
        'active_count': active_goals.count(),
        'completed_count': completed_goals.count(),
        'total_target': total_target,
        'total_current': total_current,
    }
    
    # EXPECTED: RECURRING
    active_recurring = RecurringTransaction.objects.filter(user=user, is_active=True)
    recurring_income_count = active_recurring.filter(transaction_type='Income').count()
    recurring_expense_count = active_recurring.filter(transaction_type='Expense').count()
    
    expected_inflow = Decimal('0.00')
    expected_outflow = Decimal('0.00')
    for rt in active_recurring:
        amt = rt.amount
        if rt.frequency == 'Daily':
            amt *= 30
        elif rt.frequency == 'Weekly':
            amt = amt * Decimal('4.33')
        elif rt.frequency == 'Yearly':
            amt = amt / Decimal('12.0')
            
        if rt.transaction_type == 'Income':
            expected_inflow += amt
        else:
            expected_outflow += amt
            
    recurring_summary = {
        'active_income_count': recurring_income_count,
        'active_expense_count': recurring_expense_count,
        'expected_monthly_inflow': expected_inflow,
        'expected_monthly_outflow': expected_outflow,
    }
    
    period_labels = {
        'current_month': 'Current Month',
        'previous_month': 'Previous Month',
        'last_3_months': 'Last 3 Months',
        'current_year': 'Current Year'
    }
    
    return {
        'period_value': period,
        'period_label': period_labels.get(period, 'Current Month'),
        'start_date': start_date,
        'end_date': end_date,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_cash_flow': net_cash_flow,
        'expense_count': expense_count,
        'income_count': income_count,
        'average_expense': average_expense,
        'largest_expense': largest_expense,
        'category_breakdown': category_breakdown,
        'intent_breakdown': intent_breakdown,
        'income_type_breakdown': income_type_breakdown,
        'prev_total_expense': prev_total_expense,
        'prev_total_income': prev_total_income,
        'exp_diff': exp_diff,
        'inc_diff': inc_diff,
        'exp_pct_change': exp_pct_change,
        'inc_pct_change': inc_pct_change,
        'goals_summary': goals_summary,
        'recurring_summary': recurring_summary,
    }
