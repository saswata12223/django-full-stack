from django.db import models
from django.contrib.auth.models import User

class MoneyProfile(models.Model):
    MODE_CHOICES = [
        ('School Student', 'School Student'),
        ('College Student', 'College Student'),
        ('Working Professional', 'Working Professional'),
        ('Freelancer', 'Freelancer'),
        ('Business Owner', 'Business Owner'),
        ('Family / Household', 'Family / Household'),
        ('Retired / Senior', 'Retired / Senior'),
        ('Other', 'Other'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='money_profile')
    mode = models.CharField(max_length=50, choices=MODE_CHOICES, default='Other')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.mode}"

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('Food', 'Food'),
        ('Travel', 'Travel'),
        ('Shopping', 'Shopping'),
        ('Bills', 'Bills'),
        ('Education', 'Education'),
        ('Entertainment', 'Entertainment'),
        ('Other', 'Other'),
    ]

    INTENT_CHOICES = [
        ('Need', 'Need'),
        ('Want', 'Want'),
        ('Goal', 'Goal'),
        ('Social', 'Social'),
        ('Emergency', 'Emergency'),
        ('Recurring', 'Recurring'),
        ('Work', 'Work'),
        ('Business', 'Business'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, default='Other')
    description = models.TextField()
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"


class Income(models.Model):
    INCOME_TYPE_CHOICES = [
        ('Salary', 'Salary'),
        ('Freelance', 'Freelance'),
        ('Business', 'Business'),
        ('Allowance', 'Allowance'),
        ('Gift', 'Gift'),
        ('Interest', 'Interest'),
        ('Refund', 'Refund'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    income_type = models.CharField(max_length=20, choices=INCOME_TYPE_CHOICES, default='Other')
    source = models.CharField(max_length=100)
    description = models.TextField()
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.amount}"

class SpendingExperiment(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=Expense.CATEGORY_CHOICES)
    baseline_amount = models.DecimalField(max_digits=10, decimal_places=2)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category} Experiment ({self.status})"

class RecurringTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('Expense', 'Expense'),
        ('Income', 'Income'),
    ]
    FREQUENCY_CHOICES = [
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Yearly', 'Yearly'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    next_expected_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.description} ({self.frequency})"

class Goal(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('Paused', 'Paused'),
        ('Cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.status}"

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            raw = (self.current_amount / self.target_amount) * 100
            return min(int(raw), 100)
        return 0

    @property
    def remaining_amount(self):
        # Local import to avoid circular dependency if Decimal was not imported
        from decimal import Decimal
        return max(Decimal('0.00'), self.target_amount - self.current_amount)
