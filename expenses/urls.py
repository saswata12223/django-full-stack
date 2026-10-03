from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='expenses/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
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
]
