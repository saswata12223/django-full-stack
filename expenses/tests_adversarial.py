from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from expenses.models import Expense
from expenses.services.spending_dna import generate_spending_dna
from decimal import Decimal
import datetime

class SpendingDNAAdversarialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='adv_user', password='password')
        self.other_user = User.objects.create_user(username='adv_other', password='password')

    def test_zero_expenses(self):
        dna = generate_spending_dna(self.user)
        self.assertIsNone(dna)

    def test_one_expense(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='Desc', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna)
        self.assertEqual(dna['summary']['total_transactions'], 1)
        self.assertEqual(dna['summary']['average_transaction'], Decimal('100.00'))
        self.assertEqual(dna['summary']['largest_transaction'], Decimal('100.00'))
        self.assertEqual(dna['summary']['smallest_transaction'], Decimal('100.00'))
        self.assertEqual(dna['summary']['categories_used'], 1)
        self.assertIsNone(dna['money_leak'])
        self.assertIsNone(dna['large_transaction'])
        self.assertEqual(len(dna['repeated_spending']), 0)
        self.assertIsNone(dna['monthly_pattern'])

    def test_zero_amount_expense(self):
        Expense.objects.create(user=self.user, amount=Decimal('0.00'), category='Food', description='Desc', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        # Assuming we return None if total_spending == 0, wait, I removed that! Let me check if I removed `if total_spending == Decimal('0.00'): return None`.
        # Ah, looking at the previous view_file/replace, I did NOT remove `if total_spending == Decimal('0.00'): return None`!
        # Wait, if I didn't remove it, then returning None is expected.
        self.assertIsNone(dna)

    def test_many_categories(self):
        for i in range(10):
            Expense.objects.create(user=self.user, amount=Decimal('10.00'), category=f'Cat{i}', description='Desc', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertEqual(dna['summary']['categories_used'], 10)

    def test_duplicate_descriptions_capitalization(self):
        Expense.objects.create(user=self.user, amount=Decimal('10.00'), category='Food', description='apple', date=datetime.date(2023, 1, 1))
        Expense.objects.create(user=self.user, amount=Decimal('10.00'), category='Food', description='Apple', date=datetime.date(2023, 1, 1))
        Expense.objects.create(user=self.user, amount=Decimal('10.00'), category='Food', description=' APPLE ', date=datetime.date(2023, 1, 1))
        
        dna = generate_spending_dna(self.user)
        self.assertEqual(len(dna['repeated_spending']), 1)
        self.assertEqual(dna['repeated_spending'][0]['count'], 3)

    def test_blank_descriptions(self):
        Expense.objects.create(user=self.user, amount=Decimal('10.00'), category='Food', description='', date=datetime.date(2023, 1, 1))
        Expense.objects.create(user=self.user, amount=Decimal('10.00'), category='Food', description='  ', date=datetime.date(2023, 1, 1))
        
        dna = generate_spending_dna(self.user)
        self.assertEqual(len(dna['repeated_spending']), 0)

    def test_all_expenses_below_300(self):
        for i in range(6):
            Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description=f'D{i}', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['money_leak'])
        self.assertEqual(dna['money_leak']['count'], 6)
        self.assertEqual(dna['money_leak']['share_percentage'], Decimal('100.0'))

    def test_no_expenses_below_300(self):
        for i in range(6):
            Expense.objects.create(user=self.user, amount=Decimal('500.00'), category='Food', description=f'D{i}', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertIsNone(dna['money_leak'])

    def test_exactly_300(self):
        for i in range(5):
            Expense.objects.create(user=self.user, amount=Decimal('300.00'), category='Food', description=f'D{i}', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['money_leak'])
        self.assertEqual(dna['money_leak']['count'], 5)

    def test_jan_dec_boundaries(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='D', date=datetime.date(2023, 12, 31))
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='D', date=datetime.date(2024, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertIsNotNone(dna['monthly_pattern'])
        self.assertEqual(len(dna['monthly_pattern']), 2)
        self.assertEqual(dna['monthly_pattern'][0]['month'], 'December 2023')
        self.assertEqual(dna['monthly_pattern'][1]['month'], 'January 2024')

    def test_decimal_amounts(self):
        Expense.objects.create(user=self.user, amount=Decimal('199.99'), category='Food', description='D1', date=datetime.date(2023, 1, 1))
        Expense.objects.create(user=self.user, amount=Decimal('199.99'), category='Food', description='D2', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertEqual(dna['summary']['total_spending'], Decimal('399.98'))
        self.assertEqual(dna['summary']['average_transaction'], Decimal('199.99'))

    def test_data_isolation(self):
        Expense.objects.create(user=self.user, amount=Decimal('100.00'), category='Food', description='D1', date=datetime.date(2023, 1, 1))
        Expense.objects.create(user=self.other_user, amount=Decimal('9999.00'), category='Shopping', description='Big', date=datetime.date(2023, 1, 1))
        dna = generate_spending_dna(self.user)
        self.assertEqual(dna['summary']['total_spending'], Decimal('100.00'))
        self.assertEqual(dna['summary']['largest_transaction'], Decimal('100.00'))
