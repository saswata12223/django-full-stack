from django import forms
from django.core.exceptions import ValidationError
from .models import Expense, Income, MoneyProfile, Goal, RecurringTransaction

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'category', 'intent', 'description', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'intent': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than 0.")
        return amount

class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['amount', 'income_type', 'source', 'description', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'income_type': forms.Select(attrs={'class': 'form-select'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than 0.")
        return amount

class MoneyProfileForm(forms.ModelForm):
    class Meta:
        model = MoneyProfile
        fields = ['mode']
        widgets = {
            'mode': forms.RadioSelect(attrs={'class': 'mode-select-radio'}),
        }

class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['name', 'target_amount', 'current_amount', 'deadline', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_target_amount(self):
        amount = self.cleaned_data.get('target_amount')
        if amount and amount <= 0:
            raise ValidationError("Target amount must be positive.")
        return amount

    def clean_current_amount(self):
        amount = self.cleaned_data.get('current_amount')
        if amount is not None and amount < 0:
            raise ValidationError("Current amount cannot be negative.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        target = cleaned_data.get('target_amount')
        current = cleaned_data.get('current_amount')
        
        if target and current and current > target:
            # We don't raise error, we just cap it or let the user know, but prompt says: 
            # "If current_amount exceeds target_amount, choose a sensible product behavior. 
            # Prefer validation rather than silently modifying user input."
            self.add_error('current_amount', "Current amount cannot exceed the target amount.")
            
        return cleaned_data

class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ['transaction_type', 'amount', 'category', 'description', 'frequency', 'start_date', 'end_date', 'next_expected_date', 'is_active']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}), # Will be overridden in view or template for dynamic choices based on type, but for now we'll just use TextInput or Select depending on JS. Actually, prompt says to use 'transaction_type to control appropriate presentation'. We can use TextInput with a datalist or Select. Since models.py uses CharField, we'll use TextInput.
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'next_expected_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].widget = forms.TextInput(attrs={'class': 'form-control'})

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise ValidationError("Amount must be positive.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        
        if start and end and end < start:
            self.add_error('end_date', "End date cannot precede the start date.")
            
        return cleaned_data
