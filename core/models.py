from django.db import models
from django.contrib.auth.models import AbstractUser
import datetime
import uuid

# Create your models here.
class StrAsNameMixin():
    """
    Simple mixin to return the name of the object when casted to str type. 
    """
    def __str__(self) -> str:
        return self.name

class User(AbstractUser):
    pass

class Currency(models.Model):
    """
    """

    name = models.CharField(max_length=50, unique=True)

class Account(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    user = models.ForeignObject(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=50)
    opened_on = models.DateTimeField(auto_now=True)

class TransactionTag(StrAsNameMixin, models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    user = models.ForeignObject(User, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = "Categories"

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
    reference = models.CharField(max_length=20, null=True, blank=True)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    category = models.ForeignKey(TransactionTag, on_delete=models.PROTECT)
    description = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateTimeField(default=datetime.datetime.now())
    account = models.ForeignKey(Account, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"Transaction ({self.transaction_type}) of {self.amount} on {self.date} on account {self.account} owned by {self.account.user}."