from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Sum, F, Prefetch, Case, When
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, ListView
from django.contrib import messages
from django.views.generic import View
from .utils import find_transaction_fitting_exchange_rate, convert_all, convert_each, calculate_percentage, get_new_exchange_rate

from decimal import Decimal
import datetime

from .forms import *
from .models import *
from .filters import *
from .constants import *

# Create your views here.

def welcome_view(request):
    def make_context():
        if(request.user.is_authenticated):
            exchange_rates = ExchangeRate.objects.filter(active=True) \
                .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
             
            amounts_balance = Account.objects.filter(owner=request.user, visible=True).annotate(total=Sum('current_balance')).values('currency','total')
            
            amounts = Transaction.objects.select_related('from_account__currency').filter(
                hold=False, internal=False, 
            ).annotate(total=Sum('amount'), currency=F('from_account__currency')
            ).values('total', 'transaction_type', 'opening', 'currency')
            
            amounts_income = [transaction for transaction in amounts if transaction['transaction_type'] == '+' and not transaction['opening']]
            amounts_expense = [transaction for transaction in amounts if transaction['transaction_type'] == '-']

            total_balance = convert_all(amounts_balance, request.user.main_currency.pk, exchange_rates)
            total_income = convert_all(amounts_income, request.user.main_currency.pk, exchange_rates)
            total_expense = convert_all(amounts_expense, request.user.main_currency.pk, exchange_rates)

            previous_month = datetime.date.today().month - 1 if datetime.date.today().month > 1 else 12
            year = datetime.date.today().year if previous_month != 12 else datetime.date.today().year - 1

            balances_last_month = HistoricBalance.objects.filter(account__owner=request.user, month=previous_month, year=year)
            if(balances_last_month.exists() > 0):
                balances_last_month = balances_last_month.annotate(total=F('balance'), currency=F('account__currency')).values('total','currency')
                balance_last_month = convert_all(balances_last_month, request.user.main_currency.pk, exchange_rates)
            else:
                balance_last_month = 0
            
            transactions = Transaction.objects.select_related('from_account__currency').filter(hold=False, date__month=previous_month) \
                .annotate(total=Sum('amount'), currency=F('from_account__currency')) \
                .values('total', 'currency', 'transaction_type', 'opening')
            
            incomes_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '+' and not transaction['opening']]
            income_last_month = convert_all(incomes_last_month, request.user.main_currency.pk, exchange_rates)

            expenses_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '-']
            expense_last_month = convert_all(expenses_last_month, request.user.main_currency.pk, exchange_rates)

            percentage_balance = calculate_percentage(total_balance, balance_last_month)
            percentage_income = calculate_percentage(total_income, income_last_month)
            percentage_expense = calculate_percentage(total_expense, expense_last_month)

            return {
                'balance': round(total_balance, 2),
                'current_month_income': round(total_income, 2),
                'current_month_expense': round(total_expense, 2),

                'percentage_balance': percentage_balance,
                'percentage_income': percentage_income,
                'percentage_expense': percentage_expense
            }
        else:
            return {}

    context = make_context()

    get_new_exchange_rate() # Ideally change this to a cron job, but it's a paid feature in PythonAnywhere so I'm leaving it as it is for now

    return render(request, 'welcome.html', context=context)

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

            MainCurrency.objects.create(user=form.instance, currency=Currency.objects.get(pk=self.request.POST['main_currency']))

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
        queryset = self.model.objects.filter(owner=self.request.user, visible=True).select_related('currency')
        filterx= self.filter_class(
            self.request.GET,
            queryset=queryset
        )

        return filterx
    
    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        context['object_list'] = [{'account': account, 'mc_bal': convert_all([{'total': account.current_balance, 'currency': account.currency.pk}], self.request.user.main_currency.currency.pk, exchange_rates)} for account in context['object_list']]
        
        return context
    
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

            if(form.instance.current_balance > 0):
                Transaction.objects.create(
                    from_account=form.instance,
                    amount=form.instance.current_balance,
                    transaction_type='+',
                    description=OPENING_BALANCE_DESCRIPTION,
                    date=form.instance.opening_time,
                    opening=True,
                    internal=True,
                    exchange_rate=find_transaction_fitting_exchange_rate(form.instance.currency, self.request.user.main_currency.currency, form.instance.opening_time)
                )
            
            HistoricBalance.objects.create(account=form.instance, balance=form.instance.current_balance, date=form.instance.opening_time)

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
    paginate_by = 10

    def update_tags(self, account):
        with transaction.atomic():
            tags = Tag.objects.filter(user=self.request.user)

            for tag in tags:
                MoneyTag.objects \
                    .get_or_create(
                        tag=tag, account=account
                    )[0]
    
    def get_queryset(self) -> QuerySet[Any]:
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.select_related(
                'exchange_rate'
            ).filter(
                from_account=Account.objects.get(pk=self.kwargs['pk']),
            ).annotate(
                previous_value=F('amount') / F('exchange_rate__exchange_rate'),
            )
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        account = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        
        context['account'] = account
        context['mc_account_balance'] = convert_all([{'total': account.current_balance, 'currency': account.currency.pk}], self.request.user.main_currency.currency.pk, exchange_rates)
        context['object_list'] = [{
                'mc_amount': convert_all([
                    {
                        'total': transaction.amount, 
                        'currency': account.currency.pk,
                    }],  self.request.user.main_currency.currency.pk, exchange_rates), 
                'fixed_pk': str(transaction.pk).replace('-', ''),
                'transaction': transaction,
            } for transaction in context['object_list']]
        
        self.update_tags(account)

        return context

class TransactionCreation(FormView):
    form_class = TransactionForm
    template_name = 'partials/transactions/form.html'

    def form_valid(self, form: TransactionForm) -> HttpResponse:
        with transaction.atomic():
            account = Account.objects.get(pk=self.kwargs['pk'])

            form.instance.from_account = account
            form.instance.exchange_rate = find_transaction_fitting_exchange_rate(account.currency, self.request.user.main_currency.currency, form.instance.date)
            form.save()

            if not form.instance.hold:
                amount = form.instance.amount if form.instance.transaction_type == '+' else -form.instance.amount

                account.current_balance += amount
                account.save()

                if(form.instance.tag):
                    tag = MoneyTag.objects.get(tag=self.request.POST['tag'], account=account)

                    if self.request.POST['transaction_type'] == '+':
                        tag.amount += amount
                        tag.save()
                    else:
                        money_tags = MoneyTag.objects.filter(tag=tag.tag, amount__gt=0).order_by(
                            Case(
                                When(account=account, then=0),
                                default=1
                            )
                        )
                        for money_tag in money_tags:
                            converted_amount = -convert_each([{'total': amount, 'currency': account.currency.pk}], money_tag.account.currency.pk)[0]['total']
                            subtracted_amount = min(money_tag.amount, converted_amount)
                            money_tag.amount -= subtracted_amount
                            money_tag.save()
                            amount -= convert_each([{'total': subtracted_amount, 'currency': money_tag.account.currency.pk}], account.currency.pk)[0]['total']

                historic_balance, created = HistoricBalance.objects.get_or_create(
                    account=account,
                    month=form.instance.date.month,
                    year=form.instance.date.year,
                    defaults={'balance': account.current_balance}
                )

                if created:
                    historic_balance.balance = account.current_balance
                else:
                    historic_balance.balance += amount
                historic_balance.save()

            messages.success(self.request, "The Transaction has been made successfully.")            

        return redirect(f"/transactions/{account.pk}")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        messages.error(self.request, "An error has ocurred while creating your Transaction.")
        print(form.errors)
        return render(self.request, 'partials/transactions/form.html', {'form': form, 'account': Account.objects.get(pk=self.kwargs['pk'])})
    
    def get_form(self, form_class = None):
        form = super().get_form(self.form_class)
        form.initial['date'] = datetime.datetime.now()
        return form

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        context['tags'] = MoneyTag.objects.filter(account=context['account']).select_related('tag').all()
        return context

class TransactionUpdate(TransactionCreation):
    def form_valid(self, form: Any):
        with transaction.atomic():
            transaction_instance = Transaction.objects.get(pk=self.kwargs['pk'])
            form = self.form_class(form.data, form.files, instance=transaction_instance)
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

                if(form.instance.tag):
                    if transaction_instance.tag:
                        old_tag = MoneyTag.objects.get(tag=transaction_instance.tag, account=account)
                        old_tag.amount -= transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount
                        old_tag.save()

                    new_tag = MoneyTag.objects.get(tag__pk=self.request.POST['tag'], account=account)
                    new_tag.amount += amount if form.instance.transaction_type == '+' else -amount
                    new_tag.save()
                
                historic_balance, created = HistoricBalance.objects.get_or_create(
                    account=account,
                    month=form.instance.date.month,
                    year=form.instance.date.year,
                    defaults={'balance': account.current_balance}
                )

                if created:
                    historic_balance.balance = account.current_balance
                else:
                    historic_balance.balance += amount - (transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount)
                historic_balance.save()

            form.save()

            messages.success(self.request, "The Transaction has been updated successfully.")

        return redirect(f"/transactions/{account.pk}")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        print(form.errors)
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

                if transaction_instance.tag:
                    tag = MoneyTag.objects.get(tag=transaction_instance.tag, account=account)
                    tag.amount -= amount if transaction_instance.transaction_type == '+' else -amount
                    tag.save()

                historic_balance, created = HistoricBalance.objects.get_or_create(
                    account=account,
                    month=transaction_instance.date.month,
                    year=transaction_instance.date.year,
                    defaults={'balance': account.current_balance}
                )

                if created:
                    historic_balance.balance = account.current_balance
                else:
                    historic_balance.balance -= amount
                historic_balance.save()

            transaction_instance.delete()

        return render(request, 'partials/transactions/updated-balance.html', {'account': account})

class GeneralTransactionListView(GeneralListView):
    model = Transaction
    template_name = 'partials/transactions/transactions_general.html'
    filter_class = TransactionFilter
    paginate_by = 15
    
    def get_queryset(self) -> QuerySet[Any]:
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.select_related(
                'from_account', 'from_account__currency'
            ).filter(from_account__owner=self.request.user)
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        amounts_balance = Account.objects.annotate(total=Sum('current_balance')).values('currency','total')
        main_currency = self.request.user.main_currency.currency

        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        context['object_list'] = [{'mc_amount': convert_all([{'total': transaction.amount, 'currency': transaction.from_account.currency.pk}], main_currency.pk, exchange_rates), 'transaction': transaction} for transaction in context['object_list']]
        context['current_balance']  = round(convert_all(amounts_balance, main_currency.pk), 2)
        context['main_currency']  = main_currency.code
        return context

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
    paginate_by = 20

    def get_queryset(self):
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.filter(user=self.request.user)
                .prefetch_related(Prefetch('money_tags', 
                                           queryset=MoneyTag.objects
                                                .select_related(
                                                    'account', 
                                                    'account__currency'
                                                )
                                            )
                ).annotate(assigned=Sum('money_tags__amount'))
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
       
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        alt = []
        for tag in context['object_list']:
            total = 0
            
            for money_tag in tag.money_tags.all():
                total += convert_all([{'total': money_tag.amount, 'currency': money_tag.account.currency.pk}], self.request.user.main_currency.currency.pk, exchange_rates)
            
            alt.append({
                'tag': tag,
                'total': total
            })

        context['object_list'] = alt        
        return context

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
            instance.money_tags.all().delete()
            instance.delete()

        return render(request, 'partials/transactions/updated-balance.html')

class TagAssignment(LoginRequiredMixin, View):
    template_name = 'partials/tags/assignment_form.html'

    def get_forms(self, account, request = None):
        tags = Tag.objects.filter(user=self.request.user)
        totals = MoneyTag.objects.filter(tag__in=tags.values_list('id', flat=True))
        forms = []

        with transaction.atomic():
            for tag in tags:
                instance = MoneyTag.objects.get(
                    tag=tag, account=account
                )

                forms.append({
                    'form': MoneyTagForm(request, instance=instance, prefix=tag.pk),
                    'total': sum([
                        x['total'] for x in 
                        convert_each(totals.filter(tag=tag).annotate(total=F('amount'), currency=F('account__currency'))
                                         .values('total', 'currency'), account.currency.pk)
                    ])
                })

        return forms
    
    def get_context_data(self, request = None):
        context = {}
        context['account'] = Account.objects.select_related('currency').get(pk=self.kwargs['pk'])
        context['forms'] = self.get_forms(context['account'], request)
        context['totals'] = {
            'total_account': sum([ x['total'] for x in convert_each(
                MoneyTag.objects.filter(account=context['account']).annotate(
                    total=F('amount'), currency=F('account__currency__pk')
                ).values('total', 'currency'), 
                context['account'].currency.pk
            )]),
            'total_tags': sum([ x['total'] for x in convert_each(
                    MoneyTag.objects.filter(tag__in=Tag.objects.filter(user=self.request.user)).annotate(
                        total=F('amount'), currency=F('account__currency__pk')
                    ).values('total', 'currency'),
                    context['account'].currency.pk
                )]
            )
        }
        context['totals']['not_assigned'] = context['account'].current_balance - context['totals']['total_account']
        return context

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, pk):
        account = Account.objects.get(pk=pk)
        tags = Tag.objects.filter(user=self.request.user)
        forms = []

        with transaction.atomic():
            for tag in tags:
                money_tag = tag.money_tags.get(account=account)
                if f"{tag.pk}-id" in request.POST:
                    form = MoneyTagForm(request.POST, instance=money_tag, prefix=tag.pk)
                    if form.is_valid():
                        form.save()
                    else:
                        messages.error(request, "An error has occurred while assigning your tags.")
                        return render(request, self.template_name, self.get_context_data(request.POST))
                else:
                    money_tag.amount = 0
                    money_tag.save()

        return redirect(f"/transactions/{account.pk}/")

def logout_view(request):
    logout(request)
    return redirect("/login")

def graph_by_accounts(request):
    accounts = AccountFilter(request.GET, queryset=Account.objects.filter(visible=True, owner=request.user).select_related('currency')).qs.annotate(total=F('current_balance')).values('name', 'currency', 'total')
    accounts = convert_each(accounts, request.user.main_currency.pk)

    return JsonResponse(accounts, safe=False)

def graph_by_tags(request):
    accounts = AccountFilter(request.GET, queryset=MoneyTag.objects.filter(account__visible=True, account__owner=request.user).select_related('currency')).qs.annotate(total=F('current_balance')).values('name', 'currency', 'total')
    accounts = convert_each(accounts, request.user.main_currency.pk)

    return JsonResponse(accounts, safe=False)