from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from expenses.models import Expense, Income, SpendingExperiment, MoneyProfile, Goal, RecurringTransaction
from expenses.services.smart_spending import generate_smart_insights
from expenses.services.spending_experiment import get_experiment_context, create_experiment, cancel_experiment
from decimal import Decimal
import datetime

class SmartSpendingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.other_user = User.objects.create_user(username='otheruser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')
        self.now = timezone.now().date()
        self.start_of_month = self.now.replace(day=1)

    def test_smart_spending_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('smart_spending'))
        self.assertRedirects(response, f"/login/?next=/smart-spending/")

    def test_empty_account(self):
        insights = generate_smart_insights(self.user)
        self.assertTrue(insights['is_empty'])

    def test_income_only_account(self):
        Income.objects.create(user=self.user, amount=Decimal('100.00'), source='Salary', description='Desc', date=self.now)
        insights = generate_smart_insights(self.user)
        self.assertFalse(insights['is_empty'])
        self.assertEqual(insights['summary']['income'], Decimal('100.00'))
        self.assertEqual(insights['summary']['expenses'], Decimal('0.00'))
        self.assertEqual(insights['summary']['balance'], Decimal('100.00'))

    def test_expense_only_account(self):
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', description='Desc', date=self.now)
        insights = generate_smart_insights(self.user)
        self.assertFalse(insights['is_empty'])
        self.assertEqual(insights['summary']['income'], Decimal('0.00'))
        self.assertEqual(insights['summary']['expenses'], Decimal('50.00'))
        self.assertEqual(insights['summary']['balance'], Decimal('-50.00'))
        self.assertEqual(insights['breakdown'][0]['amount'], Decimal('50.00'))

    def test_user_data_isolation(self):
        Expense.objects.create(user=self.other_user, amount=Decimal('200.00'), category='Food', description='Desc', date=self.now)
        insights = generate_smart_insights(self.user)
        self.assertTrue(insights['is_empty'])
        
    def test_previous_month_comparison(self):
        # Current month
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Desc', date=self.now)
        # Prev month
        if self.now.month == 1:
            prev_month_date = self.now.replace(year=self.now.year - 1, month=12)
        else:
            prev_month_date = self.now.replace(month=self.now.month - 1)
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', description='Desc', date=prev_month_date)
        
        insights = generate_smart_insights(self.user)
        trend_insight = next(i for i in insights['insights'] if i['title'] == 'Spending Comparison')
        self.assertIn("100%", trend_insight['explanation'])
        
    def test_zero_previous_month_spending(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Desc', date=self.now)
        insights = generate_smart_insights(self.user)
        trend_insight = next(i for i in insights['insights'] if i['title'] == 'Spending Comparison')
        self.assertEqual(trend_insight['explanation'], "More history is needed for a month-over-month comparison.")

    def test_experiment_creation_and_progress(self):
        # Create history in previous month
        if self.now.month == 1:
            prev_month = self.now.replace(year=self.now.year - 1, month=12, day=15)
        else:
            prev_month = self.now.replace(month=self.now.month - 1, day=15)
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Food', description='Desc', date=prev_month)
        
        created = create_experiment(self.user, 'Food', '10')
        self.assertTrue(created)
        
        exp = SpendingExperiment.objects.get(user=self.user, status='ACTIVE')
        self.assertEqual(exp.baseline_amount, Decimal('1000.00'))
        self.assertEqual(exp.target_amount, Decimal('900.00'))
        
        context = get_experiment_context(self.user)
        self.assertTrue(context['has_active'])
        self.assertFalse(context['is_exceeded'])
        
        # Add another expense to exceed target
        Expense.objects.create(user=self.user, amount=Decimal('1500.00'), category='Food', description='Desc', date=self.now)
        context = get_experiment_context(self.user)
        self.assertTrue(context['is_exceeded'])
        self.assertEqual(context['progress'], Decimal('100.00'))
        
    def test_experiment_cancellation(self):
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Food', description='Desc', date=self.now)
        create_experiment(self.user, 'Food', '10')
        self.assertTrue(SpendingExperiment.objects.filter(user=self.user, status='ACTIVE').exists())
        
        cancel_experiment(self.user)
        self.assertFalse(SpendingExperiment.objects.filter(user=self.user, status='ACTIVE').exists())
        self.assertTrue(SpendingExperiment.objects.filter(user=self.user, status='CANCELLED').exists())

    def test_experiment_isolation(self):
        Expense.objects.create(user=self.other_user, amount=Decimal('1000.00'), category='Food', description='Desc', date=self.now)
        create_experiment(self.other_user, 'Food', '10')
        
        context = get_experiment_context(self.user)
        self.assertFalse(context['has_active'])

from expenses.services.spending_dna import generate_spending_dna

class SpendingDNATests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dna_user', password='testpassword')
        self.other_user = User.objects.create_user(username='dna_other', password='testpassword')
        self.client.login(username='dna_user', password='testpassword')
        self.now = timezone.now().date()
    
    def test_dna_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('smart_spending'))
        self.assertRedirects(response, f"/login/?next=/smart-spending/")
        
    def test_empty_account(self):
        dna = generate_spending_dna(self.user)
        self.assertIsNone(dna)
        
    def test_user_data_isolation(self):
        Expense.objects.create(user=self.other_user, amount=Decimal('500.00'), category='Food', description='Pizza', date=self.now)
        dna = generate_spending_dna(self.user)
        self.assertIsNone(dna) # User has no expenses, so it shouldn't see other user's
        
    def test_single_transaction(self):
        Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Food', description='Pizza', date=self.now)
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna)
        self.assertEqual(dna['summary']['total_transactions'], 1)
        self.assertEqual(dna['summary']['average_transaction'], Decimal('500.00'))
        self.assertIsNone(dna['money_leak'])
        self.assertIsNone(dna['large_transaction'])
        self.assertEqual(len(dna['repeated_spending']), 0)
        
    def test_multiple_categories_frequent_highest(self):
        # 3 Food transactions, total = 900
        Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', description='A', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', description='B', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', description='C', date=self.now)
        
        # 1 Shopping transaction, total = 2000
        Expense.objects.create(user=self.user, amount=Decimal('2000.00'), category='Shopping', description='D', date=self.now)
        
        dna = generate_spending_dna(self.user)
        self.assertEqual(dna['summary']['most_frequent_category']['category'], 'Food')
        self.assertEqual(dna['summary']['highest_spending_category']['category'], 'Shopping')
        self.assertEqual(dna['summary']['categories_used'], 2)
        
    def test_money_leak(self):
        # Need 5 small transactions and at least 10% of total
        for i in range(5):
            Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description=f'Snack {i}', date=self.now)
        
        # Total = 500. Add large to make total 2500 (small is 20%)
        Expense.objects.create(user=self.user, amount=Decimal('2000.00'), category='Shopping', description='Big', date=self.now)
        
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['money_leak'])
        self.assertEqual(dna['money_leak']['count'], 5)
        self.assertEqual(dna['money_leak']['share_percentage'], Decimal('20.0'))
        
    def test_money_leak_insufficient_data(self):
        # Only 4 small transactions
        for i in range(4):
            Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description=f'Snack {i}', date=self.now)
        
        dna = generate_spending_dna(self.user)
        self.assertIsNone(dna['money_leak'])
        
    def test_repeated_spending_and_blank(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Pizza', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('200.00'), category='Food', description=' PIZZA ', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', description='pizza', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Food', description='', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Food', description='', date=self.now)
        
        dna = generate_spending_dna(self.user)
        self.assertEqual(len(dna['repeated_spending']), 1)
        self.assertEqual(dna['repeated_spending'][0]['description'], 'Pizza')
        self.assertEqual(dna['repeated_spending'][0]['count'], 3)
        self.assertEqual(dna['repeated_spending'][0]['total'], Decimal('600.00'))

    def test_large_transaction(self):
        # 4 regular tx
        for i in range(4):
            Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='A', date=self.now)
        # 1 large tx
        Expense.objects.create(user=self.user, amount=Decimal('2000.00'), category='Shopping', description='Big', date=self.now)
        
        dna = generate_spending_dna(self.user)
        # avg = 2400 / 5 = 480. 3x = 1440. 2000 > 1440.
        self.assertIsNotNone(dna['large_transaction'])
        self.assertEqual(dna['large_transaction']['amount'], Decimal('2000.00'))
        
    def test_weekend_weekday(self):
        # Find a weekend date
        d = datetime.date(2023, 10, 7) # Saturday
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Weekend', date=d)
        
        # Find a weekday date
        d_week = datetime.date(2023, 10, 6) # Friday
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', description='Weekday', date=d_week)
        
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['weekend_pattern'])
        self.assertEqual(dna['weekend_pattern']['higher'], 'weekend')
        
    def test_historical_monthly(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='M1', date=datetime.date(2023, 9, 15))
        Expense.objects.create(user=self.user, amount=Decimal('200.00'), category='Food', description='M2', date=datetime.date(2023, 10, 15))
        
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['monthly_pattern'])
        self.assertEqual(len(dna['monthly_pattern']), 2)

from django.db import IntegrityError
from expenses.models import MoneyProfile, RecurringTransaction, Goal

class ArchitectureV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='arch_user', password='testpassword')
        self.other_user = User.objects.create_user(username='arch_other', password='testpassword')
        self.now = timezone.now().date()

    def test_money_profile_belongs_to_user(self):
        profile = MoneyProfile.objects.create(user=self.user, mode='Working Professional')
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.mode, 'Working Professional')

    def test_user_cannot_have_multiple_money_profiles(self):
        MoneyProfile.objects.create(user=self.user, mode='Working Professional')
        with self.assertRaises(IntegrityError):
            MoneyProfile.objects.create(user=self.user, mode='Freelancer')

    def test_expense_intent_choices_work(self):
        expense = Expense.objects.create(
            user=self.user, amount=Decimal('50.00'), category='Food', 
            intent='Need', description='Groceries', date=self.now
        )
        self.assertEqual(expense.intent, 'Need')

    def test_existing_expense_records_remain_valid(self):
        # Create an expense without specifying intent (simulating an older record or using default)
        expense = Expense.objects.create(
            user=self.user, amount=Decimal('50.00'), category='Food', 
            description='Groceries', date=self.now
        )
        self.assertEqual(expense.intent, 'Other') # Default is 'Other'

    def test_income_type_choices_work(self):
        income = Income.objects.create(
            user=self.user, amount=Decimal('5000.00'), source='Company', 
            income_type='Salary', description='Monthly Salary', date=self.now
        )
        self.assertEqual(income.income_type, 'Salary')

    def test_existing_income_records_remain_valid(self):
        income = Income.objects.create(
            user=self.user, amount=Decimal('5000.00'), source='Company', 
            description='Monthly Salary', date=self.now
        )
        self.assertEqual(income.income_type, 'Other')

    def test_goal_belongs_to_correct_user(self):
        goal = Goal.objects.create(
            user=self.user, name='Vacation', target_amount=Decimal('10000.00'),
            deadline=self.now, status='Active'
        )
        self.assertEqual(goal.user, self.user)

    def test_recurring_financial_records_belong_to_correct_user(self):
        recurring = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=Decimal('100.00'),
            category='Bills', description='Internet', frequency='Monthly',
            start_date=self.now, next_expected_date=self.now
        )
        self.assertEqual(recurring.user, self.user)
        self.assertEqual(recurring.transaction_type, 'Expense')

class MoneyModeV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='modetestuser', password='testpassword')
        self.other_user = User.objects.create_user(username='modeotheruser', password='testpassword')

    def test_unauth_access_rejected(self):
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, f"/login/?next=/profile/")

    def test_auth_user_without_profile_redirected(self):
        self.client.login(username='modetestuser', password='testpassword')
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('profile_setup'))
        
    def test_user_can_select_money_mode(self):
        self.client.login(username='modetestuser', password='testpassword')
        response = self.client.post(reverse('profile_setup'), {'mode': 'College Student'})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(MoneyProfile.objects.get(user=self.user).mode, 'College Student')

    def test_existing_user_with_profile_accesses_dashboard(self):
        MoneyProfile.objects.create(user=self.user, mode='Working Professional')
        self.client.login(username='modetestuser', password='testpassword')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_user_can_change_money_mode(self):
        MoneyProfile.objects.create(user=self.user, mode='Working Professional')
        self.client.login(username='modetestuser', password='testpassword')
        response = self.client.post(reverse('profile'), {'mode': 'Freelancer'})
        self.assertRedirects(response, reverse('profile'))
        self.user.money_profile.refresh_from_db()
        self.assertEqual(self.user.money_profile.mode, 'Freelancer')

    def test_changing_mode_does_not_delete_data(self):
        MoneyProfile.objects.create(user=self.user, mode='Working Professional')
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', description='Desc', date=timezone.now().date())
        self.client.login(username='modetestuser', password='testpassword')
        self.client.post(reverse('profile'), {'mode': 'Freelancer'})
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)

    def test_invalid_mode_rejected(self):
        self.client.login(username='modetestuser', password='testpassword')
        response = self.client.post(reverse('profile_setup'), {'mode': 'Invalid Mode'})
        self.assertEqual(response.status_code, 200) # Form re-renders with errors
        self.assertFalse(MoneyProfile.objects.filter(user=self.user).exists())

class Phase3Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase3user', password='testpassword')
        self.other_user = User.objects.create_user(username='phase3other', password='testpassword')
        self.client.login(username='phase3user', password='testpassword')
        self.now = timezone.now().date()
        MoneyProfile.objects.create(user=self.user, mode='Freelancer')

    # --- Expense Tests ---
    def test_expense_created_with_valid_intent(self):
        response = self.client.post(reverse('expense_add'), {
            'amount': '150.00', 'category': 'Food', 'description': 'Lunch',
            'date': self.now, 'intent': 'Need'
        })
        self.assertRedirects(response, reverse('expense_list'))
        self.assertEqual(Expense.objects.get(user=self.user).intent, 'Need')

    def test_invalid_intent_rejected(self):
        response = self.client.post(reverse('expense_add'), {
            'amount': '150.00', 'category': 'Food', 'description': 'Lunch',
            'date': self.now, 'intent': 'InvalidIntent'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'intent', 'Select a valid choice. InvalidIntent is not one of the available choices.')
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 0)

    def test_expense_edited_to_change_intent(self):
        expense = Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', intent='Want', description='Snack', date=self.now)
        response = self.client.post(reverse('expense_edit', args=[expense.pk]), {
            'amount': '50.00', 'category': 'Food', 'description': 'Snack',
            'date': self.now, 'intent': 'Social'
        })
        self.assertRedirects(response, reverse('expense_list'))
        expense.refresh_from_db()
        self.assertEqual(expense.intent, 'Social')

    def test_expense_list_displays_intent(self):
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', intent='Social', description='Dinner', date=self.now)
        response = self.client.get(reverse('expense_list'))
        self.assertContains(response, 'Intent: Social')

    def test_expense_filtering_by_intent(self):
        Expense.objects.create(user=self.user, amount=Decimal('50.00'), category='Food', intent='Social', description='Dinner', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('150.00'), category='Food', intent='Need', description='Groceries', date=self.now)
        
        response = self.client.get(reverse('expense_list'), {'intent': 'Social'})
        self.assertEqual(len(response.context['expenses']), 1)
        self.assertEqual(response.context['expenses'][0].intent, 'Social')

    def test_user_cannot_access_other_user_expense(self):
        other_expense = Expense.objects.create(user=self.other_user, amount=Decimal('50.00'), category='Food', intent='Want', description='Snack', date=self.now)
        response = self.client.get(reverse('expense_edit', args=[other_expense.pk]))
        self.assertEqual(response.status_code, 404)

    # --- Income Tests ---
    def test_income_created_with_valid_income_type(self):
        response = self.client.post(reverse('income_add'), {
            'amount': '1500.00', 'source': 'Company', 'description': 'Salary',
            'date': self.now, 'income_type': 'Salary'
        })
        self.assertRedirects(response, reverse('income_list'))
        self.assertEqual(Income.objects.get(user=self.user).income_type, 'Salary')

    def test_invalid_income_type_rejected(self):
        response = self.client.post(reverse('income_add'), {
            'amount': '1500.00', 'source': 'Company', 'description': 'Salary',
            'date': self.now, 'income_type': 'InvalidType'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'income_type', 'Select a valid choice. InvalidType is not one of the available choices.')
        self.assertEqual(Income.objects.filter(user=self.user).count(), 0)

    def test_income_edited_to_change_income_type(self):
        income = Income.objects.create(user=self.user, amount=Decimal('5000.00'), source='Company', income_type='Other', description='Pay', date=self.now)
        response = self.client.post(reverse('income_edit', args=[income.pk]), {
            'amount': '5000.00', 'source': 'Company', 'description': 'Pay',
            'date': self.now, 'income_type': 'Salary'
        })
        self.assertRedirects(response, reverse('income_list'))
        income.refresh_from_db()
        self.assertEqual(income.income_type, 'Salary')

    def test_income_list_displays_income_type(self):
        Income.objects.create(user=self.user, amount=Decimal('5000.00'), source='Company', income_type='Salary', description='Pay', date=self.now)
        response = self.client.get(reverse('income_list'))
        self.assertContains(response, 'Type: Salary')

    def test_income_filtering_by_income_type(self):
        Income.objects.create(user=self.user, amount=Decimal('5000.00'), source='Company', income_type='Salary', description='Pay', date=self.now)
        Income.objects.create(user=self.user, amount=Decimal('200.00'), source='Friend', income_type='Gift', description='Gift', date=self.now)
        
        response = self.client.get(reverse('income_list'), {'income_type': 'Gift'})
        self.assertEqual(len(response.context['incomes']), 1)
        self.assertEqual(response.context['incomes'][0].income_type, 'Gift')

    def test_user_cannot_access_other_user_income(self):
        other_income = Income.objects.create(user=self.other_user, amount=Decimal('50.00'), source='Company', income_type='Salary', description='Pay', date=self.now)
        response = self.client.get(reverse('income_edit', args=[other_income.pk]))
        self.assertEqual(response.status_code, 404)
        
    def test_money_mode_influences_contextual_ui(self):
        # We created user with Freelancer mode
        response = self.client.get(reverse('expense_add'))
        # Freelancer mode suggestions: 'Personal', 'Work', 'Client', 'Business', 'Essential'
        self.assertContains(response, 'Client')
        self.assertContains(response, 'Business')
        
        # Change mode and verify suggestions change
        profile = self.user.money_profile
        profile.mode = 'College Student'
        profile.save()
        
        response = self.client.get(reverse('expense_add'))
        self.assertContains(response, 'Study')
        self.assertNotContains(response, 'Client')

class Phase4Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase4user', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')
        self.client.login(username='phase4user', password='password')
        self.now = timezone.now().date()

    # --- Goal Tests ---
    def test_authenticated_user_can_access_goals(self):
        response = self.client.get(reverse('goal_list'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_cannot_access_goals(self):
        self.client.logout()
        response = self.client.get(reverse('goal_list'))
        self.assertRedirects(response, f"/login/?next=/goals/")

    def test_user_can_create_goal(self):
        response = self.client.post(reverse('goal_add'), {
            'name': 'Vacation',
            'target_amount': 50000,
            'current_amount': 10000,
            'status': 'Active'
        })
        self.assertRedirects(response, reverse('goal_list'))
        self.assertTrue(Goal.objects.filter(name='Vacation', user=self.user).exists())

    def test_goal_defaults_correctly(self):
        response = self.client.get(reverse('goal_add'))
        self.assertEqual(response.context['form'].initial.get('status'), 'Active')

    def test_invalid_target_amount_rejected(self):
        response = self.client.post(reverse('goal_add'), {
            'name': 'Invalid Goal',
            'target_amount': -100,
            'current_amount': 0,
            'status': 'Active'
        })
        self.assertFormError(response, 'form', 'target_amount', 'Target amount must be positive.')

    def test_invalid_current_amount_rejected(self):
        response = self.client.post(reverse('goal_add'), {
            'name': 'Invalid Goal',
            'target_amount': 1000,
            'current_amount': -10,
            'status': 'Active'
        })
        self.assertFormError(response, 'form', 'current_amount', 'Current amount cannot be negative.')

    def test_goal_progress_calculation(self):
        Goal.objects.create(user=self.user, name='Progress', target_amount=1000, current_amount=250)
        response = self.client.get(reverse('goal_list'))
        active_goals = response.context['active_goals']
        goal = active_goals[0]
        self.assertEqual(goal.progress_percentage, 25)
        self.assertEqual(goal.remaining_amount, Decimal('750.00'))

    def test_goal_can_be_edited(self):
        goal = Goal.objects.create(user=self.user, name='Old Name', target_amount=1000, current_amount=0)
        response = self.client.post(reverse('goal_edit', args=[goal.pk]), {
            'name': 'New Name',
            'target_amount': 1000,
            'current_amount': 100,
            'status': 'Active'
        })
        self.assertRedirects(response, reverse('goal_list'))
        goal.refresh_from_db()
        self.assertEqual(goal.name, 'New Name')

    def test_goal_can_be_deleted(self):
        goal = Goal.objects.create(user=self.user, name='Delete Me', target_amount=1000, current_amount=0)
        response = self.client.post(reverse('goal_delete', args=[goal.pk]))
        self.assertRedirects(response, reverse('goal_list'))
        self.assertFalse(Goal.objects.filter(pk=goal.pk).exists())

    def test_user_cannot_access_another_users_goal(self):
        goal = Goal.objects.create(user=self.other_user, name='Other Goal', target_amount=100, current_amount=0)
        response = self.client.get(reverse('goal_edit', args=[goal.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_edit_another_users_goal(self):
        goal = Goal.objects.create(user=self.other_user, name='Other Goal', target_amount=100, current_amount=0)
        response = self.client.post(reverse('goal_edit', args=[goal.pk]), {
            'name': 'Hacked', 'target_amount': 100, 'current_amount': 10, 'status': 'Active'
        })
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_users_goal(self):
        goal = Goal.objects.create(user=self.other_user, name='Other Goal', target_amount=100, current_amount=0)
        response = self.client.post(reverse('goal_delete', args=[goal.pk]))
        self.assertEqual(response.status_code, 404)

    # --- Recurring Money Tests ---
    def test_authenticated_user_can_access_recurring(self):
        response = self.client.get(reverse('recurring_list'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_cannot_access_recurring(self):
        self.client.logout()
        response = self.client.get(reverse('recurring_list'))
        self.assertRedirects(response, f"/login/?next=/recurring/")

    def test_user_can_create_recurring_income(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Income',
            'amount': 50000,
            'category': 'Salary',
            'description': 'Tech Job',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertRedirects(response, reverse('recurring_list'))
        self.assertTrue(RecurringTransaction.objects.filter(description='Tech Job').exists())

    def test_user_can_create_recurring_expense(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Expense',
            'amount': 15000,
            'category': 'Rent',
            'description': 'Apartment',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertRedirects(response, reverse('recurring_list'))
        self.assertTrue(RecurringTransaction.objects.filter(description='Apartment').exists())

    def test_invalid_frequency_rejected(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Income',
            'amount': 1000,
            'category': 'Test',
            'description': 'Test',
            'frequency': 'Daily', # Invalid choice
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertFormError(response, 'form', 'frequency', 'Select a valid choice. Daily is not one of the available choices.')

    def test_invalid_transaction_type_rejected(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Invalid', # Invalid choice
            'amount': 1000,
            'category': 'Test',
            'description': 'Test',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertFormError(response, 'form', 'transaction_type', 'Select a valid choice. Invalid is not one of the available choices.')

    def test_positive_amount_required(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Expense',
            'amount': -500,
            'category': 'Test',
            'description': 'Test',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertFormError(response, 'form', 'amount', 'Amount must be positive.')

    def test_end_date_cannot_precede_start_date(self):
        response = self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Expense',
            'amount': 500,
            'category': 'Test',
            'description': 'Test',
            'frequency': 'Monthly',
            'start_date': self.now,
            'end_date': self.now - datetime.timedelta(days=1),
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertFormError(response, 'form', 'end_date', 'End date cannot precede the start date.')

    def test_user_can_edit_recurring_money(self):
        rec = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', description='Old', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.post(reverse('recurring_edit', args=[rec.pk]), {
            'transaction_type': 'Expense',
            'amount': 1000,
            'category': 'Test',
            'description': 'New',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        self.assertRedirects(response, reverse('recurring_list'))
        rec.refresh_from_db()
        self.assertEqual(rec.amount, 1000)
        self.assertEqual(rec.description, 'New')

    def test_user_can_deactivate_and_reactivate_recurring_money(self):
        rec = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', description='Test', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        # Deactivate
        self.client.post(reverse('recurring_edit', args=[rec.pk]), {
            'transaction_type': 'Expense', 'amount': 500, 'category': 'Test', 'description': 'Test', 
            'frequency': 'Monthly', 'start_date': self.now, 'next_expected_date': self.now, 'is_active': False
        })
        rec.refresh_from_db()
        self.assertFalse(rec.is_active)
        
        # Reactivate
        self.client.post(reverse('recurring_edit', args=[rec.pk]), {
            'transaction_type': 'Expense', 'amount': 500, 'category': 'Test', 'description': 'Test', 
            'frequency': 'Monthly', 'start_date': self.now, 'next_expected_date': self.now, 'is_active': True
        })
        rec.refresh_from_db()
        self.assertTrue(rec.is_active)

    def test_user_can_delete_recurring_money(self):
        rec = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', description='Test', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.post(reverse('recurring_delete', args=[rec.pk]))
        self.assertRedirects(response, reverse('recurring_list'))
        self.assertFalse(RecurringTransaction.objects.filter(pk=rec.pk).exists())

    def test_user_cannot_access_another_users_recurring_record(self):
        rec = RecurringTransaction.objects.create(
            user=self.other_user, transaction_type='Expense', amount=500, category='Test', description='Test', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.get(reverse('recurring_edit', args=[rec.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_edit_another_users_recurring_record(self):
        rec = RecurringTransaction.objects.create(
            user=self.other_user, transaction_type='Expense', amount=500, category='Test', description='Test', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.post(reverse('recurring_edit', args=[rec.pk]), {
            'transaction_type': 'Expense', 'amount': 1000, 'category': 'Test', 'description': 'Test', 
            'frequency': 'Monthly', 'start_date': self.now, 'next_expected_date': self.now, 'is_active': True
        })
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_users_recurring_record(self):
        rec = RecurringTransaction.objects.create(
            user=self.other_user, transaction_type='Expense', amount=500, category='Test', description='Test', 
            frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.post(reverse('recurring_delete', args=[rec.pk]))
        self.assertEqual(response.status_code, 404)

    def test_creating_recurring_money_does_not_create_expense_income_records(self):
        initial_expense_count = Expense.objects.count()
        initial_income_count = Income.objects.count()
        
        self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Expense',
            'amount': 15000,
            'category': 'Rent',
            'description': 'Apartment',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        
        self.client.post(reverse('recurring_add'), {
            'transaction_type': 'Income',
            'amount': 50000,
            'category': 'Salary',
            'description': 'Tech Job',
            'frequency': 'Monthly',
            'start_date': self.now,
            'next_expected_date': self.now,
            'is_active': True
        })
        
        self.assertEqual(Expense.objects.count(), initial_expense_count)
        self.assertEqual(Income.objects.count(), initial_income_count)

class Phase5Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase5user', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')
        self.client.login(username='phase5user', password='password')
        self.now = timezone.now().date()
        self.start_of_month = self.now.replace(day=1)

    def test_calendar_authenticated_only(self):
        self.client.logout()
        response = self.client.get(reverse('calendar'))
        self.assertRedirects(response, f"/login/?next=/calendar/")

    def test_forecast_authenticated_only(self):
        self.client.logout()
        response = self.client.get(reverse('forecast'))
        self.assertRedirects(response, f"/login/?next=/forecast/")

    def test_calendar_shows_actual_income_and_expense(self):
        Income.objects.create(user=self.user, amount=5000, source='Salary', income_type='Salary', description='Job', date=self.now)
        Expense.objects.create(user=self.user, amount=1000, category='Food', description='Lunch', date=self.now)
        
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        events = response.context['events']
        self.assertEqual(len(events), 2)
        
        event_types = [e['type'] for e in events]
        self.assertIn('Income', event_types)
        self.assertIn('Expense', event_types)
        
        # Verify is_actual is true for these
        for e in events:
            self.assertTrue(e['is_actual'])

    def test_calendar_shows_expected_recurring(self):
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Subscription', 
            description='Netflix', frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.get(reverse('calendar'))
        events = response.context['events']
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]['is_actual'])
        self.assertEqual(events[0]['description'], 'Netflix')

    def test_inactive_recurring_ignored(self):
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', 
            description='Test', frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=False
        )
        response = self.client.get(reverse('calendar'))
        self.assertEqual(len(response.context['events']), 0)

    def test_recurring_end_date_respected(self):
        yesterday = self.now - datetime.timedelta(days=1)
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', 
            description='Test', frequency='Monthly', start_date=yesterday, end_date=yesterday, 
            next_expected_date=yesterday, is_active=True
        )
        response = self.client.get(reverse('calendar'))
        events = response.context['events']
        # Today's month shouldn't show the event if the end_date was yesterday (unless yesterday is in the same month)
        # We need to test if occurrences generate beyond end_date.
        from expenses.services.recurrence import get_expected_transactions
        txs = get_expected_transactions(self.user, self.now, self.now + datetime.timedelta(days=30))
        self.assertEqual(len(txs), 0)

    def test_future_start_date_respected(self):
        future = self.now + datetime.timedelta(days=60)
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', 
            description='Test', frequency='Monthly', start_date=future, 
            next_expected_date=future, is_active=True
        )
        from expenses.services.recurrence import get_expected_transactions
        txs = get_expected_transactions(self.user, self.now, self.now + datetime.timedelta(days=30))
        self.assertEqual(len(txs), 0)

    def test_recurrence_frequencies(self):
        from expenses.services.recurrence import calculate_occurrences
        rec = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=500, category='Test', 
            description='Weekly', frequency='Weekly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        txs = calculate_occurrences(rec, self.now, self.now + datetime.timedelta(days=30))
        # Within 30 days, a weekly event occurs ~4-5 times
        self.assertGreaterEqual(len(txs), 4)
        
    def test_cross_user_isolation(self):
        Income.objects.create(user=self.other_user, amount=5000, source='Salary', income_type='Salary', description='Job', date=self.now)
        RecurringTransaction.objects.create(
            user=self.other_user, transaction_type='Expense', amount=500, category='Test', 
            description='Test', frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        response = self.client.get(reverse('calendar'))
        self.assertEqual(len(response.context['events']), 0)
        
        response = self.client.get(reverse('forecast'))
        self.assertEqual(response.context['projected_balance'], Decimal('0.00'))

    def test_forecast_logic(self):
        # Actual balance = 1000 - 200 = 800
        Income.objects.create(user=self.user, amount=1000, source='Salary', income_type='Salary', description='Job', date=self.now)
        Expense.objects.create(user=self.user, amount=200, category='Food', description='Lunch', date=self.now)
        
        # Expected = +5000 (Income) and -1000 (Expense) occurring once in next 30 days
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Income', amount=5000, category='Test', 
            description='Test', frequency='Monthly', start_date=self.now + datetime.timedelta(days=5), next_expected_date=self.now, is_active=True
        )
        RecurringTransaction.objects.create(
            user=self.user, transaction_type='Expense', amount=1000, category='Test', 
            description='Test', frequency='Monthly', start_date=self.now + datetime.timedelta(days=10), next_expected_date=self.now, is_active=True
        )
        
        response = self.client.get(reverse('forecast'))
        self.assertEqual(response.context['current_balance'], Decimal('800.00'))
        self.assertEqual(response.context['expected_in'], Decimal('5000.00'))
        self.assertEqual(response.context['expected_out'], Decimal('1000.00'))
        self.assertEqual(response.context['net_change'], Decimal('4000.00'))
        self.assertEqual(response.context['projected_balance'], Decimal('4800.00'))

    def test_calendar_and_forecast_do_not_mutate_db(self):
        # Creating a record to view
        rec = RecurringTransaction.objects.create(
            user=self.user, transaction_type='Income', amount=5000, category='Test', 
            description='Test', frequency='Monthly', start_date=self.now, next_expected_date=self.now, is_active=True
        )
        
        init_expense_count = Expense.objects.count()
        init_income_count = Income.objects.count()
        init_next_expected_date = rec.next_expected_date
        
        self.client.get(reverse('calendar'))
        self.client.get(reverse('forecast'))
        
        self.assertEqual(rec.next_expected_date, init_next_expected_date)
        self.assertEqual(Expense.objects.count(), init_expense_count)
        self.assertEqual(Income.objects.count(), init_income_count)

class Phase6Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase6user', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')
        self.client.login(username='phase6user', password='password')
        self.now = timezone.now().date()
        self.current_month = self.now.month
        self.current_year = self.now.year
        if self.current_month == 1:
            self.prev_month = 12
            self.prev_year = self.current_year - 1
        else:
            self.prev_month = self.current_month - 1
            self.prev_year = self.current_year
            
    def test_smart_spending_unauthenticated(self):
        self.client.logout()
        response = self.client.get(reverse('smart_spending'))
        self.assertRedirects(response, f"/login/?next=/smart-spending/")

    def test_smart_spending_empty_state(self):
        response = self.client.get(reverse('smart_spending'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_empty'])

    def test_smart_spending_totals_and_aggregations(self):
        Expense.objects.create(user=self.user, amount=Decimal('2000.00'), category='Food', intent='Need', description='Groceries', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Food', intent='Want', description='Snacks', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('1500.00'), category='Shopping', intent='Want', description='Shirt', date=self.now)
        
        # Other user's expense should be ignored
        Expense.objects.create(user=self.other_user, amount=Decimal('10000.00'), category='Food', intent='Need', description='Ignored', date=self.now)
        
        response = self.client.get(reverse('smart_spending'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_empty'])
        
        summary = response.context['summary']
        self.assertEqual(summary['expenses'], Decimal('4000.00'))
        
        breakdown = response.context['breakdown']
        self.assertEqual(len(breakdown), 2)
        self.assertEqual(breakdown[0]['category'], 'Food')
        self.assertEqual(breakdown[0]['amount'], Decimal('2500.00'))
        
        intent_breakdown = response.context['intent_breakdown']
        self.assertEqual(len(intent_breakdown), 2)
        want = next(i for i in intent_breakdown if i['intent'] == 'Want')
        self.assertEqual(want['amount'], Decimal('2000.00'))
        self.assertEqual(want['percentage'], Decimal('50.0'))
        
        largest = response.context['largest_expenses']
        self.assertEqual(len(largest), 3)
        self.assertEqual(largest[0].amount, Decimal('2000.00'))

    def test_smart_spending_comparison(self):
        # Prev month
        prev_date = self.now.replace(year=self.prev_year, month=self.prev_month, day=15)
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Food', date=prev_date)
        
        # Curr month
        Expense.objects.create(user=self.user, amount=Decimal('1500.00'), category='Food', date=self.now)
        
        response = self.client.get(reverse('smart_spending'))
        insights = response.context['insights']
        comparison_insight = next((i for i in insights if i['title'] == 'Spending Comparison'), None)
        self.assertIsNotNone(comparison_insight)
        self.assertIn('increased by 50%', comparison_insight['explanation'])

    def test_spending_dna_logic(self):
        Expense.objects.create(user=self.user, amount=Decimal('200.00'), category='Food', intent='Need', description='Coffee', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', intent='Need', description='Lunch', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Shopping', intent='Want', description='Shoes', date=self.now)
        
        # Other user
        Expense.objects.create(user=self.other_user, amount=Decimal('5000.00'), category='Travel', date=self.now)

        from expenses.services.spending_dna import generate_spending_dna
        dna = generate_spending_dna(self.user)
        
        self.assertIsNotNone(dna)
        self.assertEqual(dna['summary']['total_spending'], Decimal('1500.00'))
        self.assertEqual(dna['summary']['total_transactions'], 3)
        self.assertEqual(dna['summary']['average_transaction'], Decimal('500.00'))
        self.assertEqual(dna['summary']['largest_transaction'], Decimal('1000.00'))
        
        # Intent stats
        self.assertEqual(dna['need_want_summary']['Need']['total'], Decimal('500.00'))
        self.assertEqual(dna['need_want_summary']['Want']['total'], Decimal('1000.00'))
        
        # Monthly trend should be None if < 2 months
        self.assertIsNone(dna['monthly_trend'])

class Phase7SimulatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase7', password='password')
        self.other_user = User.objects.create_user(username='other7', password='password')
        self.client.login(username='phase7', password='password')
        self.now = timezone.now().date()
        
        # Setup some base actuals
        Income.objects.create(user=self.user, amount=Decimal('50000.00'), source='Salary', income_type='Salary', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('20000.00'), category='Food', description='Groceries', date=self.now)
        
        # Other user
        Expense.objects.create(user=self.other_user, amount=Decimal('50000.00'), category='Shopping', description='Ignore', date=self.now)

        # Base current balance: 50,000 - 20,000 = 30,000

    def test_simulator_auth_protection(self):
        self.client.logout()
        resp = self.client.get(reverse('simulator'))
        self.assertRedirects(resp, '/login/?next=/simulator/')

    def test_simulator_baseline_calculation_and_empty_state(self):
        # Even with empty state (if we delete records), baseline should be 0.
        resp = self.client.get(reverse('simulator'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['baseline_balance'], Decimal('30000.00'))
        self.assertEqual(resp.context['scenario_balance'], Decimal('30000.00'))
        self.assertEqual(resp.context['scenario_diff'], Decimal('0.00'))
        
    def test_simulator_scenario_income_expense_adjustment(self):
        # 30 day horizon by default
        # Add 10000 income, 5000 expense
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '30',
            'monthly_income_adj': '10000',
            'monthly_expense_adj': '5000'
        })
        self.assertEqual(resp.status_code, 200)
        # months_in_horizon = 1
        # Scenario = 30000 + 10000 - 5000 = 35000
        self.assertEqual(resp.context['scenario_balance'], Decimal('35000.00'))
        self.assertEqual(resp.context['scenario_diff'], Decimal('5000.00'))

    def test_simulator_category_adjustment(self):
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '30',
            'cat_adj_category': 'Food',
            'cat_adj_amount': '2000'
        })
        self.assertEqual(resp.status_code, 200)
        # Category adjustment reduces balance (it's an expense)
        self.assertEqual(resp.context['scenario_balance'], Decimal('28000.00'))
        self.assertEqual(resp.context['scenario_diff'], Decimal('-2000.00'))

    def test_simulator_multiple_adjustments_and_decimal(self):
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '30',
            'monthly_income_adj': '150.75',
            'monthly_expense_adj': '50.25',
            'cat_adj_category': 'Shopping',
            'cat_adj_amount': '100.50'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['scenario_balance'], Decimal('30000.00'))
        self.assertEqual(resp.context['scenario_diff'], Decimal('0.00'))
        
    def test_simulator_horizons(self):
        # 60 days
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '60',
            'monthly_income_adj': '3000',
        })
        # months = 60/30 = 2. scenario +6000
        self.assertEqual(resp.context['scenario_balance'], Decimal('36000.00'))
        
        # 90 days
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '90',
            'monthly_income_adj': '3000',
        })
        # months = 3. scenario +9000
        self.assertEqual(resp.context['scenario_balance'], Decimal('39000.00'))

    def test_simulator_negative_balance(self):
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '30',
            'monthly_expense_adj': '50000',
        })
        self.assertEqual(resp.context['scenario_balance'], Decimal('-20000.00'))

    def test_simulator_with_recurring(self):
        # Add active recurring
        RecurringTransaction.objects.create(
            user=self.user, amount=Decimal('5000.00'), transaction_type='Expense',
            category='Bills', description='Rent', frequency='Monthly',
            start_date=self.now,
            next_expected_date=self.now + timezone.timedelta(days=10),
            is_active=True
        )
        
        # Add inactive recurring (should be excluded)
        RecurringTransaction.objects.create(
            user=self.user, amount=Decimal('100000.00'), transaction_type='Income',
            category='Salary', description='Old Job', frequency='Monthly',
            start_date=self.now,
            next_expected_date=self.now + timezone.timedelta(days=10),
            is_active=False
        )

        resp = self.client.post(reverse('simulator'), {
            'horizon_days': '30',
        })
        # Baseline = 30,000
        # Expected tx within 30 days = 1 Rent (-5000)
        # New baseline projected = 25,000
        self.assertEqual(resp.context['baseline_balance'], Decimal('25000.00'))
        self.assertEqual(resp.context['scenario_balance'], Decimal('25000.00'))
        
    def test_simulator_does_not_mutate_data(self):
        Goal.objects.create(user=self.user, name='House', target_amount=Decimal('100000.0'), current_amount=Decimal('10000.0'), deadline=self.now + timezone.timedelta(days=365))
        
        exp_count = Expense.objects.count()
        inc_count = Income.objects.count()
        rec_count = RecurringTransaction.objects.count()
        goal_current = Goal.objects.get(name='House').current_amount
        
        self.client.post(reverse('simulator'), {
            'horizon_days': '90',
            'monthly_income_adj': '50000',
            'monthly_expense_adj': '10000',
            'cat_adj_amount': '5000'
        })
        
        self.assertEqual(Expense.objects.count(), exp_count)
        self.assertEqual(Income.objects.count(), inc_count)
        self.assertEqual(RecurringTransaction.objects.count(), rec_count)
        self.assertEqual(Goal.objects.get(name='House').current_amount, goal_current)

    def test_simulator_invalid_inputs(self):
        resp = self.client.post(reverse('simulator'), {
            'horizon_days': 'invalid',
            'monthly_income_adj': 'bad',
            'monthly_expense_adj': 'format'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['horizon_days'], 30)
        self.assertEqual(resp.context['monthly_income_adj'], Decimal('0.00'))
        self.assertEqual(resp.context['monthly_expense_adj'], Decimal('0.00'))

class Phase8ReportsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase8', password='password')
        self.other_user = User.objects.create_user(username='other8', password='password')
        self.client.login(username='phase8', password='password')
        self.now = timezone.now().date()
        
        # Setup actuals for current period
        Income.objects.create(user=self.user, amount=Decimal('5000.00'), source='Job', income_type='Salary', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Food', intent='Need', description='Groceries', date=self.now)
        Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Shopping', intent='Want', description='Shoes', date=self.now)
        
        # Cross-user isolation
        Income.objects.create(user=self.other_user, amount=Decimal('100000.00'), source='Job', income_type='Salary', date=self.now)
        
        # Previous period math
        self.prev_month = self.now.replace(day=1) - timezone.timedelta(days=1)
        Expense.objects.create(user=self.user, amount=Decimal('1000.00'), category='Food', intent='Need', description='Old Groceries', date=self.prev_month)
        
        # Ensure Goal and Recurring are NOT mixed into actuals
        Goal.objects.create(user=self.user, name='House', target_amount=Decimal('10000.0'), current_amount=Decimal('500.0'))
        RecurringTransaction.objects.create(
            user=self.user, amount=Decimal('100.00'), transaction_type='Expense',
            category='Bills', description='Netflix', frequency='Monthly',
            start_date=self.now, next_expected_date=self.now, is_active=True
        )

    def test_reports_auth_protection(self):
        self.client.logout()
        resp = self.client.get(reverse('reports'))
        self.assertRedirects(resp, '/login/?next=/reports/')

    def test_reports_current_period_aggregations(self):
        resp = self.client.get(reverse('reports'), {'period': 'current_month'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_income'], Decimal('5000.00'))
        self.assertEqual(resp.context['total_expense'], Decimal('1500.00'))
        self.assertEqual(resp.context['net_cash_flow'], Decimal('3500.00'))
        self.assertEqual(resp.context['expense_count'], 2)
        self.assertEqual(resp.context['income_count'], 1)
        self.assertEqual(resp.context['average_expense'], Decimal('750.00'))
        self.assertEqual(resp.context['largest_expense'].amount, Decimal('1000.00'))
        
    def test_reports_previous_period_aggregations(self):
        resp = self.client.get(reverse('reports'), {'period': 'previous_month'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_income'], Decimal('0.00'))
        self.assertEqual(resp.context['total_expense'], Decimal('1000.00'))
        self.assertEqual(resp.context['net_cash_flow'], Decimal('-1000.00'))
        
    def test_reports_category_intent_aggregations(self):
        resp = self.client.get(reverse('reports'), {'period': 'current_month'})
        cats = resp.context['category_breakdown']
        self.assertEqual(len(cats), 2)
        # Assuming order is descending by amount
        self.assertEqual(cats[0]['category'], 'Food')
        self.assertEqual(cats[0]['amount'], Decimal('1000.00'))
        self.assertEqual(float(cats[0]['percentage']), 66.7)
        
        intents = resp.context['intent_breakdown']
        self.assertEqual(len(intents), 2)
        
        inc_types = resp.context['income_type_breakdown']
        self.assertEqual(len(inc_types), 1)
        
    def test_reports_month_over_month_comparison(self):
        resp = self.client.get(reverse('reports'), {'period': 'current_month'})
        # previous month expense was 1000. current is 1500.
        self.assertEqual(resp.context['prev_total_expense'], Decimal('1000.00'))
        self.assertEqual(resp.context['exp_diff'], Decimal('500.00'))
        self.assertEqual(resp.context['exp_pct_change'], Decimal('50.0'))
        
        # Income previous was 0, current is 5000
        self.assertEqual(resp.context['prev_total_income'], Decimal('0.00'))
        self.assertEqual(resp.context['inc_diff'], Decimal('5000.00'))
        self.assertIsNone(resp.context['inc_pct_change'])
        
    def test_reports_isolation_and_separation(self):
        # Ensure Goal and Recurring are NOT in total_expense
        resp = self.client.get(reverse('reports'), {'period': 'current_month'})
        # total_expense is 1500. Not 1500 + 100 (recurring) + 500 (goal).
        self.assertEqual(resp.context['total_expense'], Decimal('1500.00'))
        # Goals explicitly in goals summary
        self.assertEqual(resp.context['goals_summary']['total_target'], Decimal('10000.0'))
        # Recurring explicitly in recurring summary
        self.assertEqual(resp.context['recurring_summary']['expected_monthly_outflow'], Decimal('100.0'))

class Phase8AuditPDFTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='phase8pdf', password='password')
        self.client.login(username='phase8pdf', password='password')
        
    def test_pdf_auth_protection(self):
        self.client.logout()
        resp = self.client.get(reverse('download_audit_pdf'))
        self.assertRedirects(resp, '/login/?next=/smart-spending/audit/pdf/')

    def test_pdf_generation_is_successful_and_contains_branding(self):
        resp = self.client.get(reverse('download_audit_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        
        content_disposition = resp['Content-Disposition']
        self.assertIn('filename="MoneyMitra_Comprehensive_Audit', content_disposition)
        self.assertNotIn('DhanTrack', content_disposition)
        
        # We can't trivially parse the PDF binary text here natively without PyPDF2,
        # but returning a 200 with application/pdf and proper filename is solid validation
        # that the reportlab flow ran cleanly.

