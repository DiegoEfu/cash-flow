from typing import Any
from core.models import *
from django import forms
from django.contrib.auth.hashers import make_password 

class UserForm(forms.ModelForm):
    repeat_password = forms.CharField(min_length=8)

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
        
        print(password)
        
        password = make_password(password)

        return password

    class Meta:
        model = User
        exclude = ('id', 'username', 'date_joined')

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        exclude = ('id', 'opening_time', 'owner', 'visible')

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        exclude = ('id', 'from_account', 'to_account')

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        exclude = ('id', 'user')
