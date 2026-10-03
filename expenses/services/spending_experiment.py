from decimal import Decimal
from django.db.models import Sum, Min, Max
from django.utils import timezone
from expenses.models import Expense, SpendingExperiment
import datetime

def get_experiment_context(user):
    active_exp = SpendingExperiment.objects.filter(user=user, status='ACTIVE').first()
    now = timezone.now().date()
    
    # If active experiment exists but is past end date, complete it
    if active_exp and now > active_exp.end_date:
        active_exp.status = 'COMPLETED'
        active_exp.save()
        active_exp = None
        
    if active_exp:
        # Calculate progress
        expenses = Expense.objects.filter(
            user=user,
            category=active_exp.category,
            date__gte=active_exp.start_date,
            date__lte=active_exp.end_date
        )
        current_spending = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        target = active_exp.target_amount
        if target > 0:
            progress = (current_spending / target) * Decimal('100.00')
        else:
            progress = Decimal('100.00') if current_spending > 0 else Decimal('0.00')
            
        remaining = target - current_spending
        days_remaining = (active_exp.end_date - now).days
        if days_remaining < 0:
            days_remaining = 0
            
        return {
            'has_active': True,
            'experiment': active_exp,
            'current_spending': current_spending,
            'remaining': remaining,
            'progress': min(progress, Decimal('100.00')),
            'progress_raw': progress,
            'days_remaining': days_remaining,
            'is_exceeded': current_spending > target
        }
        
    # Check if there's a recently completed one to show result
    completed_exp = SpendingExperiment.objects.filter(user=user, status='COMPLETED').order_by('-end_date').first()
    result = None
    if completed_exp and (now - completed_exp.end_date).days < 30: # show for 30 days
        actual_spending = Expense.objects.filter(
            user=user,
            category=completed_exp.category,
            date__gte=completed_exp.start_date,
            date__lte=completed_exp.end_date
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        diff_from_target = actual_spending - completed_exp.target_amount
        diff_from_baseline = actual_spending - completed_exp.baseline_amount
        
        result = {
            'experiment': completed_exp,
            'actual_spending': actual_spending,
            'diff_from_target': abs(diff_from_target),
            'target_met': diff_from_target <= 0,
            'diff_from_baseline': abs(diff_from_baseline),
            'saved_vs_baseline': diff_from_baseline < 0
        }

    # Generate averages for new experiment creation
    categories = [c[0] for c in Expense.CATEGORY_CHOICES]
    category_data = []
    
    for cat in categories:
        cat_expenses = Expense.objects.filter(user=user, category=cat)
        if not cat_expenses.exists():
            continue
            
        # calculate months of history
        earliest = cat_expenses.aggregate(Min('date'))['date__min']
        latest = cat_expenses.aggregate(Max('date'))['date__max']
        
        if earliest and latest:
            months = (latest.year - earliest.year) * 12 + (latest.month - earliest.month) + 1
            total = cat_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            avg = total / Decimal(months)
            
            label = "current month's spending" if months == 1 else f"average spending over the last {months} months"
            
            category_data.append({
                'category': cat,
                'average': avg,
                'label': label,
                'months': months
            })
            
    # Sort category data by average descending
    category_data.sort(key=lambda x: x['average'], reverse=True)

    return {
        'has_active': False,
        'completed_result': result,
        'category_data': category_data
    }

def create_experiment(user, category, reduction_pct):
    # Ensure no active exp
    if SpendingExperiment.objects.filter(user=user, status='ACTIVE').exists():
        return False
        
    cat_expenses = Expense.objects.filter(user=user, category=category)
    if not cat_expenses.exists():
        return False
        
    earliest = cat_expenses.aggregate(Min('date'))['date__min']
    latest = cat_expenses.aggregate(Max('date'))['date__max']
    months = (latest.year - earliest.year) * 12 + (latest.month - earliest.month) + 1
    total = cat_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    avg = total / Decimal(months)
    
    reduction_factor = Decimal(reduction_pct) / Decimal('100')
    target = avg * (Decimal('1') - reduction_factor)
    
    now = timezone.now().date()
    start_date = now.replace(day=1)
    
    # Calculate end of month
    if start_date.month == 12:
        end_date = start_date.replace(year=start_date.year + 1, month=1) - datetime.timedelta(days=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1) - datetime.timedelta(days=1)
        
    SpendingExperiment.objects.create(
        user=user,
        category=category,
        baseline_amount=avg,
        target_amount=target,
        start_date=start_date,
        end_date=end_date,
        status='ACTIVE'
    )
    return True

def cancel_experiment(user):
    exp = SpendingExperiment.objects.filter(user=user, status='ACTIVE').first()
    if exp:
        exp.status = 'CANCELLED'
        exp.save()
        return True
    return False
