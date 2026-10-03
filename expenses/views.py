from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from .models import Expense, Income
from .forms import ExpenseForm, IncomeForm

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

@login_required
def dashboard_view(request):
    user = request.user
    expenses = Expense.objects.filter(user=user).order_by('-date')[:5]
    incomes = Income.objects.filter(user=user).order_by('-date')[:5]
    
    total_expense = Expense.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or 0
    total_income = Income.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or 0
    balance = total_income - total_expense
    expense_count = Expense.objects.filter(user=user).count()
    
    context = {
        'recent_expenses': expenses,
        'recent_incomes': incomes,
        'total_expense': total_expense,
        'total_income': total_income,
        'balance': balance,
        'expense_count': expense_count,
    }
    return render(request, 'expenses/dashboard.html', context)

# --- Expense Views ---

@login_required
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    
    category = request.GET.get('category')
    date = request.GET.get('date')
    search = request.GET.get('search')
    
    if category:
        expenses = expenses.filter(category=category)
    if date:
        expenses = expenses.filter(date=date)
    if search:
        expenses = expenses.filter(Q(description__icontains=search) | Q(category__icontains=search))
        
    categories = Expense.CATEGORY_CHOICES
    
    context = {
        'expenses': expenses,
        'categories': categories,
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
        incomes = incomes.filter(date=date)
        
    return render(request, 'expenses/income_list.html', {'incomes': incomes})

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
