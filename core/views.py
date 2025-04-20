from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Sum, F, Prefetch, Case, When, Q, Value
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, ListView
from django.contrib import messages
from django.views.generic import View
from django.forms.models import model_to_dict

from .utils import find_transaction_fitting_exchange_rate, convert_all, convert_each, convert_all_transactions_amounts_to_main_currency_precisely, calculate_percentage, get_new_exchange_rate

from decimal import Decimal
import datetime

from .forms import *
from .models import *
from .filters import *
from .constants import *

# Create your views here.

from django.views import View

class WelcomeView(View):
    template_name = 'welcome.html'

    def get_context_data(self, request):
        if request.user.is_authenticated:
            exchange_rates = ExchangeRate.objects.filter(active=True) \
                .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
             
            amounts_balance = Account.objects.filter(owner=request.user, visible=True).annotate(total=Sum('current_balance')).values('currency', 'total')
            
            amounts = Transaction.objects.select_related('from_account__currency').filter(
                Q(from_account__owner=request.user) | Q(user=request.user),
                hold=False, internal=False, date__month=datetime.date.today().month, date__year=datetime.date.today().year
            ).exclude(from_account__visible=False).values('from_account', 'transaction_type', 'opening'
            ).annotate(total=Sum('amount'), currency=F('from_account__currency')
            ).values('total', 'exchange_rate', 'amount', 'currency', 'transaction_type', 'opening', 'date', from_account__currency=Case(
                When(from_account__currency__isnull=False, then=F('from_account__currency')),
                When(from_account__currency__isnull=True, then=Value(request.user.main_currency.pk)),
            ))
            amounts_income = [transaction for transaction in amounts if transaction['transaction_type'] == '+' and not transaction['opening']]
            amounts_expense = [transaction for transaction in amounts if transaction['transaction_type'] == '-']

            total_balance = convert_all(amounts_balance, request.user.main_currency.pk, exchange_rates)
            total_income = convert_all_transactions_amounts_to_main_currency_precisely(amounts_income, request.user.main_currency.pk)
            total_expense = convert_all_transactions_amounts_to_main_currency_precisely(amounts_expense, request.user.main_currency.pk)

            previous_month = datetime.date.today().month - 1 if datetime.date.today().month > 1 else 12
            year = datetime.date.today().year if previous_month != 12 else datetime.date.today().year - 1

            balances_last_month = HistoricBalance.objects.filter(account__owner=request.user, month=previous_month, year=year)
            if balances_last_month.exists():
                balances_last_month = balances_last_month.annotate(total=F('balance'), currency=F('account__currency')).values('total', 'currency')
                balance_last_month = convert_all(balances_last_month, request.user.main_currency.pk, exchange_rates)
            else:
                balance_last_month = 0
            
            transactions = Transaction.objects.select_related('from_account__currency').filter(Q(from_account__owner=request.user) | Q(user=request.user), hold=False, date__year=year, date__month=previous_month, internal=False) \
                .annotate(total=Sum('amount'), currency=F('from_account__currency')) \
                .values('total', 'exchange_rate', 'amount', 'currency', 'transaction_type', 'opening', 'date', from_account__currency=Case(
                When(from_account__currency__isnull=False, then=F('from_account__currency')),
                When(from_account__currency__isnull=True, then=Value(request.user.main_currency.pk)),
            ))
            
            incomes_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '+' and not transaction['opening']]
            income_last_month = convert_all_transactions_amounts_to_main_currency_precisely(incomes_last_month, request.user.main_currency.pk)

            expenses_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '-']
            expense_last_month = convert_all_transactions_amounts_to_main_currency_precisely(expenses_last_month, request.user.main_currency.pk)

            percentage_balance = calculate_percentage(total_balance, balance_last_month)
            percentage_income = calculate_percentage(total_income, income_last_month)
            percentage_expense = calculate_percentage(total_expense, expense_last_month)

            visible_accounts_count = Account.objects.filter(owner=request.user, visible=True).count()
            current_historic_balances_count = HistoricBalance.objects.filter(
                account__owner=request.user, 
                account__visible=True,
                month=previous_month, 
                year=year
            ).count()

            if visible_accounts_count != current_historic_balances_count:
                with transaction.atomic():
                    existing_account_ids = HistoricBalance.objects.filter(
                        account__owner=request.user,
                        account__visible=True,
                        month=datetime.date.today().month,
                        year=datetime.date.today().year
                    ).values_list('account_id', flat=True)
                    
                    missing_accounts = Account.objects.filter(
                        owner=request.user, 
                        visible=True
                    ).exclude(id__in=existing_account_ids)
                    
                    for account in missing_accounts:
                        HistoricBalance.objects.create(
                            account=account,
                            balance=account.current_balance,
                            month=datetime.date.today().month,
                            year=datetime.date.today().year
                        )

            return {
                    'balance': round(total_balance, 2),
                    'current_month_income': round(total_income, 2),
                    'current_month_expense': round(total_expense, 2),
                    'balance_last_month': round(balance_last_month, 2),
                    'income_last_month': round(income_last_month, 2),
                    'expense_last_month': round(expense_last_month, 2),
                    'percentage_balance': percentage_balance,
                    'percentage_income': percentage_income,
                    'percentage_expense': percentage_expense
            }

    def update_balances(self, request, *args, **kwargs):
        current_month = datetime.date.today().month
        current_year = datetime.date.today().year
        visible_accounts = Account.objects.filter(owner=request.user, visible=True)
        historic_balances = HistoricBalance.objects.filter(
            account__owner=request.user, 
            account__visible=True,
            month=current_month, 
            year=current_year
        )

        if historic_balances.count() != visible_accounts.count():
            for account in visible_accounts:
                HistoricBalance.objects.get_or_create(
                    account=account,
                    month=current_month,
                    year=current_year,
                    defaults={'balance': account.current_balance}
                )

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(request)
        
        if(request.user.is_authenticated):
            get_new_exchange_rate()  # Ideally change this to a cron job, but it's a paid feature in PythonAnywhere so I'm leaving it as it is for now
            self.update_balances(request)
            
        return render(request, self.template_name, context=context)

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
            form.instance.username = form.instance.email
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
        queryset = self.model.objects.filter(owner=self.request.user, visible=True).prefetch_related(
            'accounts_money_tags', 'transaction_from_account'
        ).select_related('currency')

        search_params = self.request.GET or self.request.session.get('previous_search')
        self.request.session['previous_search'] = search_params
        return self.filter_class(search_params, queryset=queryset)
    
    def get_current_month(self):
        return datetime.date.today().month
    
    def get_current_year(self):
        return datetime.date.today().year
    
    def get_previous_month(self):
        current_month = datetime.date.today().month
        return current_month - 1 if current_month > 1 else 12
    
    def get_previous_year(self):
        current_month = self.get_current_month()
        current_year = self.get_current_year()
        return current_year if current_month != 1 else current_year - 1
    
    def aggregate_currency(self, account, transaction_type, current_year=datetime.date.today().year, current_month=datetime.date.today().month):
            return account.transaction_from_account.filter(
                date__year=current_year, date__month=current_month, transaction_type=transaction_type
            ).aggregate(total=Sum('amount'))['total'] or 0
    
    def get_object_list(self, object_list, exchange_rates):
        result = []
        for account in object_list:
            monthly_income_total = self.aggregate_currency(account, '+')
            monthly_expense_total = self.aggregate_currency(account, '-')
            assigned_total = account.accounts_money_tags.aggregate(total=Sum('amount'))['total'] or 0
            current_balance_total = account.current_balance
            previous_month = self.get_previous_month()
            year = self.get_previous_year()
         
            monthly_income = convert_all(
                [{'total': monthly_income_total, 'currency': account.currency.pk}],
                self.request.user.main_currency.currency.pk, exchange_rates
            )
            monthly_expense = convert_all(
                [{'total': monthly_expense_total, 'currency': account.currency.pk}],
                self.request.user.main_currency.currency.pk, exchange_rates
            )
            assigned = convert_all(
                [{'total': assigned_total, 'currency': account.currency.pk}],
                self.request.user.main_currency.currency.pk, exchange_rates
            )
            mc_bal = convert_all(
                [{'total': current_balance_total, 'currency': account.currency.pk}],
                self.request.user.main_currency.currency.pk, exchange_rates
            )
            not_assigned = {
                'account_currency': current_balance_total - assigned_total,
                'main_currency': mc_bal - assigned
            }
            
            try:
                start_balance_ac = account.account_historic_balance.get(year=year, month=previous_month).balance
            except Exception as e:
                start_balance_ac = account.transaction_from_account.get(opening=True).amount if account.transaction_from_account.filter(opening=True).exists() else 0
            
            start_balance_mc = convert_all(
                [{'total': start_balance_ac, 'currency': account.currency.pk}],
                self.request.user.main_currency.currency.pk, exchange_rates
            )

            result.append({
                'account': account,
                'monthly_income': {'account_currency': monthly_income_total, 'main_currency': monthly_income},
                'monthly_expenses': {'account_currency': monthly_expense_total, 'main_currency': monthly_expense},
                'assigned': {'account_currency': assigned_total, 'main_currency': assigned},
                'start_balance': {'account_currency': start_balance_ac, 'main_currency': start_balance_mc},
                'not_assigned': not_assigned,
                'mc_bal': mc_bal
            })

        return result
    
    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')

        object_list = self.get_object_list(context['object_list'], exchange_rates)
        
        context['object_list'] = object_list

        previous_search = self.request.session.get('previous_search')
        if previous_search:
            context['filter'] = self.filter_class(previous_search)
        
        if(self.request.GET != {}):
            self.request.session['previous_search'] = self.request.GET
        
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

class AccountSumaryTableView(AccountListView):
    template_name = 'partials/accounts/summary.html'
    paginate_by = None

    def get_context_data(self, **kwargs: Any):
        qs = self.get_queryset().qs
        context = {}
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        
        object_list = self.get_object_list(qs, exchange_rates)

        total_income = sum([item['monthly_income']['main_currency'] for item in object_list])
        total_expense = sum([item['monthly_expenses']['main_currency'] for item in object_list])
        total_balance = sum([item['mc_bal'] for item in object_list])
        total_assigned = sum([item['assigned']['main_currency'] for item in object_list])
        total_not_assigned = sum([item['not_assigned']['main_currency'] for item in object_list])

        context['total_in'] = total_income
        context['total_out'] = total_expense
        context['total_balance'] = total_balance
        context['total_assigned'] = total_assigned
        context['total_not_assigned'] = total_not_assigned

        return context

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
            
            HistoricBalance.objects.create(account=form.instance, balance=form.instance.current_balance, year=form.instance.opening_time.year, month=form.instance.opening_time.month)

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
                'exchange_rate', 'tag'
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
        main_pk = self.request.user.main_currency.currency.pk
        
        context['account'] = account
        context['mc_account_balance'] = convert_all([{'total': account.current_balance, 'currency': account.currency.pk}], main_pk, exchange_rates)
        context['object_list'] = [{
                'mc_amount': convert_each([{
                'total': transaction.amount, 
                'currency': transaction.from_account.currency.pk if transaction.from_account else main_pk
            }], main_pk, [model_to_dict(transaction.exchange_rate)])[0]['total'] if transaction.exchange_rate and transaction.from_account else convert_all([{
                'total': transaction.amount, 
                'currency': transaction.from_account.currency.pk if transaction.from_account else main_pk
            }], main_pk, exchange_rates), 
                'fixed_pk': str(transaction.pk).replace('-', ''),
                'transaction': transaction,
            } for transaction in context['object_list']]
        
        previous_month = datetime.datetime.now().month - 1 if datetime.datetime.now().month > 1 else 12
        year = datetime.datetime.now().year if previous_month != 12 else datetime.datetime.now().year - 1
        previous_balance = HistoricBalance.objects.filter(account=account, month=previous_month, year=year).values('balance').first()
        if previous_balance is None:
            previous_balance = 0
        else:
            previous_balance = previous_balance['balance']

        context['previous_balance'] = previous_balance
        context['previous_balance_mc'] = convert_all([{'total': previous_balance, 'currency': account.currency.pk}], main_pk, exchange_rates)
        
        assigned_total = account.accounts_money_tags.aggregate(total=Sum('amount'))['total'] or 0
        context['assigned'] = assigned_total
        context['assigned_mc'] = convert_all([{'total': assigned_total, 'currency': account.currency.pk}], main_pk, exchange_rates)
        
        not_assigned_total = account.current_balance - assigned_total
        context['not_assigned'] = not_assigned_total
        context['not_assigned_mc'] = convert_all([{'total': not_assigned_total, 'currency': account.currency.pk}], main_pk, exchange_rates)
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
                        self.update_tags_and_accounts(amount, account, tag)

                historic_balance, created = HistoricBalance.objects.get_or_create(
                    account=account,
                    month=form.instance.date.month,
                    year=form.instance.date.year,
                    defaults={'balance': account.current_balance}
                )
                
                historic_balance.balance = account.current_balance
                historic_balance.save()

            messages.success(self.request, "The Transaction has been made successfully.")            

        return redirect(f"/transactions/{account.pk}")

    def update_tags_and_accounts(self, amount, account, tag):
        money_tags = MoneyTag.objects.filter(tag=tag.tag).filter(
            Q(account=account) | Q(amount__gt=0)
        ).order_by(
            Case(
                When(account=account, then=0),
                default=1
            )
        )

        amount = abs(amount)
        accounts = []
        tags_to_subtract_from = []
        for money_tag in money_tags:
            converted_amount = convert_each([{'total': amount, 'currency': account.currency.pk}], money_tag.account.currency.pk)[0]['total']
            subtracted_amount = min(money_tag.amount, converted_amount)
            money_tag.amount -= subtracted_amount
            money_tag.save()

            if(account.pk != money_tag.account.pk): 
                accounts.append(money_tag.account)
            
            amount -= convert_each([{'total': subtracted_amount, 'currency': money_tag.account.currency.pk}], account.currency.pk)[0]['total']
                            
            if(amount > 0):
                current_tags_total = MoneyTag.objects.filter(account=account).aggregate(total=Sum('amount'))['total'] or 0
                unassigned_money = max(0, money_tag.account.current_balance - current_tags_total)
                amount -= min(amount, unassigned_money)

            if amount and money_tag.account.pk == account.pk: # If money was not enough to be subtracted from the current account
                ref_amount = amount
                for mt in account.accounts_money_tags.all():
                    if ref_amount > 0:
                        subtracted_amount = min(mt.amount, ref_amount)
                        tags_to_subtract_from.append({'tag': mt.tag, 'amount': subtracted_amount})
                        mt.amount -= subtracted_amount
                        mt.save()
                        print(f"Subtracting {subtracted_amount} from tag {mt.tag}")
                        ref_amount -= subtracted_amount
                    else:
                        break
                            
            if(amount <= 0):
                break

        # This bit is for when the money was not enough to be subtracted from the current account, and needs to be compensated into other accounts
        if(len(tags_to_subtract_from) > 0):                        
            for account in accounts:
                availability = account.current_balance
                availability -= MoneyTag.objects.filter(account=account).aggregate(total=Sum('amount'))['total'] or 0

                if(availability > 0):
                    for i,tag in enumerate(tags_to_subtract_from):
                        converted_tag_amount = convert_each([{'total': tag['amount'], 'currency': tag['tag'].money_tags.get(account=account).account.currency.pk}], account.currency.pk)[0]['total']
                        if converted_tag_amount > 0: # Currency: current account currency
                            exchange_rate = tag['amount'] / converted_tag_amount
                            mt = MoneyTag.objects.get(tag=tag['tag'], account=account)
                            compensation = min(availability, converted_tag_amount)
                            mt.amount += compensation
                            tags_to_subtract_from[i]['amount'] -= compensation * exchange_rate
                            availability -= compensation
                            mt.save()

                            print(f"Adding {compensation} to tag {tag['tag']} on account {account} to compensate for lack of money")

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
            form.instance.exchange_rate = find_transaction_fitting_exchange_rate(account.currency, self.request.user.main_currency.currency, form.instance.date)

            if not transaction_instance.hold: # If the transaction is not on hold, we need to update the balance
                amount = transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount
                account.current_balance -= amount
                account.save()

            if not self.request.POST.get('hold'):
                amount = Decimal(form.data['amount'])
                amount = amount if form.data['transaction_type'] == '+' else -amount
                account.current_balance += amount
                account.save()

                if(self.request.POST.get('tag')):
                    if transaction_instance.tag:
                        old_tag = MoneyTag.objects.get(tag=transaction_instance.tag, account=account)
                        old_tag.amount -= transaction_instance.amount if transaction_instance.transaction_type == '+' else -transaction_instance.amount
                        old_tag.amount = max(0, old_tag.amount)
                        old_tag.save()

                    amount = abs(amount)  
                    new_tag = MoneyTag.objects.get(tag__pk=self.request.POST['tag'], account=account)                  
                    if(form.data['transaction_type'] == '-'):
                        self.update_tags_and_accounts(amount, account, new_tag)
                    else:                      
                        new_tag.amount += amount
                        new_tag.save()
                
                historic_balance, created = HistoricBalance.objects.get_or_create(
                    account=account,
                    month=form.instance.date.month,
                    year=form.instance.date.year,
                    defaults={'balance': account.current_balance}
                )

                historic_balance.balance = account.current_balance
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
                    tag.amount -= amount
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
                'from_account', 'from_account__currency', 'tag', 'exchange_rate'
            ).filter(Q(from_account__owner=self.request.user) | Q(user=self.request.user))
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        amounts_balance = Account.objects.filter(owner=self.request.user, visible=True).annotate(total=Sum('current_balance')).values('currency','total')
        main_currency = self.request.user.main_currency.currency
        
        if not self.request.GET.get('date_from'):
            context['filter'] = self.filter_class({
                'date_from': datetime.datetime.now() - datetime.timedelta(days=30),
            })

        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        context['object_list'] = [{
            'mc_amount': convert_each([{
                'total': transaction.amount, 
                'currency': transaction.from_account.currency.pk if transaction.from_account else transaction.user.main_currency.currency.pk
            }], main_currency.pk, [model_to_dict(transaction.exchange_rate)])[0]['total'] if transaction.exchange_rate and transaction.from_account else convert_all([{
                'total': transaction.amount, 
                'currency': transaction.from_account.currency.pk if transaction.from_account else transaction.user.main_currency.currency.pk
            }], main_currency.pk, exchange_rates), 
            'transaction': transaction} for transaction in context['object_list']]
        context['current_balance']  = round(convert_all(amounts_balance, main_currency.pk), 2)
        
        qs = self.get_queryset().qs
        transactions = qs.values('from_account__currency').annotate(total=Sum('amount')).values('total', 'from_account__currency', 'transaction_type', 'hold')
        context['total_in'] = round(convert_all([{'total': transaction['total'], 'currency': transaction['from_account__currency']} for transaction in transactions.filter(transaction_type='+', hold=False)], main_currency.pk, exchange_rates), 2)
        context['total_out'] = round(convert_all([{'total': transaction['total'], 'currency': transaction['from_account__currency']} for transaction in transactions.filter(transaction_type='-', hold=False)], main_currency.pk, exchange_rates), 2)
        context['total_hold'] = round(convert_all([{'total': transaction['total'], 'currency': transaction['from_account__currency']} for transaction in transactions.filter(hold=True)], main_currency.pk, exchange_rates), 2)
        context['total_cash_flow'] = context['total_in'] - context['total_out']

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
                ).annotate(assigned=Sum('money_tags__amount')).order_by('-assigned')
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accounts"] = self.get_assigned_balance_per_account()
        context["current_balance"] = self.get_current_balance()
        context["assigned_balance"] = self.get_assigned_balance()
        context["not_assigned_balance"] = context["current_balance"] - context["assigned_balance"]
        context["object_list"] = self.get_object_list(context["object_list"])
        return context
    
    def get_assigned_balance_per_account(self):
        accounts_money_tags = Account.objects.filter(
            owner=self.request.user, visible=True
        ).prefetch_related('accounts_money_tags').select_related('currency').annotate(
            total=Coalesce(Sum('accounts_money_tags__amount'), Decimal(0))
        ).order_by('name')
        alt = []
        for account in accounts_money_tags:
            assigned, balance = [x['total'] for x in convert_each(
                [{'total': account.total, 'currency': account.currency.pk}, {'total': account.current_balance, 'currency': account.currency.pk}], 
                 self.request.user.main_currency.currency.pk
            )]

            assigned = assigned if assigned != None else 0

            alt.append({'account': account,
            'balance': {
                'main_currency': balance,
                'account_currency': account.current_balance
            },                       
            'assigned': {
                'main_currency': assigned,
                'account_currency': account.total
            }, 'not_assigned': {
                'main_currency': balance - assigned,
                'account_currency': account.current_balance - account.total                
            }})
        
        return alt
    
    def get_current_balance(self):
        accounts_balance = Account.objects.filter(owner=self.request.user, visible=True).annotate(total=Sum('current_balance')).values('currency','total')
        return convert_all(accounts_balance, self.request.user.main_currency.currency.pk)
    
    def get_assigned_balance(self):
        assigned_balance = MoneyTag.objects.filter(account__owner=self.request.user, account__visible=True).annotate(total=Sum('amount'), currency=F('account__currency__pk')).values('currency','total')
        return convert_all(assigned_balance, self.request.user.main_currency.currency.pk)
    
    def get_object_list(self, object_list):
        exchange_rates = ExchangeRate.objects.filter(active=True).values('currency1', 'currency2', 'exchange_rate')
        alt = []
        for tag in object_list:
            total = 0
            
            for money_tag in tag.money_tags.all():
                total += convert_all([{'total': money_tag.amount, 'currency': money_tag.account.currency.pk}], self.request.user.main_currency.currency.pk, exchange_rates)
            
            alt.append({
                'tag': tag,
                'total': total
            })
        return alt

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
    accounts = sorted(
        convert_each(
            accounts, request.user.main_currency.pk
        ), 
        key=lambda x: x['total'], 
        reverse=True
    )

    return JsonResponse(accounts, safe=False)

def graph_by_tags(request):
    accounts = AccountFilter(request.GET, queryset=MoneyTag.objects.filter(account__visible=True, account__owner=request.user).select_related('currency')).qs.annotate(total=F('current_balance')).values('name', 'currency', 'total')
    accounts = convert_each(accounts, request.user.main_currency.pk)

    return JsonResponse(accounts, safe=False)

def daily_balance_graph(request, pk):
    account = Account.objects.get(pk=pk)
    today = datetime.date.today()

    balances = []    
    total_difference = 0
    current_balance = account.current_balance
    for n in range(30):
        day = today - datetime.timedelta(days=n)
        current_balance += total_difference
        balances.append({
            'date': day,
            'balance': current_balance
        })

        total_difference = sum(
            -amount if transaction_type == '+' else +amount 
            for amount, transaction_type in 
            account.transaction_from_account.filter(date__day=day.day, date__month=day.month, date__year=day.year).values_list('amount', 'transaction_type')
        )
    balances.reverse()

    return JsonResponse(balances, safe=False)

def tag_graph_by_account(request, pk):
    account = Account.objects.get(pk=pk)
    
    balances = []
    total_assigned = 0
    money_tags = MoneyTag.objects.filter(account=account).values('tag__name', 'amount') 
    for tag in money_tags:
        balance = tag['amount']
        name = tag['tag__name']
        if balance > 0:
            balances.append({'tag': name, 'balance': balance})

    available_money = account.current_balance - sum([tag['amount'] for tag in money_tags])
    if available_money > 0:
        balances.append({'tag': "AVAILABLE", 'balance': available_money})

    balances.sort(key=lambda x: x['balance'], reverse=True)

    return JsonResponse(balances, safe=False)

# Password Views

class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = 'partials/user_management/change_password.html'
    form_class = ChangePasswordForm

    def get(self, request):
        form = self.get_form()
        return render(request, self.template_name, {'form': form})

    def form_valid(self, form):
        user = self.request.user
        if user.check_password(form.cleaned_data['current_password']):
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(self.request, 'Password changed successfully! Now log in again')
            
            response = HttpResponse(status=201)
            response['HX-Location'] = reverse('login')
            return response
        else:
            messages.error(self.request, 'The current password you introduced is not correct.')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if form.cleaned_data['new_password'] != form.cleaned_data['repeat_password']:
            messages.error(self.request, 'The new passwords do not match.')
    
        return render(self.request, self.template_name, {'form': form})

class HistoricBalanceListView(GeneralListView):
    filter_class = HistoricBalanceFilter
    model = HistoricBalance
    template_name = 'partials/accounts/historic-balance.html'
    paginate_by = 100

    def get_queryset(self):
        current_year = datetime.date.today().year
        current_month = datetime.date.today().month
        
        query_dict = self.request.GET.copy()
        
        if 'year' not in query_dict:
            query_dict['year'] = str(current_year)
        if 'month' not in query_dict:
            query_dict['month'] = str(current_month)
        
        return self.filter_class(
            query_dict,
            request=self.request,
            queryset=self.model.objects.select_related('account').filter(account__owner=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.GET.get('year') and self.request.GET.get('month') :
            exchange_rates = ExchangeRate.objects.filter(
                date__year=int(self.request.GET.get('year', datetime.date.today().year)),
                date__month=int(self.request.GET.get('month', datetime.date.today().month))
            ).order_by(
                'currency1', 'currency2', '-date'
            ).values('currency1', 'currency2', 'exchange_rate')

            unique_exchange_rates = {}
            for rate in exchange_rates:
                key = (rate['currency1'], rate['currency2'])
                if key not in unique_exchange_rates:
                    unique_exchange_rates[key] = rate

            exchange_rates = list(unique_exchange_rates.values())
        else:
            exchange_rates = ExchangeRate.objects.filter(active=True).order_by(
                'currency1', 'currency2', '-date'
            ).values('currency1', 'currency2', 'exchange_rate')
        
        context['object_list'] = context['object_list'].annotate(
            total_in=Coalesce(Sum('account__transaction_from_account__amount', output_field=DecimalField(), filter=Q(account__transaction_from_account__transaction_type='+', account__transaction_from_account__date__year=F('year'), account__transaction_from_account__date__month=F('month'), account__transaction_from_account__hold=False)), Value(Decimal(0))),
            total_out=Coalesce(Sum('account__transaction_from_account__amount', output_field=DecimalField(), filter=Q(account__transaction_from_account__transaction_type='-', account__transaction_from_account__date__year=F('year'), account__transaction_from_account__date__month=F('month'), account__transaction_from_account__hold=False)), Value(Decimal(0))),
            total_internal_in=Coalesce(Sum('account__transaction_from_account__amount', output_field=DecimalField(), filter=Q(account__transaction_from_account__transaction_type='+', account__transaction_from_account__internal=True, account__transaction_from_account__date__year=F('year'), account__transaction_from_account__date__month=F('month'), account__transaction_from_account__hold=False, account__transaction_from_account__from_account__owner=F('account__owner'))), Value(Decimal(0))),
            total_internal_out=Coalesce(Sum('account__transaction_from_account__amount', output_field=DecimalField(), filter=Q(account__transaction_from_account__transaction_type='-', account__transaction_from_account__internal=True, account__transaction_from_account__date__year=F('year'), account__transaction_from_account__date__month=F('month'), account__transaction_from_account__hold=False, account__transaction_from_account__from_account__owner=F('account__owner'))), Value(Decimal(0))),
            total_external_in=F('total_in') - F('total_internal_in'),
            total_external_out=F('total_out') - F('total_internal_out')
        )

        context['filter'] = self.filter_class(
            self.request.GET if self.request.GET else {
                'year': str(datetime.date.today().year),
                'month': str(datetime.date.today().month)
            },
            request=self.request
        )

        context['object_list'] = [
            {
                'balance': convert_all(
                    [{'total': obj.balance, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_in': convert_all(
                    [{'total': obj.total_in, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_out': convert_all(
                    [{'total': obj.total_out, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_internal_in': convert_all(
                    [{'total': obj.total_internal_in, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_internal_out': convert_all(
                    [{'total': obj.total_internal_out, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_external_in': convert_all(
                    [{'total': obj.total_external_in, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'total_external_out': convert_all(
                    [{'total': obj.total_external_out, 'currency': obj.account.currency.pk}],
                    self.request.user.main_currency.currency.pk, exchange_rates
                ),
                'obj': obj
            } for obj in context['object_list']
        ]

        # add the sum of all the expenses and income of the transactions that do not have an account
        # please assume these are in main currency
        transactions_without_account = Transaction.objects.filter(
            user=self.request.user,
            from_account__isnull=True,
            date__year=int(self.request.GET.get('year', datetime.date.today().year)),
            date__month=int(self.request.GET.get('month', datetime.date.today().month))
        ).aggregate(
            total_in=Sum(
                Case(
                    When(transaction_type='+', then='amount'),
                    default=Decimal(0.00)
                ),
                output_field=DecimalField()
            ),
            total_out=Sum(
                Case(
                    When(transaction_type='-', then='amount'),
                    default=Decimal(0.00)
                ),
                output_field=DecimalField()
            )
        )

        context['totals'] = {
            'total_balance': sum(obj['balance'] for obj in context['object_list']),
            'total_in': sum(obj['total_in'] for obj in context['object_list']),
            'total_out': sum(obj['total_out'] for obj in context['object_list']),
            'total_internal_in': sum(obj['total_internal_in'] for obj in context['object_list']),
            'total_internal_out': sum(obj['total_internal_out'] for obj in context['object_list']),
            'total_external_in': sum(obj['total_external_in'] for obj in context['object_list']),
            'total_external_out': sum(obj['total_external_out'] for obj in context['object_list'])
        }

        context['totals']['total_in'] += transactions_without_account['total_in'] or 0
        context['totals']['total_out'] += transactions_without_account['total_out'] or 0
        context['totals']['total_external_in'] += transactions_without_account['total_in'] or 0
        context['totals']['total_external_out'] += transactions_without_account['total_out'] or 0
        context['exchange_diffs'] = transactions_without_account 

        context['total_cash_flow'] = context['totals']['total_in'] - context['totals']['total_out']

        return context
    
class TransferCreationView(TransactionCreation):
    template_name = 'partials/transactions/transfer_form.html'
    form_class = TransferForm

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'form': self.get_form(), 'account': Account.objects.get(pk=self.kwargs['pk'])})
    
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                super().post(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, str(e))
            return redirect("/accounts")
        
        return redirect("/transactions", pk=self.kwargs['pk'])
    
def transfer_update(request, pk):
    from_account = Account.objects.get(pk=pk)

    to_account = Account.objects.get(pk=request.GET.get('to_account'))
    to_acc_currency = to_account.currency

    # sent and conversion
    sent_money = Decimal(request.GET.get('amount', 0))
    converted_sent = convert_all(
        [{'total': sent_money, 'currency': from_account.currency.pk}],
        to_account.currency.pk
    )
    
    # if there is a received in the request, keep it, else assume its 0
    rec_amount = Decimal(request.GET.get('received_amount', 0))

    if(rec_amount != None and rec_amount != '' and rec_amount != 0): 
        print(f"Rec amount: {rec_amount}", "\nConverted sent:", converted_sent)
        discounted_received = converted_sent - rec_amount
    else:
        rec_amount = converted_sent
        discounted_received = 0
    
    final_from = from_account.current_balance - sent_money
    final_to = to_account.current_balance + rec_amount

    fee = 0
    if(discounted_received):
        fee = convert_all(
            [{'total': discounted_received, 'currency': to_account.currency.pk}],
            from_account.currency.pk
        )

    effective_exchange_rate = sent_money / rec_amount

    return render(request, 'partials/transactions/transfer_update.html', {
        'from_account': from_account,
        'sent_money': sent_money,
        'to_account': to_account,
        'to_acc_currency': to_acc_currency,
        'rec_amount': rec_amount,
        'fee': fee,
        'final_from': final_from,
        'final_to': final_to,
        'effective_exchange_rate': effective_exchange_rate,
        'discounted_received': discounted_received
    })