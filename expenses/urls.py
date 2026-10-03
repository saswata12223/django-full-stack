from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='expenses/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Password Reset
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Smart Spending
    path('smart-spending/', views.smart_spending_view, name='smart_spending'),

    
    # Expenses
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_create, name='expense_add'),
    path('expenses/<int:pk>/edit/', views.expense_update, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    
    # Incomes
    path('incomes/', views.income_list, name='income_list'),
    path('incomes/add/', views.income_create, name='income_add'),
    path('incomes/<int:pk>/edit/', views.income_update, name='income_edit'),
    path('incomes/<int:pk>/delete/', views.income_delete, name='income_delete'),
    path('smart-spending/audit/pdf/', views.download_audit_pdf, name='download_audit_pdf'),
]
