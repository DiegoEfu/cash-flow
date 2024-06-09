from django.db import models
from django.contrib.auth.models import AbstractUser
from .mixins import StrAsNameMixin
import datetime
import uuid

# TODO: Use API https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json

# Create your models here.

class Currency(models.Model):
    """
    """

    name = models.CharField(max_length=50, unique=True)

class ExchangeRate(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=2)
    active = models.BooleanField(default=True)
    currency1 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency1_exchange_rate")
    currency2 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency2_exchange_rate")

class Account(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    owner = models.ForeignObject(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length = 100)
    opening_time = models.DateTimeField(auto_now=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

class Tag(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    user = models.ForeignObject(User, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = "Tags"

class Transaction(models.Model):
    """
        Summary:

        Inherits From:

        Attributes:

        Functions:
    """

    TRANSACTION_TYPES = (
        ('+','Income'),
        ('-','Expense')
    )

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    reference = models.CharField(max_length=15, null=True, blank=True)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.CharField(max_length=100, null=True, blank=True)
    hold = models.BooleanField(default=False)
    date = models.DateTimeField(default=datetime.datetime.now())
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transaction_from_account", null=True)
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transaction_from_account")

    def __str__(self) -> str:
        return f"Transaction ({self.transaction_type}) of {self.amount} on {self.date} on account {self.account} owned by {self.account.user}."
    
class Fee(StrAsNameMixin, models.Model):
    FEE_TYPES = (
        ('P','Income'),
        ('A','Absolute')
    )

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    transaction_type = models.CharField(max_length=1, choices=FEE_TYPES)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2) 
    fee_maximum = models.DecimalField(max_digits=15, decimal_places=2)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate_used = models.ForeignKey(ExchangeRate, on_delete=models.PROTECT)

class MoneyTag(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    active = models.BooleanField(default=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT)

class HistoricBalance(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(auto_now=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)

class User(AbstractUser):
    main_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, default=1)