from decimal import Decimal
from django.db.models import Sum, Count, Avg, Max, Min
from django.db.models.functions import Lower, Trim
from expenses.models import Expense

def generate_spending_dna(user):
    # Fetch all user expenses
    expenses = Expense.objects.filter(user=user)
    
    if not expenses.exists():
        return None

    total_transactions = expenses.count()
    total_spending = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    if total_spending == Decimal('0.00'):
        return None

    # 1. Summary
    average_transaction = (total_spending / Decimal(total_transactions)).quantize(Decimal('0.01'))
    largest_transaction = expenses.aggregate(Max('amount'))['amount__max']
    smallest_transaction = expenses.aggregate(Min('amount'))['amount__min']
    
    cat_stats = expenses.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    most_frequent_cat = cat_stats.order_by('-count').first()
    highest_spending_cat = cat_stats.order_by('-total').first()
    categories_used = cat_stats.count()

    # 2. Money Leak (Small Purchases)
    SMALL_PURCHASE_LIMIT = Decimal("300")
    MIN_SMALL_PURCHASE_COUNT = 5
    MIN_SMALL_PURCHASE_SHARE = Decimal("0.10")

    small_purchases = expenses.filter(amount__lte=SMALL_PURCHASE_LIMIT)
    small_count = small_purchases.count()
    small_total = small_purchases.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    money_leak = None
    if small_count >= MIN_SMALL_PURCHASE_COUNT:
        small_share = small_total / total_spending if total_spending > 0 else Decimal('0')
        if small_share >= MIN_SMALL_PURCHASE_SHARE:
            money_leak = {
                'count': small_count,
                'total': small_total,
                'average': (small_total / Decimal(small_count)).quantize(Decimal('0.01')) if small_count > 0 else Decimal('0.00'),
                'share_percentage': (small_share * Decimal('100')).quantize(Decimal('0.1')),
                'limit': SMALL_PURCHASE_LIMIT
            }

    # 3. Repeated Spending
    # Ignore blank descriptions
    repeated = expenses.exclude(description__exact='').exclude(description__isnull=True) \
        .annotate(norm_desc=Lower(Trim('description'))) \
        .values('norm_desc') \
        .annotate(count=Count('id'), total=Sum('amount')) \
        .filter(count__gt=1) \
        .order_by('-count')

    repeated_spending = []
    for rep in repeated:
        repeated_spending.append({
            'description': rep['norm_desc'].title(),
            'count': rep['count'],
            'total': rep['total'],
            'average': (rep['total'] / Decimal(rep['count'])).quantize(Decimal('0.01')) if rep['count'] > 0 else Decimal('0.00')
        })

    # 4. Large Transaction Detection
    large_transaction = None
    if total_transactions >= 5 and average_transaction > 0:
        threshold = average_transaction * Decimal('3')
        large_exp = expenses.filter(amount__gte=threshold).order_by('-date').first()
        if large_exp:
            large_transaction = {
                'category': large_exp.category,
                'amount': large_exp.amount,
                'average': average_transaction,
                'multiple': (large_exp.amount / average_transaction).quantize(Decimal('0.1')) if average_transaction > 0 else Decimal('0.0')
            }

    # 5. Category Behavior
    category_behavior = []
    for cat in cat_stats.order_by('-total'):
        percentage = ((cat['total'] / total_spending) * Decimal('100')).quantize(Decimal('0.1')) if total_spending > 0 else Decimal('0.0')
        category_behavior.append({
            'category': cat['category'],
            'total': cat['total'],
            'count': cat['count'],
            'average': (cat['total'] / Decimal(cat['count'])).quantize(Decimal('0.01')) if cat['count'] > 0 else Decimal('0.00'),
            'percentage': percentage
        })

    # 6. Weekday vs Weekend Pattern
    # Note: date.weekday() returns 0 for Mon, 6 for Sun. Weekends are 5 and 6.
    weekend_expenses = []
    weekday_expenses = []
    for exp in expenses:
        if exp.date.weekday() >= 5:
            weekend_expenses.append(exp.amount)
        else:
            weekday_expenses.append(exp.amount)

    weekend_pattern = None
    if weekend_expenses and weekday_expenses:
        weekend_total = sum(weekend_expenses)
        weekday_total = sum(weekday_expenses)
        weekend_count = len(weekend_expenses)
        weekday_count = len(weekday_expenses)
        
        weekend_avg = weekend_total / Decimal(weekend_count) if weekend_count > 0 else Decimal('0.00')
        weekday_avg = weekday_total / Decimal(weekday_count) if weekday_count > 0 else Decimal('0.00')
        
        weekend_pattern = {
            'weekend_total': weekend_total,
            'weekday_total': weekday_total,
            'weekend_count': weekend_count,
            'weekday_count': weekday_count,
            'weekend_average': weekend_avg.quantize(Decimal('0.01')),
            'weekday_average': weekday_avg.quantize(Decimal('0.01')),
            'higher': 'weekend' if weekend_total > weekday_total else 'weekday'
        }

    # 7. Historical Monthly Pattern
    monthly_data = {}
    for exp in expenses:
        key = exp.date.strftime('%Y-%m')
        if key not in monthly_data:
            monthly_data[key] = Decimal('0.00')
        monthly_data[key] += exp.amount
        
    monthly_pattern = None
    monthly_trend = None
    if len(monthly_data) > 1:
        # Sort by key to have chronological order
        sorted_months = sorted(monthly_data.keys())
        trends = []
        for m in sorted_months:
            # Parse 'YYYY-MM' back to displayable string 'Month YYYY'
            from datetime import datetime
            dt = datetime.strptime(m, '%Y-%m')
            trends.append({
                'month': dt.strftime('%B %Y'),
                'total': monthly_data[m]
            })
        monthly_pattern = trends
        
        # Calculate trend if we have at least 2 months
        if len(sorted_months) >= 2:
            current_month_total = monthly_data[sorted_months[-1]]
            
            # Average of up to 3 previous months
            previous_months = sorted_months[-4:-1] if len(sorted_months) >= 4 else sorted_months[:-1]
            prev_total = sum(monthly_data[m] for m in previous_months)
            prev_avg = prev_total / Decimal(len(previous_months))
            
            if prev_avg > 0:
                diff = current_month_total - prev_avg
                pct = ((abs(diff) / prev_avg) * Decimal('100')).quantize(Decimal('0.1'))
                if diff > 0:
                    monthly_trend = f"Your spending this month is {pct}% higher than your average of the previous {len(previous_months)} month(s)."
                elif diff < 0:
                    monthly_trend = f"Your spending this month is {pct}% lower than your average of the previous {len(previous_months)} month(s)."
                else:
                    monthly_trend = f"Your spending this month is exactly equal to your average of the previous {len(previous_months)} month(s)."

    return {
        'summary': {
            'total_transactions': total_transactions,
            'total_spending': total_spending,
            'average_transaction': average_transaction,
            'largest_transaction': largest_transaction,
            'smallest_transaction': smallest_transaction,
            'most_frequent_category': most_frequent_cat,
            'highest_spending_category': highest_spending_cat,
            'categories_used': categories_used
        },
        'money_leak': money_leak,
        'repeated_spending': repeated_spending[:5], # limit to top 5
        'large_transaction': large_transaction,
        'category_behavior': category_behavior,
        'weekend_pattern': weekend_pattern,
        'monthly_pattern': monthly_pattern,
        'monthly_trend': monthly_trend
    }
