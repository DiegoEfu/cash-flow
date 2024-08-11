from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AbstractUser

from .mixins import StrAsNameMixin
from .managers import *

import datetime
import uuid

# TODO: Use API https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json

# Create your models here.

class Currency(models.Model):
    """
    """

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
    
    class Meta:
        ordering = ("code",)

class User(AbstractUser):
    main_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, default=1)
    username = None
    USERNAME_FIELD = 'email'
    email = models.EmailField(unique=True)
    REQUIRED_FIELDS = []

class ExchangeRate(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    date = models.DateField(auto_now=True)
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=2)
    active = models.BooleanField(default=True)
    currency1 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency1_exchange_rate")
    currency2 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency2_exchange_rate")

class Account(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length = 100)
    opening_time = models.DateTimeField(auto_now=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, blank=True, validators=[MinValueValidator(0.0)])
    visible = models.BooleanField(default=True, blank=True)

    class Meta:
        ordering = ("name",)

class Tag(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

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
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.CharField(max_length=100, null=True, blank=True)
    hold = models.BooleanField(default=False)
    date = models.DateTimeField(default=datetime.datetime.now())
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transaction_from_account", null=True)
    exchange_rate = models.ForeignKey(ExchangeRate, on_delete=models.PROTECT, null=True, blank=True)
    opening = models.BooleanField(default=False, blank=True)

    objects = TransactionQuerySet.as_manager()

    def __str__(self) -> str:
        return f"Transaction ({self.transaction_type}) of {self.amount} on {self.date} on account {self.account} owned by {self.account.user}."
    
    class Meta:
        ordering = ("-date",)
    
class MoneyTag(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    active = models.BooleanField(default=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="accounts_money_tags")
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, related_name="money_tags")

class HistoricBalance(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(auto_now=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)