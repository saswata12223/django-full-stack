from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Max, Avg, Count
from django.utils import timezone
from decimal import Decimal
from .models import Expense, Income, MoneyProfile, Goal, RecurringTransaction
from .forms import ExpenseForm, IncomeForm, MoneyProfileForm, GoalForm, RecurringTransactionForm
from .services.smart_spending import generate_smart_insights
from .services.recurrence import get_expected_transactions
import datetime
from dateutil.relativedelta import relativedelta

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful. Welcome!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'expenses/register.html', {'form': form})

def landing_view(request):
    # If the user is authenticated, they can still view it or we can pass a flag.
    # The template will handle the logic using `request.user.is_authenticated`.
    return render(request, 'expenses/landing.html')

@login_required
def dashboard_view(request):
    user = request.user
    if not hasattr(user, 'money_profile'):
        return redirect('profile_setup')
    expenses = Expense.objects.filter(user=user).order_by('-date')[:5]
    incomes = Income.objects.filter(user=user).order_by('-date')[:5]
    
    total_expense = Expense.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_income = Income.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    balance = total_income - total_expense
    expense_count = Expense.objects.filter(user=user).count()
    income_count = Income.objects.filter(user=user).count()

    # Current month metrics for the new UI
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_expenses = Expense.objects.filter(user=user, date__gte=month_start.date())
    month_total_expense = month_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    all_cat_totals = list(month_expenses.values('category').annotate(total=Sum('amount')).order_by('-total'))
    category_totals = all_cat_totals[:4]
    if len(all_cat_totals) > 4:
        category_totals.append({'category': 'Other', 'total': sum(c['total'] for c in all_cat_totals[4:])})
    for cat in category_totals:
        cat['percentage'] = float((cat['total'] / month_total_expense) * 100) if month_total_expense > 0 else 0.0
        
    largest_category = category_totals[0] if category_totals else None
    daily_consumption = (month_total_expense / now.day) if now.day > 0 else Decimal('0.00')
    
    # Goals and Recurring counts
    active_goals_count = Goal.objects.filter(user=user).exclude(status='Completed').count()
    active_recurring_count = RecurringTransaction.objects.filter(user=user, is_active=True).count()

    context = {
        'recent_expenses': expenses,
        'recent_incomes': incomes,
        'total_expense': total_expense,
        'total_income': total_income,
        'balance': balance,
        'expense_count': expense_count,
        'income_count': income_count,
        'category_totals': category_totals,
        'largest_category': largest_category,
        'daily_consumption': daily_consumption,
        'month_total_expense': month_total_expense,
        'active_goals_count': active_goals_count,
        'active_recurring_count': active_recurring_count,
    }
    return render(request, 'expenses/dashboard.html', context)

# --- Expense Views ---

def get_money_mode_suggestions(user):
    if not hasattr(user, 'money_profile'):
        return []
        
    mode = user.money_profile.mode
    suggestions = {
        'School Student': ['Study', 'Social', 'Personal', 'Entertainment'],
        'College Student': ['Study', 'Food', 'Travel', 'Social', 'Personal', 'Entertainment'],
        'Working Professional': ['Essential', 'Personal', 'Work', 'Social', 'Lifestyle'],
        'Freelancer': ['Personal', 'Work', 'Client', 'Business', 'Essential'],
        'Business Owner': ['Personal', 'Business', 'Operations', 'Marketing', 'Travel', 'Equipment'],
        'Family / Household': ['Household', 'Essential', 'Education', 'Healthcare', 'Personal', 'Social'],
        'Retired / Senior': ['Essential', 'Healthcare', 'Household', 'Personal', 'Leisure'],
        'Other': ['Personal', 'Essential', 'Other']
    }
    return suggestions.get(mode, [])

from django.core.paginator import Paginator

@login_required
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    
    category = request.GET.get('category')
    intent = request.GET.get('intent')
    date = request.GET.get('date')
    search = request.GET.get('search', '').strip()
    
    if category:
        expenses = expenses.filter(category=category)
    if intent:
        expenses = expenses.filter(intent=intent)
    if date:
        try:
            expenses = expenses.filter(date__startswith=date)
        except:
            pass
    if search:
        expenses = expenses.filter(Q(description__icontains=search) | Q(category__icontains=search))
        
    categories = Expense.CATEGORY_CHOICES
    intents = Expense.INTENT_CHOICES
    
    # Calculate stats for the current filtered queryset
    stats = expenses.aggregate(
        total_amount=Sum('amount'),
        largest_outflow=Max('amount'),
        average_outflow=Avg('amount'),
        total_count=Count('id')
    )
    total_amount = stats['total_amount'] or Decimal('0.00')
    largest_outflow = stats['largest_outflow'] or Decimal('0.00')
    average_outflow = stats['average_outflow'] or Decimal('0.00')
    total_count = stats['total_count'] or 0
    
    # Category Distribution
    all_cat_totals = list(expenses.values('category').annotate(total=Sum('amount')).order_by('-total'))
    category_totals = all_cat_totals[:4]
    if len(all_cat_totals) > 4:
        category_totals.append({'category': 'Other', 'total': sum(c['total'] for c in all_cat_totals[4:])})
    active_baskets = expenses.values('category').distinct().count()
    
    for cat in category_totals:
        cat['percentage'] = float((cat['total'] / total_amount) * 100) if total_amount > 0 else 0.0
        
    largest_expense = expenses.order_by('-amount').first() if largest_outflow > 0 else None
    
    # Pagination
    paginator = Paginator(expenses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    current_cycle = timezone.now().strftime("%b %Y")
    
    context = {
        'expenses': page_obj,
        'paginator': paginator,
        'categories': categories,
        'intents': intents,
        'total_amount': total_amount,
        'total_count': total_count,
        'largest_outflow': largest_outflow,
        'largest_expense': largest_expense,
        'average_outflow': average_outflow,
        'category_totals': category_totals,
        'active_baskets': active_baskets,
        'current_cycle': current_cycle,
        'search_query': search or '',
        'selected_category': category or '',
        'selected_intent': intent or '',
        'selected_date': date or '',
    }
    return render(request, 'expenses/expense_list.html', context)

@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense added successfully.')
            return redirect('expense_list')
    else:
        form = ExpenseForm()
    suggested_contexts = get_money_mode_suggestions(request.user)
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Add Expense', 'suggested_contexts': suggested_contexts})

@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('expense_list')
    else:
        form = ExpenseForm(instance=expense)
    suggested_contexts = get_money_mode_suggestions(request.user)
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Edit Expense', 'expense': expense, 'suggested_contexts': suggested_contexts})

@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('expense_list')
    return render(request, 'expenses/confirm_delete.html', {'object': expense, 'type': 'Expense', 'cancel_url': 'expense_list'})

# --- Income Views ---

@login_required
def income_list(request):
    incomes = Income.objects.filter(user=request.user).order_by('-date')
    
    search = request.GET.get('search', '').strip()
    date = request.GET.get('date')
    income_type = request.GET.get('income_type')
    
    if search:
        incomes = incomes.filter(Q(description__icontains=search) | Q(source__icontains=search))
    if income_type:
        incomes = incomes.filter(income_type=income_type)
    if date:
        try:
            incomes = incomes.filter(date__startswith=date)
        except:
            pass
            
    # Calculate stats for the current filtered queryset
    stats = incomes.aggregate(
        total_amount=Sum('amount'),
        largest_inflow=Max('amount'),
        average_inflow=Avg('amount'),
        total_count=Count('id')
    )
    total_amount = stats['total_amount'] or Decimal('0.00')
    largest_inflow = stats['largest_inflow'] or Decimal('0.00')
    average_inflow = stats['average_inflow'] or Decimal('0.00')
    total_count = stats['total_count'] or 0
    
    # Source Distribution
    all_src_totals = list(incomes.values('source').annotate(total=Sum('amount')).order_by('-total'))
    source_totals = all_src_totals[:4]
    if len(all_src_totals) > 4:
        source_totals.append({'source': 'Other', 'total': sum(s['total'] for s in all_src_totals[4:])})
    active_streams = incomes.values('source').distinct().count()
    
    for src in source_totals:
        src['percentage'] = float((src['total'] / total_amount) * 100) if total_amount > 0 else 0.0
        
    largest_income = incomes.order_by('-amount').first() if largest_inflow > 0 else None
    
    # Pagination
    paginator = Paginator(incomes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    income_types = Income.INCOME_TYPE_CHOICES

    context = {
        'incomes': page_obj,
        'paginator': paginator,
        'total_amount': total_amount,
        'total_count': total_count,
        'largest_inflow': largest_inflow,
        'largest_income': largest_income,
        'average_inflow': average_inflow,
        'source_totals': source_totals,
        'active_streams': active_streams,
        'search_query': search or '',
        'selected_date': date or '',
        'selected_income_type': income_type or '',
        'income_types': income_types,
    }
    return render(request, 'expenses/income_list.html', context)

@login_required
def income_create(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            messages.success(request, 'Income added successfully.')
            return redirect('income_list')
    else:
        form = IncomeForm()
    return render(request, 'expenses/income_form.html', {'form': form, 'title': 'Add Income'})

@login_required
def income_update(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        form = IncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, 'Income updated successfully.')
            return redirect('income_list')
    else:
        form = IncomeForm(instance=income)
    return render(request, 'expenses/income_form.html', {'form': form, 'title': 'Edit Income', 'income': income})

@login_required
def income_delete(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        income.delete()
        messages.success(request, 'Income deleted successfully.')
        return redirect('income_list')
    return render(request, 'expenses/confirm_delete.html', {'object': income, 'type': 'Income', 'cancel_url': 'income_list'})

from .services.spending_experiment import get_experiment_context, create_experiment, cancel_experiment
from .services.spending_dna import generate_spending_dna

from django.http import HttpResponse
from datetime import date
from .services.audit_pdf import generate_audit_pdf

@login_required
def download_audit_pdf(request):
    filename = f"MoneyMitra_Comprehensive_Audit_{date.today().strftime('%Y-%m-%d')}.pdf"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Generate the PDF and write directly to the response stream
    generate_audit_pdf(request.user, response)
    
    return response

# --- Smart Spending View ---

@login_required
def smart_spending_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'start_experiment':
            category = request.POST.get('category')
            reduction = request.POST.get('reduction')
            if category and reduction:
                create_experiment(request.user, category, reduction)
                messages.success(request, 'Spending experiment started successfully!')
        elif action == 'cancel_experiment':
            if cancel_experiment(request.user):
                messages.success(request, 'Experiment cancelled.')
            else:
                messages.error(request, 'No active experiment found to cancel.')
        return redirect('smart_spending')

    insights_data = generate_smart_insights(request.user)
    experiment_data = get_experiment_context(request.user)
    dna_data = generate_spending_dna(request.user)
    
    context = {**insights_data, 'experiment': experiment_data, 'dna': dna_data}
    return render(request, 'expenses/smart_spending.html', context)

@login_required
def profile_setup_view(request):
    if hasattr(request.user, 'money_profile'):
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = MoneyProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, 'Money Profile created successfully!')
            return redirect('dashboard')
    else:
        form = MoneyProfileForm()
        
    return render(request, 'expenses/profile_setup.html', {'form': form})

@login_required
def profile_view(request):
    try:
        profile = request.user.money_profile
    except MoneyProfile.DoesNotExist:
        return redirect('profile_setup')
        
    if request.method == 'POST':
        form = MoneyProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Money Profile updated successfully!')
            return redirect('profile')
    else:
        form = MoneyProfileForm(instance=profile)
        
    return render(request, 'expenses/profile.html', {'form': form, 'profile': profile})

# --- Goal Views ---

@login_required
def goal_list(request):
    goals = Goal.objects.filter(user=request.user).order_by('deadline')
    active_goals = goals.exclude(status='Completed')
    completed_goals = goals.filter(status='Completed')

    context = {
        'active_goals': active_goals,
        'completed_goals': completed_goals,
        'has_goals': goals.exists(),
    }
    return render(request, 'expenses/goal_list.html', context)

@login_required
def goal_create(request):
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, 'Goal created successfully.')
            return redirect('goal_list')
    else:
        form = GoalForm(initial={'status': 'Active'})
    return render(request, 'expenses/goal_form.html', {'form': form, 'title': 'Create Goal'})

@login_required
def goal_update(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Goal updated successfully.')
            return redirect('goal_list')
    else:
        form = GoalForm(instance=goal)
    return render(request, 'expenses/goal_form.html', {'form': form, 'title': 'Edit Goal'})

@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        goal.delete()
        messages.success(request, 'Goal deleted successfully.')
        return redirect('goal_list')
    return render(request, 'expenses/confirm_delete.html', {'object': goal, 'type': 'Goal', 'cancel_url': 'goal_list'})


# --- Recurring Money Views ---

@login_required
def recurring_list(request):
    recurring = RecurringTransaction.objects.filter(user=request.user).order_by('next_expected_date')
    incoming = recurring.filter(transaction_type='Income')
    outgoing = recurring.filter(transaction_type='Expense')

    context = {
        'incoming': incoming,
        'outgoing': outgoing,
        'has_recurring': recurring.exists(),
    }
    return render(request, 'expenses/recurring_list.html', context)

@login_required
def recurring_create(request):
    if request.method == 'POST':
        form = RecurringTransactionForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.user = request.user
            rec.save()
            messages.success(request, 'Recurring record created successfully.')
            return redirect('recurring_list')
    else:
        form = RecurringTransactionForm(initial={'is_active': True})
    return render(request, 'expenses/recurring_form.html', {'form': form, 'title': 'Create Recurring Record'})

@login_required
def recurring_update(request, pk):
    rec = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == 'POST':
        form = RecurringTransactionForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Recurring record updated successfully.')
            return redirect('recurring_list')
    else:
        form = RecurringTransactionForm(instance=rec)
    return render(request, 'expenses/recurring_form.html', {'form': form, 'title': 'Edit Recurring Record'})

@login_required
def recurring_delete(request, pk):
    rec = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Recurring record deleted successfully.')
        return redirect('recurring_list')
    return render(request, 'expenses/confirm_delete.html', {'object': rec, 'type': 'Recurring Record', 'cancel_url': 'recurring_list'})

# --- Phase 5 Views ---

@login_required
def calendar_view(request):
    user = request.user
    
    today = datetime.date.today()
    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except ValueError:
        month, year = today.month, today.year
        
    current_date = datetime.date(year, month, 1)
    
    start_date = current_date
    end_date = current_date + relativedelta(months=1) - relativedelta(days=1)
    
    prev_month = current_date - relativedelta(months=1)
    next_month = current_date + relativedelta(months=1)
    
    actual_expenses = Expense.objects.filter(user=user, date__gte=start_date, date__lte=end_date)
    actual_incomes = Income.objects.filter(user=user, date__gte=start_date, date__lte=end_date)
    expected_tx = get_expected_transactions(user, start_date, end_date)
    
    calendar_events = []
    for exp in actual_expenses:
        calendar_events.append({
            'id': f"exp_{exp.pk}",
            'date': exp.date,
            'type': 'Expense',
            'amount': exp.amount,
            'category': exp.category,
            'description': exp.description,
            'is_actual': True,
        })
    for inc in actual_incomes:
        calendar_events.append({
            'id': f"inc_{inc.pk}",
            'date': inc.date,
            'type': 'Income',
            'amount': inc.amount,
            'category': inc.source,
            'description': inc.description,
            'is_actual': True,
        })
        
    calendar_events.extend(expected_tx)
    calendar_events.sort(key=lambda x: x['date'])
    
    context = {
        'current_date': current_date,
        'prev_month': prev_month,
        'next_month': next_month,
        'events': calendar_events,
    }
    return render(request, 'expenses/calendar.html', context)

@login_required
def forecast_view(request):
    user = request.user
    
    total_expense = Expense.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_income = Income.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    current_balance = total_income - total_expense
    
    horizon_days = int(request.GET.get('days', 30))
    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=horizon_days)
    
    expected_tx = get_expected_transactions(user, start_date, end_date)
    
    forecast_timeline = []
    running_balance = current_balance
    expected_in = Decimal('0.00')
    expected_out = Decimal('0.00')
    
    for tx in expected_tx:
        amount = tx['amount']
        if tx['type'] == 'Income':
            running_balance += amount
            expected_in += amount
        else:
            running_balance -= amount
            expected_out += amount
            
        forecast_timeline.append({
            'date': tx['date'],
            'type': tx['type'],
            'description': tx['description'],
            'amount': amount,
            'running_balance': running_balance
        })
        
    net_change = expected_in - expected_out
        
    context = {
        'horizon_days': horizon_days,
        'start_date': start_date,
        'end_date': end_date,
        'current_balance': current_balance,
        'projected_balance': running_balance,
        'expected_in': expected_in,
        'expected_out': expected_out,
        'net_change': net_change,
        'forecast_timeline': forecast_timeline,
    }
    return render(request, 'expenses/forecast.html', context)

@login_required
def simulator_view(request):
    user = request.user
    
    total_expense = Expense.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_income = Income.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    current_balance = total_income - total_expense
    
    try:
        horizon_days = int(request.POST.get('horizon_days', 30) if request.method == 'POST' else request.GET.get('horizon_days', 30))
    except ValueError:
        horizon_days = 30
        
    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=horizon_days)
    
    expected_tx = get_expected_transactions(user, start_date, end_date)
    
    baseline_running_balance = current_balance
    for tx in expected_tx:
        if tx['type'] == 'Income':
            baseline_running_balance += tx['amount']
        else:
            baseline_running_balance -= tx['amount']
            
    # Process scenario inputs
    monthly_income_adj = Decimal('0.00')
    monthly_expense_adj = Decimal('0.00')
    cat_adj_amount = Decimal('0.00')
    cat_adj_category = ""
    
    if request.method == 'POST':
        try:
            monthly_income_adj = Decimal(request.POST.get('monthly_income_adj') or '0.00')
        except: pass
        try:
            monthly_expense_adj = Decimal(request.POST.get('monthly_expense_adj') or '0.00')
        except: pass
        try:
            cat_adj_amount = Decimal(request.POST.get('cat_adj_amount') or '0.00')
        except: pass
        cat_adj_category = request.POST.get('cat_adj_category', '')

    months_in_horizon = Decimal(horizon_days) / Decimal('30.0')
    
    scenario_running_balance = baseline_running_balance
    scenario_running_balance += monthly_income_adj * months_in_horizon
    scenario_running_balance -= monthly_expense_adj * months_in_horizon
    scenario_running_balance -= cat_adj_amount * months_in_horizon
    
    scenario_diff = scenario_running_balance - baseline_running_balance
    
    # Timeline
    dates = [start_date + datetime.timedelta(days=i) for i in range(horizon_days + 1)]
    baseline_by_date = {}
    scenario_by_date = {}
    
    current_baseline = current_balance
    current_scenario = current_balance
    
    tx_by_date = {}
    for tx in expected_tx:
        if tx['date'] not in tx_by_date:
            tx_by_date[tx['date']] = []
        tx_by_date[tx['date']].append(tx)
        
    for d in dates:
        for tx in tx_by_date.get(d, []):
            if tx['type'] == 'Income':
                current_baseline += tx['amount']
                current_scenario += tx['amount']
            else:
                current_baseline -= tx['amount']
                current_scenario -= tx['amount']
                
        # add daily prorated adjustments
        if monthly_income_adj:
            current_scenario += monthly_income_adj / Decimal('30.0')
        if monthly_expense_adj:
            current_scenario -= monthly_expense_adj / Decimal('30.0')
        if cat_adj_amount:
            current_scenario -= cat_adj_amount / Decimal('30.0')
            
        baseline_by_date[d] = current_baseline
        scenario_by_date[d] = current_scenario

    table_dates = [start_date]
    if horizon_days >= 30:
        table_dates.append(start_date + datetime.timedelta(days=horizon_days//3))
        table_dates.append(start_date + datetime.timedelta(days=(horizon_days*2)//3))
    table_dates.append(end_date)
    
    timeline_summary = []
    for d in sorted(list(set(table_dates))):
        timeline_summary.append({
            'date': d,
            'baseline': baseline_by_date[d].quantize(Decimal('0.01')),
            'scenario': scenario_by_date[d].quantize(Decimal('0.01'))
        })
        
    categories = Expense.CATEGORY_CHOICES
    
    context = {
        'horizon_days': horizon_days,
        'baseline_balance': baseline_running_balance.quantize(Decimal('0.01')),
        'scenario_balance': scenario_running_balance.quantize(Decimal('0.01')),
        'scenario_diff': scenario_diff.quantize(Decimal('0.01')),
        'monthly_income_adj': monthly_income_adj,
        'monthly_expense_adj': monthly_expense_adj,
        'cat_adj_amount': cat_adj_amount,
        'cat_adj_category': cat_adj_category,
        'timeline_summary': timeline_summary,
        'categories': categories,
    }
    return render(request, 'expenses/simulator.html', context)

from .services.reports import get_report_data

@login_required
def reports_view(request):
    period = request.GET.get('period', 'current_month')
    report_data = get_report_data(request.user, period)
    return render(request, 'expenses/reports.html', report_data)
