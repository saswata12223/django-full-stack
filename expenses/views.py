from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Max, Avg, Count
from django.utils import timezone
from decimal import Decimal
from .models import Expense, Income
from .forms import ExpenseForm, IncomeForm
from .services.smart_spending import generate_smart_insights

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
    
    category_totals = list(month_expenses.values('category').annotate(total=Sum('amount')).order_by('-total')[:5])
    for cat in category_totals:
        cat['percentage'] = int((cat['total'] / month_total_expense) * 100) if month_total_expense > 0 else 0
        
    largest_category = category_totals[0] if category_totals else None
    daily_consumption = (month_total_expense / now.day) if now.day > 0 else Decimal('0.00')
    
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
    }
    return render(request, 'expenses/dashboard.html', context)

# --- Expense Views ---

from django.core.paginator import Paginator

@login_required
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    
    category = request.GET.get('category')
    date = request.GET.get('date')
    search = request.GET.get('search')
    
    if category:
        expenses = expenses.filter(category=category)
    if date:
        try:
            expenses = expenses.filter(date__startswith=date)
        except:
            pass
    if search:
        expenses = expenses.filter(Q(description__icontains=search) | Q(category__icontains=search))
        
    categories = Expense.CATEGORY_CHOICES
    
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
    category_totals = list(expenses.values('category').annotate(total=Sum('amount')).order_by('-total')[:4])
    active_baskets = expenses.values('category').distinct().count()
    
    for cat in category_totals:
        cat['percentage'] = int((cat['total'] / total_amount) * 100) if total_amount > 0 else 0
        
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
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Add Expense'})

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
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Edit Expense', 'expense': expense})

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
    
    search = request.GET.get('search')
    date = request.GET.get('date')
    
    if search:
        incomes = incomes.filter(Q(description__icontains=search) | Q(source__icontains=search))
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
    source_totals = list(incomes.values('source').annotate(total=Sum('amount')).order_by('-total')[:4])
    active_streams = incomes.values('source').distinct().count()
    
    for src in source_totals:
        src['percentage'] = int((src['total'] / total_amount) * 100) if total_amount > 0 else 0
        
    largest_income = incomes.order_by('-amount').first() if largest_inflow > 0 else None
    
    # Pagination
    paginator = Paginator(incomes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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
    filename = f"DhanTrack_Comprehensive_Audit_{date.today().strftime('%Y-%m-%d')}.pdf"
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

