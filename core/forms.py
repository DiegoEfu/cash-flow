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

money_tag_formset = forms.modelformset_factory(MoneyTag, form=MoneyTagForm)