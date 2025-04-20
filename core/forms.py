from typing import Any
from core.models import *
from django import forms
from django.contrib.auth.hashers import make_password 
from .validators import file_size_validator

class UserForm(forms.ModelForm):
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

    class Meta:
        model = get_user_model()
        exclude = ('id', 'username', 'date_joined')

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        exclude = ('id', 'opening_time', 'owner', 'visible')

class TransactionForm(forms.ModelForm):
    voucher = forms.FileField(required=False, validators=[FileExtensionValidator(allowed_extensions=['pdf','jpg','png']), file_size_validator])

    class Meta:
        model = Transaction
        exclude = ('id', 'from_account', 'exchange_rate', 'user')

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        exclude = ('id', 'user')

class MoneyTagForm(forms.ModelForm):
    class Meta:
        model = MoneyTag
        exclude = ('account','tag')

class ChangePasswordForm(forms.Form):
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
    to_account = forms.ModelChoiceField(queryset=Account.objects.all(), required=True)
    received_amount = forms.FloatField(required=True)
    deduce_from_tag = forms.ModelChoiceField(queryset=Tag.objects.all(), required=True)

money_tag_formset = forms.modelformset_factory(MoneyTag, form=MoneyTagForm)