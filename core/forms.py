"""
core/forms.py

This file contains forms for the core application.
It includes forms for creating new users, updating existing users, creating transactions,
and updating existing transactions.

"""

from core.models import *
from django import forms
from django.contrib.auth.hashers import make_password 
from .validators import file_size_validator

class UserForm(forms.ModelForm):
    """
    Summary:
    A form for creating new users.

    Properties:
    username (CharField): The username for the new user.
    email (EmailField): The email address for the new user.
    password (CharField): The password for the new user.
    repeat_password (CharField): The repeated password for the new user.
    main_currency (ModelChoiceField): The main currency for the new user.

    Methods:
    clean_repeat_password(self): Cleans the repeated password by comparing it with the password.
    clean_password(self): Cleans the password by encrypting it.
    clean_username(self): Cleans the username by checking if it already exists.
    """
    repeat_password = forms.CharField(min_length=8)
    main_currency = forms.ModelChoiceField(queryset=Currency.objects.all(), required=True)

    def clean_repeat_password(self):
        password = self.data['password'].replace(" ", "")
        repeat = self.data['repeat_password'].replace(" ", "")

        if(password != repeat):
            raise forms.ValidationError("The password and the repeated password must be equal.")
        
        return repeat
    
    def clean_password(self):
        password = self.data['password'].replace(" ", "")

        if(len(password) < 8):
            raise forms.ValidationError("The password must be at least 8 characters long.")
                
        password = make_password(password)

        return password
    
    def clean_username(self):
        username = self.cleaned_data['username']
        user = get_user_model().objects.filter(username=username).first()
        if user:
            raise forms.ValidationError("Username already exists.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data['email']
        user = get_user_model().objects.filter(email=email).first()
        if user:
            raise forms.ValidationError("Email already exists.")
        return email

    class Meta:
        model = get_user_model()
        exclude = ('id', 'username', 'date_joined')

class AccountForm(forms.ModelForm):
    """
    Summary:
    A form for creating and updating accounts.

    Properties:
    - Meta (class): Defines the model and fields to be excluded for the form.

    Methods:
    None specific to this class, as it inherits from Django's ModelForm which provides form handling functionality.
    """

    class Meta:
        model = Account
        exclude = ('id', 'opening_time', 'owner', 'visible')

class TransactionForm(forms.ModelForm):
    """
    Summary:
    A form for creating and updating transactions.

    Properties:
    amount (DecimalField): The amount of the transaction.
    description (CharField): The description of the transaction.
    transaction_type (ChoiceField): The type of the transaction, either '+' (income) or '-' (expense).
    date (DateField): The date of the transaction.
    voucher (FileField): The voucher for the transaction, with file size and extension validation.

    Methods:
    clean_amount(self): Cleans the amount by validating if it is positive.
    clean_voucher(self): Cleans the voucher by validating the file size and extension.

    Meta (class): Defines the model and fields to be excluded for the form.
    """
    voucher = forms.FileField(required=False, validators=[FileExtensionValidator(allowed_extensions=['pdf','jpg','png']), file_size_validator])

    class Meta:
        model = Transaction
        exclude = ('id', 'from_account', 'exchange_rate', 'user')

class TagForm(forms.ModelForm):
    """
    Summary:
    A form for creating and updating tags associated with user transactions.

    Properties:
    - Meta (class): Defines the model and fields to be excluded for the form.

    Methods:
    None specific to this class, as it inherits from Django's ModelForm which provides form handling functionality.
    """

    class Meta:
        model = Tag
        exclude = ('id', 'user')

class MoneyTagForm(forms.ModelForm):
    """
    Summary:
    A form for creating and updating money tags associated with specific accounts and tags.

    Properties:
    - Meta (class): Defines the model and fields to be excluded for the form.

    Methods:
    None specific to this class, as it inherits from Django's ModelForm which provides form handling functionality.
    """

    class Meta:
        model = MoneyTag
        exclude = ('account','tag')

class ChangePasswordForm(forms.Form):
    """
    Summary:
    A form for changing the user's password.

    Properties:
    current_password (CharField): The user's current password.
    new_password (CharField): The user's new password.
    repeat_password (CharField): The user's new password repeated for confirmation.

    Methods:
    clean_current_password(self): Cleans the current_password field by checking if the provided password matches the user's current password.

    Other:
    This form is used to change the user's password.
    """
    current_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Current Password",
        min_length=8
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        label="New Password",
        min_length=8
    )
    repeat_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Repeat New Password",
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        repeat_password = cleaned_data.get('repeat_password')

        if new_password != repeat_password:
            raise forms.ValidationError("The new passwords must match.")

        return cleaned_data
    
class TransferForm(TransactionForm):
    """
    Summary:
    This form is a TransactionForm with additional fields for the account to transfer money to and the tag to deduce the money from.

    Properties:
    to_account (ChoiceField): The account to transfer money to.
    deduce_from_tag (ChoiceField): The tag to deduce the money from.

    Methods:
    __init__(self, request = None, *args, **kwargs): Initializes the form with the request and the account and tag choices.

    Other:
    This form is used to create a transfer transaction.
    """
    def __init__(self, request = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['to_account'].choices = Account.objects.filter(owner=request['user'], visible=True).exclude(pk=request.get('pk')).values_list('pk', 'name') if request else []
        self.fields['deduce_from_tag'].choices = Tag.objects.filter(user=request['user']).exclude(pk=request.get('pk')).values_list('pk', 'name') if request else []

    to_account = forms.ChoiceField(required=True)
    received_amount = forms.FloatField(required=True)
    deduce_from_tag = forms.ChoiceField(required=True)

# This form is used to create a transfer transaction.
money_tag_formset = forms.modelformset_factory(MoneyTag, form=MoneyTagForm)