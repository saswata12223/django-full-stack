from django.contrib import admin
from .models import Expense, Income

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'amount', 'date', 'created_at')
    list_filter = ('category', 'date')
    search_fields = ('description', 'category')

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('user', 'source', 'amount', 'date', 'created_at')
    list_filter = ('date',)
    search_fields = ('description', 'source')
