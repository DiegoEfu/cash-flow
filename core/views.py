from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Sum
from django.db import transaction
from django.forms.forms import BaseForm
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, ListView
from django.contrib import messages
from django.views.generic import View

from decimal import Decimal

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

class GeneralListView(LoginRequiredMixin, ListView):
    model = None  # This attribute must be overridden in the subclass
    template_name = '' # must be overridden by a partial
    paginate_by = 5 # pagination used by default

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter_class()
        return context

    def paginate_queryset(self, queryset, page_size):
        return super().paginate_queryset(queryset.qs, page_size)

## ACCOUNT VIEWS
class AccountListView(GeneralListView):
    model = Account
    template_name = 'partials/accounts/accounts.html'
    filter_class = AccountFilter

    def get_queryset(self) -> QuerySet[Any]:
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.filter(owner=self.request.user)
        )
    
    def post(self, request):
        if(request.POST.get('pk')):
            try:
                with transaction.atomic():
                    account = Account.objects.get(pk=request.POST['pk'])
                    account.visible = False
                    account.save()

            except Account.DoesNotExist:
                messages.error(request, "The account you are trying to delete does not exist.")
                return redirect("/accounts")

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
        return render(self.request, 'partials/accounts/form.html', {'form': form})
    
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

# TRANSACTIONS VIEWS
class TransactionListView(GeneralListView):
    model = Transaction
    template_name = 'partials/transactions/transactions.html'
    filter_class = TransactionFilter
    paginate_by = 15
    
    def get_queryset(self) -> QuerySet[Any]:
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.filter(from_account=Account.objects.get(pk=self.kwargs['pk']))
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        return context

class TransactionCreation(FormView):
    form_class = TransactionForm
    template_name = 'partials/transactions/form.html'

    def form_valid(self, form: TransactionForm) -> HttpResponse:
        with transaction.atomic():
            account = Account.objects.get(pk=self.kwargs['pk'])

            form.instance.from_account = account
            form.save()

            if not form.instance.hold:
                amount = form.instance.amount if form.instance.transaction_type == '+' else -form.instance.amount

                account.current_balance += amount
                account.save()

            messages.success(self.request, "The Transaction has been made successfully.")

        return redirect(f"/transactions/{account.pk}")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        messages.error(self.request, "An error has ocurred while creating your Transaction.")
        print(form.errors)
        return render(self.request, 'partials/transactions/form.html', {'form': form, 'account': Account.objects.get(pk=self.kwargs['pk'])})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        return context

class TransactionUpdate(TransactionCreation):
    def form_valid(self, form: Any):
        with transaction.atomic():
            transaction_instance = Transaction.objects.get(pk=self.kwargs['pk'])
            form = self.form_class(form.data, instance=transaction_instance)
            account = transaction_instance.from_account

            if not transaction_instance.hold:
                amount = transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount
                account.current_balance -= amount
                account.save()

            if not form.instance.hold:
                amount = Decimal(form.data['amount'])
                amount = amount if form.data['transaction_type'] == '+' else -amount
                account.current_balance += amount
                account.save()

            form.save()

            messages.success(self.request, "The Transaction has been updated successfully.")

        return redirect(f"/transactions/{account.pk}")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        return render(self.request, '/transactions/form.html', {'form': form, 'edit': True})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        instance = Transaction.objects.get(pk=self.kwargs['pk'])
        return {**super().get_context_data(**kwargs), 'account': instance.from_account, 'form': self.form_class(instance=instance), 'edit': True}

class TransactionDelete(LoginRequiredMixin, View):
    model = Transaction

    def delete(self, request, *args, **kwargs):
        transaction_instance = self.model.objects.get(pk=self.kwargs['pk'])
        account = transaction_instance.from_account

        if(account.owner != request.user):
            return HttpResponseForbidden()
        
        with transaction.atomic():
            if not transaction_instance.hold:
                amount = transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount
                account.current_balance -= amount
                account.save()

            transaction_instance.delete()

        return render(request, 'partials/transactions/updated-balance.html', {'account': account})

# TAGS VIEWS
class TagCreation(LoginRequiredMixin, FormView):
    form_class = TagForm
    template_name = 'partials/tags/form.html'

    def form_valid(self, form: Any) -> HttpResponse:
        with transaction.atomic():
            form.instance.user = self.request.user
            form.save()

        messages.success(self.request, "The tag has been created successfully.")

        return redirect("/tags")

class TagListView(GeneralListView):
    model = Tag
    template_name = 'partials/tags/list.html'
    filter_class = TagFilter

    def get_queryset(self):
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.filter(user=self.request.user)
                .prefetch_related('money_tags')
                .annotate(assigned=Sum('money_tags__amount'))
        )

class TagUpdate(LoginRequiredMixin, FormView):
    form_class = TagForm
    template_name = 'partials/tags/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Tag.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def form_valid(self, form: Any):
        form.save()
        messages.success(self.request, "The tag has been updated successfully.")

        return redirect("/tags")

    def form_invalid(self, form: Any) -> HttpResponse:
        return render(self.request, 'partials/tags/form.html', {'form': form, 'edit': True})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['edit'] = True
        self.tag = Tag.objects.get(pk=self.kwargs['pk'], user=self.request.user)
        return context

class TagDelete(LoginRequiredMixin, View):
    model = Tag

    def delete(self, request, *args, **kwargs):
        instance = self.model.objects.get(pk=self.kwargs['pk'])

        if(instance.user != request.user):
            return HttpResponseForbidden()
        
        with transaction.atomic():
            instance.delete()

        return render(request, 'partials/transactions/updated-balance.html')

class TagAssignment(LoginRequiredMixin, View):
    template_name = 'partials/tags/assignment_form.html'

    def get_forms(self, account):
        tags = Tag.objects.filter(user=self.request.user)
        totals = MoneyTag.objects.filter(tag__in=tags.values_list('id', flat=True)).annotate(total=Sum('amount'))
        forms = []

        with transaction.atomic():
            for tag in tags:
                instance = MoneyTag.objects \
                .get_or_create(
                    tag=tag, account=account
                )[0]

                forms.append({
                    'form': MoneyTagForm(instance=instance, prefix=tag.pk),
                    'total': totals.get(tag=tag).total
                })

        return forms
    
    def get_context_data(self, **kwargs):
        context = {}
        context['account'] = Account.objects.select_related('currency').get(pk=self.kwargs['pk'])
        context['forms'] = self.get_forms(context['account'])
        context['totals'] = {
            'total_account': sum(MoneyTag.objects.filter(account=context['account']).values_list('amount', flat=True)),
            'total_tags': sum(MoneyTag.objects.filter(tag__in=Tag.objects.filter(user=self.request.user)).values_list('amount', flat=True))
        }
        context['totals']['not_assigned'] = context['account'].current_balance - context['totals']['total_tags']
        return context

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        pass

def logout_view(request):
    logout(request)
    return redirect("/login")