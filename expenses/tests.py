from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from expenses.models import Expense, Income, SpendingExperiment
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
        trend_insight = next(i for i in insights['insights'] if i['title'] == 'Spending Trend')
        self.assertIn("100%", trend_insight['explanation'])
        
    def test_zero_previous_month_spending(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Desc', date=self.now)
        insights = generate_smart_insights(self.user)
        trend_insight = next(i for i in insights['insights'] if i['title'] == 'Spending Trend')
        self.assertEqual(trend_insight['explanation'], "There isn't enough previous-month data to calculate a spending trend yet.")

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

