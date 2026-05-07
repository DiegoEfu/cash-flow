"""
core/models.py

This file contains the models for the core application.
It includes models for currencies, accounts, tags, transactions, and more.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

from .mixins import StrAsNameMixin
from .managers import *

from django.core.validators import FileExtensionValidator
import uuid

# Create your models here.

class Currency(models.Model):
    """
    Summary:
    Represents a currency with a unique code and name.

    Properties:
    code (str): The unique code for the currency, with a maximum length of 10 characters.
    name (str): The unique name of the currency, with a maximum length of 50 characters.
    ordering (tuple): Specifies the default ordering of currency objects by code.

    Methods:
    __str__() -> str: Returns a string representation of the currency in the format "code - name".
    """

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
    
    class Meta:
        ordering = ("code",)

class MainCurrency(models.Model):
    """
    Summary:
    Represents the main currency for a user, with a unique code and name.

    Properties:
    user (User): The user that this main currency belongs to.
    currency (Currency): The currency that this main currency represents.

    Methods:
    __str__() -> str: Returns a string representation of the main currency in the format "code".

    """
    user = models.OneToOneField(get_user_model(), on_delete=models.PROTECT, null=True, related_name="main_currency")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True)

    def __str__(self) -> str:
        return self.currency.code

class ExchangeRate(models.Model):
    """
    Summary:
    Represents an exchange rate between two currencies, with a unique id, date, exchange rate, and active status.

    Properties:
    id (UUID): The unique id for the exchange rate, with a default value of a uuid4.
    date (Date): The date for which the exchange rate is valid.
    exchange_rate (Decimal): The exchange rate between the two currencies, with a maximum of 15 digits, and 6 decimal places.
    active (Boolean): Indicates whether the exchange rate is active or not.
    currency1 (Currency): The first currency of the exchange rate.
    currency2 (Currency): The second currency of the exchange rate.

    Methods:
    __str__() -> str: Returns a string representation of the exchange rate in the format "date - currency1 - currency2 - exchange_rate".

    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    date = models.DateField()
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, validators=[MinValueValidator(0.000001)])
    active = models.BooleanField(default=True)
    currency1 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency1_exchange_rate")
    currency2 = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency2_exchange_rate")

    def __str__(self):
        return f"{self.exchange_rate} {self.currency1} = 1 {self.currency2} on {self.date}"

    class Meta:
        ordering = ("-date",)

class Account(StrAsNameMixin, models.Model):
    """
    Summary:
    Represents a user's account, with a unique id, currency, owner, name, description, opening time, current balance, and visibility status.

    Properties:
    id (UUID): The unique id for the account, with a default value of a uuid4.
    currency (Currency): The currency for the account.
    owner (User): The owner of the account.
    name (str): The name of the account.
    description (str): The description of the account.
    opening_time (Date): The date and time that the account was opened.
    current_balance (Decimal): The current balance of the account, with a maximum of 15 digits, and 2 decimal places.
    visible (Boolean): Whether the account is visible to the user.

    Methods:
    __str__() -> str: Returns a string representation of the account in the format "name - currency".
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    owner = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, null=True, related_name="accounts")
    name = models.CharField(max_length=50)
    description = models.CharField(max_length = 100)
    opening_time = models.DateTimeField(auto_now=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, blank=True, validators=[MinValueValidator(0.0)])
    visible = models.BooleanField(default=True, blank=True)

    class Meta:
        ordering = ("name",)

class Tag(models.Model):
    """
    Summary:
    Represents a user's tag, with a unique id, name, owner, and monthly goal.

    Properties:
    id (UUID): The unique id for the tag, with a default value of a uuid4.
    name (str): The name of the tag.
    user (User): The owner of the tag.
    month_goal (Decimal): The goal for the total amount of money to be assigned to this tag per month, with a maximum of 15 digits, and 2 decimal places.

    Methods:
    __str__() -> str: Returns a string representation of the tag in the format "name - user".

    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name="tags")
    month_goal = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, blank=True, null=True, validators=[MinValueValidator(0.0)])

    def __str__(self, *args, **kwds):
        return self.name.upper()

    class Meta:
        verbose_name_plural = "Tags"
        ordering = ("name",)

class TagHistory(models.Model):
    """
    Summary:
    Represents a user's tag history, with a unique id, tag, year, month, and amount.

    Properties:
    id (UUID): The unique id for the tag history, with a default value of a uuid4.
    tag (Tag): The tag related to this tag history.
    year (int): The year for which the tag history is valid.
    month (int): The month for which the tag history is valid.
    amount (Decimal): The amount of money assigned to this tag for the given month, with a maximum of 15 digits, and 2 decimal places.

    Methods:
    __str__() -> str: Returns a string representation of the tag history in the format "TagHistory (tag) on (date) by (user)".

    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, related_name="tag_history")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, blank=True, null=True, validators=[MinValueValidator(0.0)])

    def __str__(self) -> str:
        return f"TagHistory ({self.tag}) on {self.date} by {self.user}."
    
    class Meta:
        ordering = ("-year", "-month")

class MoneyTag(models.Model):
    """
    Summary:
    Represents a tag associated with a certain amount of money.

    Properties:
    id (UUID): The unique id for the money tag, with a default value of a uuid4.
    amount (Decimal): The amount of money associated with this tag, with a maximum of 15 digits, and 2 decimal places.
    active (Boolean): Indicates whether the money tag is active or not.
    account (Account): The account that this money tag belongs to.
    tag (Tag): The tag associated with this money tag.

    Methods:
    __str__() -> str: Returns a string representation of the money tag in the format "MoneyTag (tag) of (amount) on account (account) owned by (user)".

    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    active = models.BooleanField(default=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="accounts_money_tags")
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, related_name="money_tags")

    def __str__(self) -> str:
        return f"MoneyTag ({self.tag}) of {self.amount} on account {self.account} owned by {self.account.owner}."
    
    class Meta:
        ordering = ("tag",)

class Transaction(models.Model):
    """
    Summary:
    Represents a transaction of money from one account to another.

    Properties:
    id (UUID): The unique id for the transaction, with a default value of a uuid4.
    reference (str): The reference number of the transaction.
    transaction_type (str): The type of transaction, either '+' for income or '-' for expense.
    amount (Decimal): The amount of money transferred, with a maximum of 15 digits, and 2 decimal places.
    description (str): A description of the transaction.
    date (Date): The date and time at which the transaction was made.
    account (Account): The account that the transaction was made from.
    to_account (Account): The account that the transaction was made to, if applicable.
    exchange (ExchangeRate): The exchange rate used to exchange the currency of the account to the currency of the to_account, if applicable.

    Methods:
    __str__() -> str: Returns a string representation of the transaction in the format "Transaction (reference) for (amount) from (account) to (to_account) on (date)".
    """

    TRANSACTION_TYPES = (
        ('+','Income'),
        ('-','Expense')
    )

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    reference = models.CharField(max_length=15, null=True, blank=True)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.CharField(max_length=100, null=True, blank=True)
    hold = models.BooleanField(default=False)
    date = models.DateTimeField()
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transaction_from_account", null=True)
    exchange_rate = models.ForeignKey(ExchangeRate, on_delete=models.PROTECT, null=True, blank=True)
    opening = models.BooleanField(default=False, blank=True)
    internal = models.BooleanField(default=False, blank=True)
    money_tag = models.ForeignKey(MoneyTag, on_delete=models.PROTECT, null=True, blank=True)
    voucher = models.FileField(blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=['pdf','jpg','png'])], upload_to="vouchers/")
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, null=True, blank=True, related_name="transactions")
    user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, null=True)

    objects = TransactionQuerySet.as_manager()

    def __str__(self) -> str:
        return f"Transaction ({self.transaction_type}) of {self.from_account.currency.code if self.from_account else self.user.main_currency.currency.code} {self.amount} on {self.date} from account {self.from_account} owned by {self.from_account.owner}."
    
    class Meta:
        ordering = ("-date",)

class HistoricBalance(StrAsNameMixin, models.Model):
    """
    Summary:
    Represents the historic balance of an account, tracking monthly balances.

    Properties:
    id (UUID): The unique id for the historic balance entry, with a default value of a uuid4.
    account (Account): The account for which the historic balance is tracked.
    year (int): The year of the balance entry.
    month (int): The month of the balance entry.
    balance (Decimal): The balance amount for the given month, with a maximum of 15 digits, and 2 decimal places.

    Methods:
    __str__() -> str: Returns a string representation of the historic balance in the format "Historic Balance for account (account) on (month/year)".
    """

    MONTHS = (
        (1,"January"),
        (2,"February"),
        (3,"March"),
        (4,"April"),
        (5,"May"),
        (6,"June"),
        (7,"July"),
        (8,"August"),
        (9,"September"),
        (10,"October"),
        (11,"November"),
        (12,"December")
    )

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    month = models.PositiveSmallIntegerField(choices=MONTHS, validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.PositiveSmallIntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="account_historic_balance")

    class Meta:
        ordering = ("-year","-month","account__name")