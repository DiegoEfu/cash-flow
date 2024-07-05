from typing import Any
from django.db.models.query import QuerySet
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, ListView
from django.contrib import messages

from .forms import *
from .models import *
from .filters import *

# Create your views here.

def welcome_view(request):
    return render(request, 'welcome.html')

class LoginView(LoginView):
    template_name = 'login.html'

    def get_success_url(self) -> str:
        return '/'
    
    def get(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        if(request.user.is_authenticated):
            return redirect('/')
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        response = super().post(request, *args, **kwargs)

        if(response.status_code == 200 and not request.user.is_authenticated):
            messages.warning(request, "Provided credentials are invalid.")

        return response
    
class SignUpView(FormView):
    template_name = 'signup.html'
    form_class = UserForm
    success_url = "/login"

    def form_valid(self, form: Any) -> HttpResponse:
        with transaction.atomic():
            res = super().form_valid(form)

            form.instance.is_active = True
            form.save()

            messages.success(self.request, "Your account has been created successfully. Now log in.")

        return res
    
    def form_invalid(self, form: Any) -> HttpResponse:
        messages.error(self.request, "An error has ocurred while creating your user.")
        return super().form_invalid(form)

## ACCOUNT VIEWS
class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'partials/accounts/accounts.html'

    def get_queryset(self) -> QuerySet[Any]:
        return self.model.objects.filter(owner = self.request.user, visible=True).select_related("currency")
    
    def post(self, request):
        if(request.POST.get('pk')):
            with transaction.atomic():
                account = Account.objects.get(pk=request.POST['pk'])
                account.visible = False
                account.save()

            messages.warning(request, "The account has been deleted successfully.")
            return redirect("/accounts")

class AccountCreation(LoginRequiredMixin, FormView):
    form_class = AccountForm
    template_name = 'partials/accounts/form.html'
    success_url = "/accounts"

    def form_valid(self, form: Any):
        res = super().form_valid(form)

        with transaction.atomic():
            form.instance.owner = self.request.user
            form.save()

        messages.success(self.request, "The account has been created successfully.")

        return res
    
    def form_invalid(self, form: Any) -> HttpResponse:
        return render(self.request, '/accounts/form.html', {'form': form})
    
class AccountUpdate(AccountCreation):

    def form_valid(self, form: Any):
        with transaction.atomic():
            form = self.form_class(form.data, instance=Account.objects.get(pk=self.kwargs['pk']))
            form.save()

            messages.success(self.request, "The Account has been updated successfully.")

        return redirect("/accounts")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        return render(self.request, '/accounts/form.html', {'form': form, 'edit': True})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        instance = Account.objects.get(pk=self.kwargs['pk'])
        return {**super().get_context_data(**kwargs), 'form': self.form_class(instance=instance), 'edit': True}

def logout_view(request):
    logout(request)
    return redirect("/login")