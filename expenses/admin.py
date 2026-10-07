from django.contrib import admin
from .models import Expense, Income, MoneyProfile, RecurringTransaction, Goal

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'intent', 'amount', 'date', 'created_at')
    list_filter = ('category', 'intent', 'date')
    search_fields = ('description', 'category')

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('user', 'income_type', 'source', 'amount', 'date', 'created_at')
    list_filter = ('income_type', 'date')
    search_fields = ('description', 'source')

@admin.register(MoneyProfile)
class MoneyProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'mode', 'created_at')
    list_filter = ('mode',)

@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'category', 'frequency', 'is_active', 'next_expected_date')
    list_filter = ('transaction_type', 'frequency', 'is_active')
    search_fields = ('description', 'category')

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'target_amount', 'current_amount', 'deadline', 'status')
    list_filter = ('status',)
    search_fields = ('name',)
