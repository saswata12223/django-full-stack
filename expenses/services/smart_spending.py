from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from expenses.models import Expense, Income

def generate_smart_insights(user):
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    # Current month data
    curr_expenses = Expense.objects.filter(user=user, date__year=current_year, date__month=current_month)
    curr_incomes = Income.objects.filter(user=user, date__year=current_year, date__month=current_month)

    # Previous month data
    prev_expenses = Expense.objects.filter(user=user, date__year=prev_year, date__month=prev_month)

    # Aggregations
    total_curr_expense = curr_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_curr_income = curr_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_prev_expense = prev_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    balance = total_curr_income - total_curr_expense

    insights = []
    
    # Empty state logic
    has_any_expense = Expense.objects.filter(user=user).exists()
    has_any_income = Income.objects.filter(user=user).exists()

    if not has_any_expense and not has_any_income:
        return {
            'is_empty': True,
            'summary': {'income': Decimal('0'), 'expenses': Decimal('0'), 'balance': Decimal('0'), 'period': now.strftime('%B %Y')},
            'breakdown': [],
            'insights': [],
            'recent_expenses': []
        }

    # Month over Month
    if total_prev_expense == Decimal('0.00'):
        insights.append({
            'title': 'Spending Trend',
            'icon': '📈',
            'explanation': "There isn't enough previous-month data to calculate a spending trend yet.",
            'type': 'info'
        })
    else:
        diff = total_curr_expense - total_prev_expense
        pct_change = (diff / total_prev_expense) * Decimal('100.00')
        if diff > 0:
            insights.append({
                'title': 'Spending Trend',
                'icon': '📈',
                'explanation': f"Your spending increased by {pct_change:.0f}% compared with last month.",
                'type': 'warning'
            })
        elif diff < 0:
            insights.append({
                'title': 'Spending Trend',
                'icon': '📉',
                'explanation': f"Your spending decreased by {abs(pct_change):.0f}% compared with last month.",
                'type': 'success'
            })

    # Intent Breakdown
    intent_breakdown = curr_expenses.values('intent').annotate(total=Sum('amount')).order_by('-total')
    intent_list = []
    for idx, ib in enumerate(intent_breakdown, 1):
        pct = (ib['total'] / total_curr_expense) * Decimal('100.00') if total_curr_expense > Decimal('0') else Decimal('0')
        intent_name = ib['intent'] if ib['intent'] else 'Uncategorized'
        intent_list.append({
            'rank': idx,
            'intent': intent_name,
            'amount': ib['total'],
            'percentage': pct
        })

    # Category Breakdown
    cat_breakdown = curr_expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    breakdown_list = []
    for idx, cb in enumerate(cat_breakdown, 1):
        pct = (cb['total'] / total_curr_expense) * Decimal('100.00') if total_curr_expense > Decimal('0') else Decimal('0')
        breakdown_list.append({
            'rank': idx,
            'category': cb['category'],
            'amount': cb['total'],
            'percentage': pct
        })

    insights = []
    
    # Month over Month Insight
    if total_prev_expense == Decimal('0.00'):
        insights.append({
            'title': 'Spending Comparison',
            'explanation': "More history is needed for a month-over-month comparison."
        })
    else:
        diff = total_curr_expense - total_prev_expense
        pct_change = (diff / total_prev_expense) * Decimal('100.00')
        if diff > 0:
            insights.append({
                'title': 'Spending Comparison',
                'explanation': f"Spending increased by {pct_change:.0f}% compared with the previous month."
            })
        elif diff < 0:
            insights.append({
                'title': 'Spending Comparison',
                'explanation': f"Spending decreased by {abs(pct_change):.0f}% compared with the previous month."
            })
        else:
            insights.append({
                'title': 'Spending Comparison',
                'explanation': "Spending remained stable compared with the previous month."
            })

    # Category Insight
    if breakdown_list:
        top_cat = breakdown_list[0]
        insights.append({
            'title': 'Top Category',
            'explanation': f"{top_cat['category']} was your largest spending category this month, representing {top_cat['percentage']:.0f}% of your recorded spending."
        })

    # Intent Insight
    want_spending = next((i for i in intent_list if i['intent'] == 'Want'), None)
    if want_spending:
        insights.append({
            'title': 'Want-based Spending',
            'explanation': f"Want-based spending accounted for {want_spending['percentage']:.0f}% of your recorded expenses."
        })
        
    need_spending = next((i for i in intent_list if i['intent'] == 'Need'), None)
    if need_spending:
        insights.append({
            'title': 'Need-based Spending',
            'explanation': f"Need-based spending accounted for {need_spending['percentage']:.0f}% of your recorded expenses."
        })
        
    # Largest Individual Expenses
    largest_expenses = curr_expenses.order_by('-amount')[:5]

    return {
        'is_empty': False,
        'summary': {
            'income': total_curr_income,
            'expenses': total_curr_expense,
            'balance': balance,
            'period': now.strftime('%B %Y')
        },
        'breakdown': breakdown_list,
        'intent_breakdown': intent_list,
        'insights': insights,
        'largest_expenses': largest_expenses
    }
