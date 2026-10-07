import datetime
from dateutil.relativedelta import relativedelta
from expenses.models import RecurringTransaction

def calculate_occurrences(recurring_record: RecurringTransaction, start_range: datetime.date, end_range: datetime.date):
    """
    Calculates expected occurrences of a RecurringTransaction within a given date range.
    Returns a list of dicts with occurrence details.
    """
    occurrences = []
    
    if not recurring_record.is_active:
        return occurrences

    # We will generate occurrences starting from start_date up to end_range.
    current_date = recurring_record.start_date
    
    while current_date <= end_range:
        if recurring_record.end_date and current_date > recurring_record.end_date:
            break
            
        if current_date >= start_range:
            occurrences.append({
                'id': f"req_{recurring_record.pk}_{current_date.strftime('%Y%m%d')}",
                'date': current_date,
                'type': recurring_record.transaction_type,
                'amount': recurring_record.amount,
                'category': recurring_record.category,
                'description': recurring_record.description,
                'is_actual': False,
            })
            
        # Advance current_date
        if recurring_record.frequency == 'Weekly':
            current_date += relativedelta(weeks=1)
        elif recurring_record.frequency == 'Monthly':
            current_date += relativedelta(months=1)
        elif recurring_record.frequency == 'Quarterly':
            current_date += relativedelta(months=3)
        elif recurring_record.frequency == 'Yearly':
            current_date += relativedelta(years=1)
        else:
            break # Failsafe

    return occurrences

def get_expected_transactions(user, start_range: datetime.date, end_range: datetime.date):
    """
    Get all expected transactions for a user within a given date range.
    """
    expected = []
    active_recurring = RecurringTransaction.objects.filter(user=user, is_active=True)
    
    for rec in active_recurring:
        expected.extend(calculate_occurrences(rec, start_range, end_range))
        
    return sorted(expected, key=lambda x: x['date'])
