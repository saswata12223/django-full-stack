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

    # Category Breakdown
    cat_breakdown = curr_expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    breakdown_list = []
    for cb in cat_breakdown:
        pct = (cb['total'] / total_curr_expense) * Decimal('100.00') if total_curr_expense > Decimal('0') else Decimal('0')
        breakdown_list.append({
            'category': cb['category'],
            'amount': cb['total'],
            'percentage': pct
        })
        
    if breakdown_list:
        top_cat = breakdown_list[0]
        insights.append({
            'title': 'Largest Spending Category',
            'icon': '💡',
            'explanation': f"{top_cat['category']} is currently your largest expense category. Reviewing your recent {top_cat['category'].lower()} expenses may help identify opportunities to reduce unnecessary spending.",
            'value': f"₹{top_cat['amount']} ({top_cat['percentage']:.1f}%)",
            'type': 'info'
        })
        
        # High spending categories
        for cat in breakdown_list:
            if cat['percentage'] >= 30 and cat['category'] != top_cat['category']:
                insights.append({
                    'title': 'Spending Pattern',
                    'icon': '🎯',
                    'explanation': f"{cat['category']} represents {cat['percentage']:.0f}% of your recorded expenses this month. Reviewing recent transactions can help identify recurring purchases.",
                    'type': 'warning'
                })

    # Income vs Expenses
    if total_curr_income > total_curr_expense:
        insights.append({
            'title': 'Income vs Expenses',
            'icon': '✅',
            'explanation': "Your recorded income currently exceeds your recorded expenses.",
            'type': 'success'
        })
        insights.append({
            'title': 'Savings Tip',
            'icon': '💰',
            'explanation': "Your recorded income is currently higher than your expenses. You could consider setting aside part of the remaining amount toward a financial goal.",
            'type': 'success'
        })
    elif total_curr_expense > total_curr_income:
        insights.append({
            'title': 'Income vs Expenses',
            'icon': '⚠️',
            'explanation': "Your recorded expenses currently exceed your recorded income.",
            'type': 'warning'
        })
    elif total_curr_income == total_curr_expense and total_curr_income > 0:
        insights.append({
            'title': 'Income vs Expenses',
            'icon': '⚖️',
            'explanation': "Your recorded income and expenses are currently equal.",
            'type': 'info'
        })
        
    # Recent Spending Activity
    recent_exps = Expense.objects.filter(user=user).order_by('-date', '-created_at')[:5]
    if recent_exps.exists() and total_curr_expense > 0:
        avg_expense = total_curr_expense / Decimal(curr_expenses.count()) if curr_expenses.count() > 0 else Decimal('0')
        for exp in recent_exps:
            if avg_expense > 0 and exp.amount > (avg_expense * Decimal('3.0')): 
                insights.append({
                    'title': 'Recent Large Transaction',
                    'icon': '🔍',
                    'explanation': f"Your recent expense of ₹{exp.amount} for '{exp.description}' is one of your larger recent transactions.",
                    'type': 'info'
                })
                break 

    # limit insights
    insights = insights[:6]

    return {
        'is_empty': False,
        'summary': {
            'income': total_curr_income,
            'expenses': total_curr_expense,
            'balance': balance,
            'period': now.strftime('%B %Y')
        },
        'breakdown': breakdown_list,
        'insights': insights,
        'recent_expenses': recent_exps
    }
