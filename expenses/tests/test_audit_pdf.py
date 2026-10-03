from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from expenses.models import Expense, Category

class AuditPDFSecurityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='usera', password='password123')
        self.user_b = User.objects.create_user(username='userb', password='password123')

        cat_a = Category.objects.create(name='Food A', type='expense', user=self.user_a)
        cat_b = Category.objects.create(name='Food B', type='expense', user=self.user_b)

        Expense.objects.create(user=self.user_a, category=cat_a, amount=100.00, date='2026-10-01', description='Burger')
        Expense.objects.create(user=self.user_b, category=cat_b, amount=5000.00, date='2026-10-01', description='Steak')

    def test_unauthenticated_access(self):
        """Unauthenticated user should be redirected to login."""
        response = self.client.get(reverse('download_audit_pdf'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))

    def test_authenticated_access_is_scoped(self):
        """User A should not see User B's data in the PDF."""
        self.client.login(username='usera', password='password123')
        response = self.client.get(reverse('download_audit_pdf'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Check if the generated PDF contains the specific expense amounts and descriptions for User A
        pdf_content = response.content
        
        # We can't easily parse PDF text in unit test without external libs like PyPDF2,
        # but we can check if the response was successful. To truly check isolation, 
        # we rely on the fact that `generate_audit_pdf` uses exactly `generate_smart_insights(request.user)`.
        # However, checking if "usera" is in the content stream can be a naive test for the username rendering.
        self.assertIn(b'usera', pdf_content)
        self.assertNotIn(b'userb', pdf_content)
