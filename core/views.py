"""
This file contains views for the core application.
Views are functions that handle HTTP requests and return HTTP responses.
They are the core of the Django framework.

The views here are for the main application, the ones that will be used by normal users.
Most of them are generic views that use Django's generic view system.
"""

from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Sum, F, Prefetch, Case, When, Q, Value
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, ListView
from django.contrib import messages
from django.views.generic import View
from django.forms.models import model_to_dict

from .utils import get_current_exchange_rates, update_tag_history, find_transaction_fitting_exchange_rate, convert_all, convert_each, convert_all_transactions_amounts_to_main_currency_precisely, calculate_percentage, get_new_exchange_rate

from decimal import Decimal
import datetime

from .forms import *
from .models import *
from .filters import *
from .constants import *

# Create your views here.

from django.views import View

class WelcomeView(View):
    """
    Summary:
    This class is a Django View that handles the welcome page for
    authenticated users. It will show a summary of the user's current
    balance, their income and expenses for the current month, and
    their exchange rates.

    Attributes:
    template_name (str): The template to render for the welcome page.

    Methods:
    get_context_data(request)
    get(request)

    """
    template_name = 'welcome.html'

    def get_context_data(self, request):
        """
        Summary:
        This method is used to generate the context data for the welcome page.
        It will gather the user's accounts, their exchange rates, and the total
        amount of money they have in each currency.

        Parameters:
        request - The request object passed to the view.

        Returns:
        context - A dictionary with the user's accounts, exchange rates, and
        total balance in each currency.
        """
        if request.user.is_authenticated:
            exchange_rates = get_current_exchange_rates()
             
            amounts_balance = Account.objects.filter(owner=request.user, visible=True).annotate(total=Sum('current_balance')).values('currency', 'total', 'current_balance')

            main_currency_pk = request.user.main_currency.currency.pk
            
            amounts = Transaction.objects.select_related('from_account__currency').filter(
                Q(from_account__owner=request.user) | Q(user=request.user),
                hold=False, internal=False, date__month=datetime.date.today().month, date__year=datetime.date.today().year
            ).exclude(from_account__visible=False).values('from_account', 'transaction_type', 'opening'
            ).annotate(total=Sum('amount'), currency=F('from_account__currency')
            ).values('total', 'exchange_rate', 'amount', 'currency', 'transaction_type', 'opening', 'date', from_account__currency=Case(
                When(from_account__currency__isnull=False, then=F('from_account__currency')),
                When(from_account__currency__isnull=True, then=Value(main_currency_pk)),
            ))
            amounts_income = [transaction for transaction in amounts if transaction['transaction_type'] == '+' and not transaction['opening']]
            amounts_expense = [transaction for transaction in amounts if transaction['transaction_type'] == '-']

            total_balance = convert_all(amounts_balance, main_currency_pk)
            total_income = convert_all_transactions_amounts_to_main_currency_precisely(amounts_income, main_currency_pk)
            total_expense = convert_all_transactions_amounts_to_main_currency_precisely(amounts_expense, main_currency_pk)

            previous_month = datetime.date.today().month - 1 if datetime.date.today().month > 1 else 12
            year = datetime.date.today().year if previous_month != 12 else datetime.date.today().year - 1

            balances_last_month = HistoricBalance.objects.filter(account__owner=request.user, month=previous_month, year=year)
            if balances_last_month.exists():
                balances_last_month = balances_last_month.annotate(total=F('balance'), currency=F('account__currency')).values('total', 'currency')
                balance_last_month = convert_all(balances_last_month, main_currency_pk, exchange_rates)
            else:
                balance_last_month = 0
            
            transactions = Transaction.objects.select_related('from_account__currency').filter(Q(from_account__owner=request.user) | Q(user=request.user), hold=False, date__year=year, date__month=previous_month, internal=False) \
                .annotate(total=Sum('amount'), currency=F('from_account__currency')) \
                .values('total', 'exchange_rate', 'amount', 'currency', 'transaction_type', 'opening', 'date', from_account__currency=Case(
                When(from_account__currency__isnull=False, then=F('from_account__currency')),
                When(from_account__currency__isnull=True, then=Value(main_currency_pk)),
            ))
            
            incomes_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '+' and not transaction['opening']]
            income_last_month = convert_all_transactions_amounts_to_main_currency_precisely(incomes_last_month, main_currency_pk)

            expenses_last_month = [transaction for transaction in transactions if transaction['transaction_type'] == '-']
            expense_last_month = convert_all_transactions_amounts_to_main_currency_precisely(expenses_last_month, main_currency_pk)

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

            with transaction.atomic():
                for tag in request.user.tags.all():
                    update_tag_history(tag.pk)

            cashflow = total_income - total_expense
            cashflow_last_month = income_last_month - expense_last_month
            percentage_cashflow = calculate_percentage(cashflow, cashflow_last_month)

            return {
                    'balance': round(total_balance, 2),
                    'current_month_income': round(total_income, 2),
                    'current_month_expense': round(total_expense, 2),
                    'balance_last_month': round(balance_last_month, 2),
                    'income_last_month': round(income_last_month, 2),
                    'expense_last_month': round(expense_last_month, 2),
                    'cash_flow': round(cashflow, 2),
                    'cash_flow_last_month': round(cashflow_last_month, 2),
                    'percentage_balance': percentage_balance,
                    'percentage_income': percentage_income,
                    'percentage_expense': percentage_expense,
                    'percentage_cash_flow': percentage_cashflow,
            }

    def update_balances(self, request, *args, **kwargs):
        """
        Updates all the balances of the user and returns a json response with them.

        Parameters:
        request (HttpRequest): The request that triggered the view.

        Returns:
        dict: A dictionary with the following keys:
            - balance (float): The total balance of the user.
            - current_month_income (float): The total income of the current month of the user.
            - current_month_expense (float): The total expense of the current month of the user.
            - balance_last_month (float): The total balance of the last month of the user.
            - income_last_month (float): The total income of the last month of the user.
            - expense_last_month (float): The total expense of the last month of the user.
            - cash_flow (float): The cash flow of the user in the current month.
            - cash_flow_last_month (float): The cash flow of the user in the last month.
            - percentage_balance (str): The percentage change of the balance of the user between the last month and the current month.
            - percentage_income (str): The percentage change of the income of the user between the last month and the current month.
            - percentage_expense (str): The percentage change of the expense of the user between the last month and the current month.
            - percentage_cash_flow (str): The percentage change of the cash flow of the user between the last month and the current month.
        """
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
        """
        Handles GET requests for the home page.

        Parameters:
        request (HttpRequest): The request that triggered the view.

        Returns:
        HttpResponse: The rendered home page.
        """
        context = self.get_context_data(request)
        
        if(request.user.is_authenticated):
            get_new_exchange_rate()  # Ideally change this to a cron job, but it's a paid feature in PythonAnywhere so I'm leaving it as it is for now
            self.update_balances(request)
            
        return render(request, self.template_name, context=context)

class LoginView(LoginView):
    """
    A custom login view for the application.

    Properties:
    - template_name (str): The name of the template to use for the login page.

    Methods:
    - get_success_url (HttpRequest): Returns the URL to redirect to after a successful login.
    - get (HttpRequest, *args, **kwargs): Handles GET requests for the login page.
    """
    template_name = 'login.html'

    def get_success_url(self) -> str:
        """
        Summary:
        Returns the URL to redirect to after a successful login.

        Returns:
        str: The URL to redirect to after a successful login.
        """

        return '/'
    
    def get(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        """
        Summary:
        Handles GET requests for the login page.

        Parameters:
        request (HttpRequest): The request that triggered the view.

        Returns:
        HttpResponse: The rendered login page.
        """
        
        if(request.user.is_authenticated):
            return redirect('/')
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        """
        Summary:
        Handles POST requests for the login page.

        Parameters:
        request (HttpRequest): The request that triggered the view.

        Returns:
        HttpResponse: The rendered login page.
        """
        response = super().post(request, *args, **kwargs)

        if(response.status_code == 200 and not request.user.is_authenticated):
            messages.warning(request, "Provided credentials are invalid.")

        return response
    
class SignUpView(FormView):
    """
    Summary:
    A custom sign up view for the application.

    Properties:
    - template_name (str): The name of the template to use for the sign up page.
    - form_class (Form): The form class to use for the sign up page.
    - success_url (str): The URL to redirect to after a successful sign up.

    Methods:
    - form_valid (Form): Handles valid form submissions and creates a new user.
    - get (HttpRequest, *args, **kwargs): Handles GET requests for the sign up page.
    """
    template_name = 'signup.html'
    form_class = UserForm
    success_url = "/login"

    def form_valid(self, form: Any) -> HttpResponse:
        """
        Summary:
        Handles valid form submissions and creates a new user.

        Parameters:
        form (Form): The form that was submitted.

        Returns:
        HttpResponse: The response to return to the user.
        """
        with transaction.atomic():
            res = super().form_valid(form)

            form.instance.is_active = True
            form.instance.username = form.instance.email
            form.save()

            MainCurrency.objects.create(user=form.instance, currency=Currency.objects.get(pk=self.request.POST['main_currency']))

            messages.success(self.request, "Your account has been created successfully. Now log in.")

        return res
    
    def form_invalid(self, form: Any) -> HttpResponse:
        """
        Summary:
        Handles invalid form submissions and returns the appropriate response.

        Parameters:
        form (Form): The form that was submitted and found to be invalid.

        Returns:
        HttpResponse: The response to return to the user, indicating the form was invalid.
        """

        messages.error(self.request, "An error has ocurred while creating your user.")
        return super().form_invalid(form)

class GeneralListView(LoginRequiredMixin, ListView):
    """
    Summary:
    A base class for ListViews that should be used when the items being listed are related to the user.

    Properties:
    model (Model): The model that should be used to retrieve the list of items.
    template_name (str): The name of the template that should be used to render the ListView.
    paginate_by (int): The number of items to show per page.

    Methods:
    get_context_data(self, **kwargs: Any): Retrieves the context data that should be used to render the ListView, including the list of items and pagination information.
    """
    model = None  # This attribute must be overridden in the subclass
    template_name = '' # must be overridden by a partial
    paginate_by = 5 # pagination used by default

    def get_context_data(self, **kwargs: Any):
        """
        Summary:
        Retrieves the context data that should be used to render the ListView, including the filter class.

        Parameters:
        kwargs (Any): Additional context data that might be needed.

        Returns:
        dict: A dictionary containing the context data for rendering the ListView.
        """

        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter_class()
        return context

    def paginate_queryset(self, queryset, page_size):
        """
        Summary:
        Paginates the queryset with the given page size.

        Parameters:
        queryset (QuerySet): The queryset that should be paginated.
        page_size (int): The number of items to show per page.

        Returns:
        tuple: A tuple containing the paginated queryset and the pagination information.
        """
        return super().paginate_queryset(queryset.qs, page_size)

## ACCOUNT VIEWS
class AccountListView(GeneralListView):
    """
    Summary:
    This view is responsible for listing the user's accounts. It uses the `Account` model to retrieve
    and display all visible accounts belonging to the authenticated user. The view also supports filtering
    and pagination of the account list.

    Properties:
    - model (Model): The Django model `Account` used to retrieve and display account data.
    - template_name (str): The template used to render the list of accounts.
    - filter_class (Type[FilterSet]): The filter class used to filter the accounts based on user input.

    Methods:
    - get_queryset(self) -> QuerySet[Any]: Retrieves the filtered queryset of accounts visible to the user.
    - get_current_month(self): Returns the current month as an integer.
    - get_current_year(self): Returns the current year as an integer.
    - get_previous_month(self): Returns the previous month as an integer.
    - get_previous_year(self): Returns the previous year as an integer.
    - aggregate_currency(self, account, transaction_type, current_year, current_month): Aggregates the total transaction amounts for a specific month and year.
    """

    model = Account
    template_name = 'partials/accounts/accounts.html'
    filter_class = AccountFilter

    def get_queryset(self) -> QuerySet[Any]:
        """
        Summary:
        Retrieves the filtered queryset of accounts that are visible to the authenticated user.

        Parameters:
        None

        Returns:
        QuerySet[Any]: A queryset containing the accounts that match the search parameters and are visible to the user.
        """

        queryset = self.model.objects.filter(owner=self.request.user, visible=True).prefetch_related(
            'accounts_money_tags', 'transaction_from_account'
        ).select_related('currency')

        search_params = self.request.GET or self.request.session.get('previous_search')
        self.request.session['previous_search'] = search_params
        return self.filter_class(search_params, queryset=queryset)
    
    def get_current_month(self):
        """
        Summary:
        Returns the current month as an integer.

        Returns:
        int: The current month as an integer.
        """
        return datetime.date.today().month
    
    def get_current_year(self):
        """
        Summary:
        Returns the current year as an integer.

        Returns:
        int: The current year as an integer.
        """
        return datetime.date.today().year
    
    def get_previous_month(self):
        """
        Summary:
        Returns the previous month as an integer. If the current month is January, it returns 12 (December of the previous year).

        Returns:
        int: The previous month as an integer.
        """
        current_month = datetime.date.today().month
        return current_month - 1 if current_month > 1 else 12
    
    def get_previous_year(self):
        
        """
        Summary:
        Returns the previous year as an integer. If the current month is January, it returns the previous year.

        Returns:
        int: The previous year as an integer.
        """
        current_month = self.get_current_month()
        current_year = self.get_current_year()
        return current_year if current_month != 1 else current_year - 1
    
    def aggregate_currency(self, account, transaction_type, current_year=datetime.date.today().year, current_month=datetime.date.today().month):
        """
        Summary:
        Aggregates the total transaction amounts for a specific month and year.

        Parameters:
        account (Account): The account for which to retrieve the transaction amounts.
        transaction_type (str): The transaction type to filter by, either '+' for incoming or '-' for outgoing.
        current_year (int): The year for which to retrieve the transactions. Defaults to the current year.
        current_month (int): The month for which to retrieve the transactions. Defaults to the current month.

        Returns:
        float: The total transaction amount for the given account, month and year.
        """
        return account.transaction_from_account.filter(
            date__year=current_year, date__month=current_month, transaction_type=transaction_type
        ).aggregate(total=Sum('amount'))['total'] or 0
    
    def get_object_list(self, object_list, exchange_rates):
        """
        Aggregates the total income, expenses, assigned and start balance for all accounts in the given object_list.

        Parameters:
        object_list (list): A list of Account objects.
        exchange_rates (list): A list of ExchangeRate objects containing the exchange rates for the current month.

        Returns:
        list: A list of dictionaries, each containing the total income, expenses, assigned and start balance for an account in the given object_list.
        """
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
        """
        Retrieves the context data that should be used to render the ListView, including the exchange rates, aggregated data for each account, and the filter class.

        Parameters:
        kwargs (Any): Additional context data that might be needed.

        Returns:
        dict: A dictionary containing the context data for rendering the ListView.
        """
        context = super().get_context_data(**kwargs)
        exchange_rates = get_current_exchange_rates()

        object_list = self.get_object_list(context['object_list'], exchange_rates)
        
        context['object_list'] = object_list

        previous_search = self.request.session.get('previous_search')
        if previous_search:
            context['filter'] = self.filter_class(previous_search)

        years = []
        for year in range(self.request.user.date_joined.year, datetime.date.today().year + 1):
            years.append(year)
        context['years'] = years
        
        if(self.request.GET != {}):
            self.request.session['previous_search'] = self.request.GET
        
        return context
    
    def post(self, request):
        """
        Handles the POST request sent when the user wants to delete an account.

        The view will retrieve the account with the given primary key, set its visible flag to False, and save the changes.

        If the account does not exist, the view will redirect to the accounts page with an error message.

        If the account was successfully deleted, the view will redirect to the accounts page with a success message.

        Parameters:
        request (HttpRequest): The request object sent by the client.

        Returns:
        HttpResponse: A redirect to the accounts page with a message about the outcome of the deletion.
        """
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
    """
    Summary:
    This class is a Django View that handles the summary table for all accounts, including the balance, income and expenses for the current month, and the exchange rates.

    Properties:
    model (Model): The model that should be used to retrieve the list of items.
    template_name (str): The name of the template that should be used to render the ListView.
    paginate_by (int): The number of items to show per page.

    Methods:
    get_context_data(self, **kwargs: Any): Retrieves the context data that should be used to render the ListView, including the list of items and pagination information.
    """
    template_name = 'partials/accounts/summary.html'
    paginate_by = None

    def get_context_data(self, **kwargs: Any):
        """
        Retrieves the context data that should be used to render the ListView, including the exchange rates, aggregated data for each account, and the filter class.

        Parameters:
        kwargs (Any): Additional context data that might be needed.

        Returns:
        dict: A dictionary containing the context data for rendering the ListView.
        """
        qs = self.get_queryset().qs
        context = {}
        exchange_rates = get_current_exchange_rates()
        
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
    """
    Summary:
    This class is a Django View that handles the creation of new accounts. It uses a form to gather data about the account
    and saves it to the database. If the account has a positive balance, an initial transaction is created to represent
    the opening balance. Additionally, a historic balance record is created for the account.

    Properties:
    form_class (Form): The form class used to create a new account.
    template_name (str): The name of the template used to render the form.
    success_url (str): The URL to redirect to upon successful form submission.

    Methods:
    form_valid(form: Any): Handles the successful submission of the form. Saves the account and creates initial transactions and historic balance records if needed.
    form_invalid(form: Any) -> HttpResponse: Handles the case where the form is invalid by re-rendering the form with errors.
    """

    form_class = AccountForm
    template_name = 'partials/accounts/form.html'
    success_url = "/accounts"

    def form_valid(self, form: Any):
        """
        Summary:
        Handles the successful submission of the account creation form.

        This method saves the account and, if the account has a positive balance,
        creates an initial transaction to represent the opening balance. Additionally,
        it creates a historic balance record for the account.

        Parameters:
        form (Any): The form containing the account data.

        Returns:
        HttpResponse: The response to be sent after the form is successfully processed.
        """
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
        """
        Summary:
        Handles the case where the form is invalid by re-rendering the form with errors.

        This method is called when the form is invalid and it renders the form with errors in the template.

        Parameters:
        form (Any): The form containing the account data.

        Returns:
        HttpResponse: The response to be sent after the form is successfully processed.
        """
        
        return render(self.request, 'partials/accounts/form.html', {'form': form})
    
class AccountUpdate(AccountCreation):
    """
    Summary:
    This class is a Django View that handles the update of existing accounts. It uses a form to gather data about the account
    and saves it to the database. If the account has a positive balance, an initial transaction is created to represent
    the opening balance. Additionally, a historic balance record is created for the account.

    Properties:
    form_class (Form): The form class used to update an existing account.
    template_name (str): The name of the template used to render the form.
    success_url (str): The URL to redirect to upon successful form submission.

    Methods:
    form_valid(form: Any): Handles the successful submission of the form. Saves the account and creates initial transactions and historic balance records if needed.
    form_invalid(form: Any) -> HttpResponse: Handles the case where the form is invalid by re-rendering the form with errors.
    get_context_data(self, **kwargs: Any) -> dict[str, Any]: Retrieves the context data that should be used to render the template, including the form and a flag to indicate if this is an update or a creation.
    """
    def form_valid(self, form: Any):
        """
        Summary:
        Handles the successful submission of the account update form.

        This method saves the updated account data. It uses a transaction to ensure
        that the update is atomic. Upon successful update, it displays a success message
        to the user.

        Parameters:
        form (Any): The form containing the updated account data.

        Returns:
        HttpResponse: A redirect response to the accounts page after the form is successfully processed.
        """

        with transaction.atomic():
            form = self.form_class(form.data, instance=Account.objects.get(pk=self.kwargs['pk']))
            form.save()

            messages.success(self.request, "The Account has been updated successfully.")

        return redirect("/accounts")
    
    def form_invalid(self, form: Any) -> HttpResponse:
        """
        Summary:
        Handles the case where the account update form is invalid by re-rendering the form with errors.

        This method is called when the form submission fails validation. It renders the form template
        with error messages, allowing the user to correct the input.

        Parameters:
        form (Any): The form containing the data that was submitted and found to be invalid.

        Returns:
        HttpResponse: The response to render the form with errors.
        """

        return render(self.request, '/accounts/form.html', {'form': form, 'edit': True})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Summary:
        Returns a dictionary of context variables for the account update template.

        This method overrides the default get_context_data method to include the
        account instance being updated and a flag indicating that the form is for
        editing.

        Parameters:
        **kwargs (Any): Any additional keyword arguments.

        Returns:
        dict[str, Any]: A dictionary of context variables.
        """
        instance = Account.objects.get(pk=self.kwargs['pk'])
        return {**super().get_context_data(**kwargs), 'form': self.form_class(instance=instance), 'edit': True}

# TRANSACTIONS VIEWS
class TransactionListView(GeneralListView):
    """
    Summary:
    This class is a Django View that handles the display of all the transactions of an account. It uses a form to filter the transactions
    by date, tags, and more. The transactions are displayed in a table with columns for the date, description, amount, and tags. The view also
    calculates the total balance of the account by summing the amounts of all the transactions.

    Properties:
    model (Model): The model used to retrieve the transactions.
    template_name (str): The name of the template used to render the transactions table.
    filter_class (Filter): The filter class used to filter the transactions.
    paginate_by (int): The number of items to display per page.

    Methods:
    update_tags(account: Account): Updates the tags of the account by creating a MoneyTag for each tag.
    get_queryset(self) -> QuerySet[Any]: Retrieves the filtered and annotated transactions.
    get_context_data(self, **kwargs: Any) -> dict[str, Any]: Retrieves the context data that should be used to render the template, including the form, the transactions, the account, and the total balance.
    """
    
    model = Transaction
    template_name = 'partials/transactions/transactions.html'
    filter_class = TransactionFilter
    paginate_by = 10

    def update_tags(self, account):
        """
        Updates the tags associated with a given account.

        This method retrieves all tags belonging to the current user and ensures that
        a MoneyTag is created for each tag-account combination using an atomic transaction.

        Parameters:
        account (Account): The account for which tags need to be updated.
        """

        with transaction.atomic():
            tags = Tag.objects.filter(user=self.request.user)

            for tag in tags:
                MoneyTag.objects \
                    .get_or_create(
                        tag=tag, account=account
                    )[0]
    
    def get_queryset(self) -> QuerySet[Any]:
        """
        Summary:
        Retrieves the filtered and annotated transactions.

        This method uses the filter class to filter the transactions by the values
        provided in the request GET parameters. The transactions are annotated with
        the previous value of the transaction in the currency of the account.

        Returns:
        QuerySet[Any]: The filtered and annotated transactions.
        """
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
        """
        Summary:
        Retrieves the context data necessary for rendering the transaction list view.

        This method extends the default context data by adding account-specific information
        such as the account details, main currency balance, previous balance, assigned and
        not-assigned funds, and transaction details converted to the main currency. It also
        calculates the previous month's balance and updates account tags.

        Parameters:
        **kwargs (Any): Additional keyword arguments.

        Returns:
        dict[str, Any]: A dictionary containing the context data for rendering the transaction list view.
        """

        context = super().get_context_data(**kwargs)
        account = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        exchange_rates = get_current_exchange_rates()
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
        context['years'] = list(range(account.opening_time.year, datetime.datetime.now().year + 1))
        self.update_tags(account)

        return context

class TransactionCreation(FormView):
    """
    Summary:
    This view handles the creation of a transaction from a given account.
    
    Properties:
    form_class (TransactionForm): The form class that will be used to validate the transaction data.
    template_name (str): The template to render for this view.
    
    Methods:
    form_valid(form, account=None): Overrides the form_valid method from the FormView to add the from_account field to the transaction and save it.
    """
    
    form_class = TransactionForm
    template_name = 'partials/transactions/form.html'

    def form_valid(self, form: TransactionForm, account = None) -> HttpResponse:
        """
        Summary:
        Handles the successful submission of the transaction form.

        This method processes the transaction by associating it with the specified account.
        It updates the account's current balance, handles money tags if applicable, and updates 
        the historic balance for the account. All operations are performed atomically to ensure
        data integrity.

        Parameters:
        form (TransactionForm): The form containing the transaction data.
        account (Optional[Account]): The account to associate with the transaction. If not provided, 
                                    it is retrieved using the account's primary key from the URL.

        Returns:
        HttpResponse: A redirect response to the transaction's page after the form is successfully processed.
        """

        with transaction.atomic():
            account = Account.objects.get(pk=self.kwargs['pk'] if not account else account)

            form.instance.from_account = account
            form.instance.exchange_rate = find_transaction_fitting_exchange_rate(account.currency, self.request.user.main_currency.currency, form.instance.date)
            form.save()

            if not form.instance.hold:
                amount = form.instance.amount if form.instance.transaction_type == '+' else -form.instance.amount
                account.current_balance += amount
                account.save()

                if(form.data['tag']):
                    tag = MoneyTag.objects.get(tag=form.data['tag'], account=account)

                    if form.data['transaction_type'] == '+':
                        tag.amount += amount
                        tag.save()
                    else:
                        self.update_tags_and_accounts(amount, account, tag)

                    update_tag_history(form.data['tag'])

                historic_balance, _ = HistoricBalance.objects.get_or_create(
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
        """
        Summary:
        Adjusts the amounts of MoneyTags for a given account and redistributes amounts
        across different accounts as necessary.

        This method iterates over MoneyTags associated with a specified tag and account,
        adjusting their amounts based on the provided amount. If the amount to be adjusted
        is greater than what is available in the current account, it redistributes the
        deficit to other accounts that share the same tag until the required amount is met
        or all available funds are exhausted.

        Parameters:
        amount (Decimal): The amount to adjust in the MoneyTags.
        account (Account): The account from which the tags are being updated.
        tag (MoneyTag): The MoneyTag associated with the account.

        Side Effects:
        - Adjusts the amount in the MoneyTags.
        - May affect current balances of related accounts.
        - Saves changes to the MoneyTag instances in the database.
        """

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
        """
        Summary:
        If the form is invalid, render the invalid form, adding an error message.

        Parameters:
        form (Any): The invalid form.

        Returns:
        HttpResponse: The rendered template with the invalid form.
        """
        messages.error(self.request, "An error has ocurred while creating your Transaction.")
        print(form.errors)
        return render(self.request, 'partials/transactions/form.html', {'form': form, 'account': Account.objects.get(pk=self.kwargs['pk'])})
    
    def get_form(self, form_class = None):
        """
        Summary:
        Returns an instance of the form to be used in this view.

        Parameters:
        form_class (Any): The form class to be used.

        Returns:
        Form: The instance of the form to be used in this view.
        """
        form = super().get_form(self.form_class)
        form.initial['date'] = datetime.datetime.now()
        form.fields['tag'].queryset = Tag.objects.filter(user=self.request.user)
        return form

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Summary:
        Retrieves the context data that should be used to render the template, including the account and its tags.

        Parameters:
        kwargs (Any): Additional context data that might be needed.

        Returns:
        dict: A dictionary containing the context data for rendering the TransactionCreation view.
        """
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.filter(pk=self.kwargs['pk']).select_related('currency').first()
        context['tags'] = MoneyTag.objects.filter(account=context['account']).select_related('tag').all()
        return context

class TransactionUpdate(TransactionCreation):
    """
    Summary:
    This class is a Django View that handles the update of existing transactions. It uses a form to gather data about the transaction
    and saves it to the database. If the transaction has a positive balance, an initial transaction is created to represent
    the opening balance. Additionally, a historic balance record is created for the account.

    Properties:
    form_class (Form): The form class used to update an existing transaction.
    template_name (str): The name of the template used to render the form.
    success_url (str): The URL to redirect to upon successful form submission.

    Methods:
    form_valid(form: Any): Handles the successful submission of the form. Saves the transaction and creates initial transactions and historic balance records if needed.
    form_invalid(form: Any): Handles the case where the form is invalid by re-rendering the form with errors.
    get_context_data(self, **kwargs: Any): Retrieves the context data that should be used to render the template, including the form and a flag to indicate if this is an update or a creation.
    get_form(self, form_class = None): Returns an instance of the form to be used in this view.
    """
    
    def form_valid(self, form: Any):
        """
        Summary:
        Handles the successful submission of the transaction form.

        This method processes the transaction by associating it with the specified account.
        It updates the account's current balance, handles money tags if applicable, and updates 
        the historic balance for the account. All operations are performed atomically to ensure
        data integrity.

        Parameters:
        form (TransactionForm): The form containing the transaction data.

        Returns:
        HttpResponse: A redirect response to the transaction's page after the form is successfully processed.
        """
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
        """
        Summary:
        Handles the case where the transaction update form is invalid by re-rendering the form with errors.

        This method is called when the form submission fails validation. It prints the form errors
        to the console and renders the form template with error messages, allowing the user to correct
        the input.

        Parameters:
        form (Any): The form containing the data that was submitted and found to be invalid.

        Returns:
        HttpResponse: The response to render the form with errors.
        """

        return render(self.request, '/transactions/form.html', {'form': form, 'edit': True})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Summary:
        Retrieves the context data that should be used to render the template, including the account and the form.

        Parameters:
        kwargs (Any): Additional context data that might be needed.

        Returns:
        dict: A dictionary containing the context data for rendering the TransactionUpdate view.
        """
        instance = Transaction.objects.get(pk=self.kwargs['pk'])
        return {**super().get_context_data(**kwargs), 'account': instance.from_account, 'form': self.form_class(instance=instance), 'edit': True}

class TransactionDelete(LoginRequiredMixin, View):
    """
    Summary:
    This class is a Django View that handles the deletion of existing transactions. It verifies that the user is the owner of the account
    associated with the transaction, and then deletes the transaction, updating the account's current balance and historic balance records
    if the transaction is not on hold.

    Properties:
    model (Model): The model used to retrieve the transactions.

    Methods:
    delete(self, request, *args, **kwargs): Handles the deletion of the transaction. Verifies that the user is the owner of the account
                                             associated with the transaction, and then deletes the transaction, updating the account's
                                             current balance and historic balance records if the transaction is not on hold.
    """
    
    model = Transaction

    def delete(self, request, *args, **kwargs):
        """
        Summary:
        Handles the deletion of the transaction. Verifies that the user is the owner of the account
        associated with the transaction, and then deletes the transaction, updating the account's
        current balance and historic balance records if the transaction is not on hold.

        Parameters:
        request (HttpRequest): The request that triggered this view.
        *args (Any): Additional positional arguments that might be passed to this view.
        **kwargs (Any): Additional keyword arguments that might be passed to this view.

        Returns:
        HttpResponse: A redirect response to the account's page after the transaction is successfully deleted.
        """
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
    """
    Summary:
    This class is a Django View that handles the display of all the user's transactions, regardless of the account.

    Properties:
    model (Model): The model used to retrieve the transactions.
    template_name (str): The name of the template used to render the view.
    filter_class (Filter): The filter class used to filter the transactions.
    paginate_by (int): The number of items to display per page.

    Methods:
    get_queryset(self) -> QuerySet[Any]: Retrieves the filtered and annotated transactions.
    get_context_data(self, **kwargs: Any) -> dict[str, Any]: Retrieves the context data that should be used to render the template, including the form, the transactions, the account, and the total balance.
    """
    
    model = Transaction
    template_name = 'partials/transactions/transactions_general.html'
    filter_class = TransactionFilter
    paginate_by = 15
    
    def get_queryset(self) -> QuerySet[Any]:
        """
        Summary:
        Retrieves the filtered and annotated transactions.

        This method uses the filter class to filter the transactions by the values
        provided in the request GET parameters. The transactions are annotated with
        the previous value of the transaction in the currency of the account.

        Returns:
        QuerySet[Any]: The filtered and annotated transactions.
        """
        return self.filter_class(
            self.request.GET,
            queryset=self.model.objects.select_related(
                'from_account', 'from_account__currency', 'tag', 'exchange_rate'
            ).filter(Q(from_account__owner=self.request.user) | Q(user=self.request.user)).exclude(from_account__visible=False)
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Summary:
        Retrieves the context data that should be used to render the template, including the form, the transactions, the account, and the total balance.

        This method extends the default context data by adding information about the user's accounts, such as the total balance of all accounts, the total amount of money coming in and going out, and the total amount of money on hold. The transactions are annotated with the previous value of the transaction in the currency of the account.

        Parameters:
        **kwargs (Any): Additional keyword arguments.

        Returns:
        dict[str, Any]: The context data that should be used to render the template.
        """
        context = super().get_context_data(**kwargs)

        amounts_balance = Account.objects.filter(owner=self.request.user, visible=True).annotate(total=Sum('current_balance')).values('currency','total')
        main_currency = self.request.user.main_currency.currency
        
        if not self.request.GET.get('date_from'):
            context['filter'] = self.filter_class({
                'date_from': datetime.datetime.now() - datetime.timedelta(days=30),
            })

        years = []
        for year in range(self.request.user.date_joined.year, datetime.date.today().year + 1):
            years.append(year)
        context['years'] = years

        exchange_rates = get_current_exchange_rates()
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
        context['total_in'] = round(convert_all_transactions_amounts_to_main_currency_precisely([{'amount': transaction.amount, 'exchange_rate': transaction.exchange_rate.pk if transaction.exchange_rate else None,  'from_account__currency': transaction.from_account.currency.pk if transaction.from_account else main_currency.pk, 'date': transaction.date} for transaction in qs.filter(transaction_type='+', hold=False)], main_currency.pk), 2)
        context['total_out'] = round(convert_all_transactions_amounts_to_main_currency_precisely([{'amount': transaction.amount, 'exchange_rate': transaction.exchange_rate.pk if transaction.exchange_rate else None, 'from_account__currency': transaction.from_account.currency.pk if transaction.from_account else main_currency.pk, 'date': transaction.date} for transaction in qs.filter(transaction_type='-', hold=False)], main_currency.pk), 2)
        context['total_hold'] = round(convert_all_transactions_amounts_to_main_currency_precisely([{'amount': transaction.amount, 'exchange_rate': transaction.exchange_rate.pk if transaction.exchange_rate else None, 'from_account__currency': transaction.from_account.currency.pk if transaction.from_account else main_currency.pk, 'date': transaction.date} for transaction in qs.filter(hold=True, transaction_type='+')], main_currency.pk), 2)
        context['total_cash_flow'] = context['total_in'] - context['total_out']

        context['main_currency']  = main_currency.code
        return context

# TAGS VIEWS
class TagCreation(LoginRequiredMixin, FormView):
    """
    Summary:
    This view handles the creation of tags. It uses a form to validate
    and save the tag data submitted by the user. Upon successful creation,
    a success message is displayed to the user.

    Properties:
    form_class (Form): The form class used for tag creation.
    template_name (str): The template used to render the tag creation form.

    Methods:
    form_valid(form: Any) -> HttpResponse: Handles the successful submission
    of the form. Saves the tag to the database and displays a success message.
    """

    form_class = TagForm
    template_name = 'partials/tags/form.html'

    def form_valid(self, form: Any) -> HttpResponse:
        """
        Summary:
        Handles the successful submission of the tag creation form.

        This method saves the tag to the database and displays a success message
        to the user.

        Parameters:
        form (Any): The form containing the tag data.

        Returns:
        HttpResponse: A redirect response to the tags page after the form is successfully processed.
        """
        with transaction.atomic():
            form.instance.user = self.request.user
            form.save()

        messages.success(self.request, "The tag has been created successfully.")

        return redirect("/tags")

class TagListView(GeneralListView):
    """
    Summary:
    This view is responsible for listing all the tags of a user. It uses a filter
    to filter the tags based on the search parameters provided by the user. The
    view also supports pagination of the tag list.

    Properties:
    model (Model): The Django model `Tag` used to retrieve and display tag data.
    template_name (str): The template used to render the tag list.
    filter_class (Type[FilterSet]): The filter class used to filter the tags based
    on user input.
    paginate_by (int): The number of items to display per page.

    Methods:
    get_queryset(self) -> QuerySet[Any]: Retrieves the filtered queryset of tags
    visible to the user.
    """
    model = Tag
    template_name = 'partials/tags/list.html'
    filter_class = TagFilter
    paginate_by = 20

    def get_queryset(self):
        """
        Summary:
        Retrieves the filtered queryset of tags visible to the user.

        This method uses the filter class to filter the tags based on the search
        parameters provided by the user. The tags are annotated with the total
        amount of money assigned to each tag and ordered by the assigned amount
        in descending order.

        Returns:
        QuerySet[Any]: The filtered queryset of tags visible to the user.
        """
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
        """
        Summary:
        Retrieves the context data necessary for rendering the tag list view.

        This method extends the default context data by adding information about the
        user's accounts, such as the total balance of all accounts, the total amount of
        money assigned to each tag, and the total amount of money not assigned to any
        tag. The tags are annotated with the total amount of money assigned to each tag
        and ordered by the assigned amount in descending order.

        Parameters:
        **kwargs (Any): Additional keyword arguments.

        Returns:
        dict[str, Any]: The context data that should be used to render the template.
        """

        context = super().get_context_data(**kwargs)
        context["accounts"] = self.get_assigned_balance_per_account()
        context["current_balance"] = self.get_current_balance()
        context["assigned_balance"] = self.get_assigned_balance()
        context["not_assigned_balance"] = context["current_balance"] - context["assigned_balance"]
        context["object_list"] = self.get_object_list(context["object_list"])
        return context
    
    def get_assigned_balance_per_account(self):
        """
        Summary:
        Retrieves the assigned balance per account.

        This method retrieves the balance of each account visible to the user, the
        total amount of money assigned to each account from all its tags, and the
        total amount of money not assigned to any tag. The results are returned as a
        list of dictionaries with the following structure:

        - account: The account object.
        - balance: A dictionary containing the total balance of the account in both
          the main currency and the account's currency.
        - assigned: A dictionary containing the total assigned balance of the account
          in both the main currency and the account's currency.
        - not_assigned: A dictionary containing the total unassigned balance of the
          account in both the main currency and the account's currency.

        Returns:
        list: A list of dictionaries containing the assigned balance per account.
        """
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
        """
        Summary:
        Retrieves the total current balance of all accounts visible to the user.

        This method retrieves the balance of each account visible to the user, and
        converts the balance to the user's main currency using the current exchange
        rates.

        Returns:
        Decimal: The total current balance of all accounts visible to the user in the
        user's main currency.
        """
        accounts_balance = Account.objects.filter(owner=self.request.user, visible=True).annotate(total=Sum('current_balance')).values('currency','total')
        return convert_all(accounts_balance, self.request.user.main_currency.currency.pk)
    
    def get_assigned_balance(self):
        """
        Summary:
        Retrieves the total assigned balance of all visible accounts owned by the user.

        This method calculates the sum of amounts assigned to accounts via MoneyTags,
        aggregated by currency. The result is then converted to the user's main currency
        using current exchange rates.

        Returns:
        Decimal: The total assigned balance of all visible accounts in the user's main currency.
        """

        assigned_balance = MoneyTag.objects.filter(account__owner=self.request.user, account__visible=True).annotate(total=Sum('amount'), currency=F('account__currency__pk')).values('currency','total')
        return convert_all(assigned_balance, self.request.user.main_currency.currency.pk)
    
    def get_object_list(self, object_list):
        """
        Retrieves a list of tags with their total assigned balance and the difference between the current month and the previous month in the user's main currency.

        This method iterates over the given object_list, which is expected to be a list of MoneyTag objects. For each tag, it calculates the total assigned balance by summing the amounts of all MoneyTags associated with the tag, and converts the result to the user's main currency using the current exchange rates. It then calculates the difference between the current month and the previous month by querying the TagHistory model, and stores the result as 'flow' and 'pctg' in the returned list. The 'history' key stores the amount assigned to the tag for each month.

        Parameters:
        object_list (list): A list of MoneyTag objects.

        Returns:
        list: A list of dictionaries, each containing a tag, its total assigned balance in the user's main currency, the difference between the current month and the previous month, and the amount assigned to the tag for each month.
        """
        exchange_rates = get_current_exchange_rates()
        alt = []
        for tag in object_list:
            total = 0
            
            for money_tag in tag.money_tags.all():
                total += convert_all([{'total': money_tag.amount, 'currency': money_tag.account.currency.pk}], self.request.user.main_currency.currency.pk, exchange_rates)
            
            alt.append({
                'tag': tag,
                'total': total,
                'spent': round(convert_all_transactions_amounts_to_main_currency_precisely(
                    tag.transactions.filter(
                        date__year=datetime.date.today().year, 
                        date__month=datetime.date.today().month, 
                        transaction_type='-',
                        hold=False,
                        internal=False
                    ).values(
                        'amount', 'from_account__currency', 'date', 'exchange_rate'
                    ), 
                    self.request.user.main_currency.currency.pk
                ), 2),
                'history': TagHistory.objects.filter(tag=tag).order_by('-year', '-month').values('year', 'month', 'amount'),
            })

            previous = TagHistory.objects.filter(
                tag=tag, 
                year=datetime.date.today().year if datetime.date.today().month != 1 else datetime.date.today().year - 1,
                month=datetime.date.today().month - 1 if datetime.date.today().month != 1 else 12
            ).last().amount if TagHistory.objects.filter(
                tag=tag, 
                year=datetime.date.today().year if datetime.date.today().month != 1 else datetime.date.today().year - 1,
                month=datetime.date.today().month - 1 if datetime.date.today().month != 1 else 12
            ) else 0
            alt[-1]['flow'] = total - previous
            alt[-1]['pctg'] = round(alt[-1]['flow'] / previous * 100, 2) if previous != 0 else 0
        return alt

class TagUpdate(LoginRequiredMixin, FormView):
    """
    Summary:
    This view is responsible for updating a tag. It handles the rendering of the form,
    the validation of the form data, and the saving of the tag.

    Properties:
    form_class (Form): The form class used to validate the form data.
    template_name (str): The template used to render the form.
    model (Model): The model used to retrieve the tag instance.
    success_url (str): The URL to redirect to after the tag has been updated.

    Methods:
    get_form_kwargs(self): Retrieves the form kwargs, including the instance of the tag.
    form_valid(self, form): Saves the tag and redirects to the success URL.
    form_invalid(self, form): Renders the form with errors.
    get_context_data(self, **kwargs): Retrieves the context data, including the tag instance.
    """
    form_class = TagForm
    template_name = 'partials/tags/form.html'

    def get_form_kwargs(self):
        """
        Summary:
        Retrieves the form kwargs, including the instance of the tag.

        Parameters:
        None

        Returns:
        dict: A dictionary containing the form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Tag.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def form_valid(self, form: Any):
        """
        Summary:
        Saves the tag and redirects to the success URL.

        Parameters:
        form (Any): The form containing the tag data.

        Returns:
        HttpResponse: A redirect response to the success URL after the tag is successfully updated.
        """
        form.save()
        messages.success(self.request, "The tag has been updated successfully.")

        return redirect("/tags")

    def form_invalid(self, form: Any) -> HttpResponse:
        """
        Summary:
        Handles the case where the form is invalid by re-rendering the form with errors.

        This method is called when the form is invalid and it renders the form with errors in the template.

        Parameters:
        form (Any): The form containing the tag data.

        Returns:
        HttpResponse: The response to be sent after the form is successfully processed.
        """
        return render(self.request, 'partials/tags/form.html', {'form': form, 'edit': True})

    def get_context_data(self, **kwargs):
        """
        Summary:
        Retrieves the context data, including the tag instance.

        This method extends the default context data by adding the tag instance
        and a flag to indicate that this is an update, not a creation.

        Parameters:
        **kwargs (Any): Additional keyword arguments.

        Returns:
        dict: A dictionary containing the context data for rendering the tag update form.
        """
        context = super().get_context_data(**kwargs)
        context['edit'] = True
        self.tag = Tag.objects.get(pk=self.kwargs['pk'], user=self.request.user)
        return context

class TagDelete(LoginRequiredMixin, View):
    """
    Summary:
    This view handles the deletion of a tag. It retrieves the tag to be deleted,
    checks if the user owns the tag, and deletes the tag and its associated MoneyTags.

    Properties:
    model (Model): The model used to retrieve the tag instance.

    Methods:
    delete(self, request, *args, **kwargs): Handles the deletion of the tag by retrieving the tag instance,
                                            checking if the user owns the tag, and deleting the tag and its associated MoneyTags.
    """
    model = Tag

    def delete(self, request, *args, **kwargs):
        """
        Summary:
        Handles the deletion of a tag. It retrieves the tag to be deleted,
        checks if the user owns the tag, and deletes the tag and its associated MoneyTags.

        Returns:
        HttpResponse: A redirect response to the account's page after the tag is successfully deleted.
        """
        instance = self.model.objects.get(pk=self.kwargs['pk'])

        if(instance.user != request.user):
            return HttpResponseForbidden()
        
        with transaction.atomic():
            instance.money_tags.all().delete()
            instance.tag_history.all().delete()
            instance.delete()

        return render(request, 'partials/transactions/updated-balance.html')

class TagAssignment(LoginRequiredMixin, View):
    """
    Summary:
    This view manages the assignment of tags to an account. It retrieves the appropriate forms for each tag
    and prepares the context data needed for rendering the assignment form.

    Properties:
    template_name (str): The path to the template used for rendering the tag assignment form.

    Methods:
    get_forms(account, request=None): Retrieves the forms for each tag associated with the user and calculates the total amount assigned to each tag in the main currency.
    get_context_data(request=None): Constructs the context data required for rendering the template, including the account details, forms for tag assignment, and exchange rates.
    """

    template_name = 'partials/tags/assignment_form.html'

    def get_forms(self, account, request = None):
        """
        Summary:
        Retrieves the forms for each tag associated with the user and calculates the total amount assigned to each tag in the main currency.

        Parameters:
        account (Account): The account for which the forms are being retrieved.
        request (HttpRequest, optional): The request object containing the user data. Defaults to None.

        Returns:
        list[dict]: A list of dictionaries containing the form for each tag and the total amount assigned to each tag in the main currency.
        """
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
                                         .values('total', 'currency'), self.request.user.main_currency.currency.pk)
                    ])
                })

        return forms
    
    def get_context_data(self, request = None):
        """
        Summary:
        Constructs the context data required for rendering the template, including the account details, forms for tag assignment, and exchange rates.

        Parameters:
        request (HttpRequest, optional): The request object containing the user data. Defaults to None.

        Returns:
        dict[str, Any]: The context data that should be used to render the template.
        """
        
        context = {}
        context['account'] = Account.objects.select_related('currency').get(pk=self.kwargs['pk'])
        context['forms'] = self.get_forms(context['account'], request)
        context['exchange_rate'] = ExchangeRate.objects.get(
            active=True, 
            currency1=self.request.user.main_currency.currency, 
            currency2=context['account'].currency
        ).exchange_rate if context['account'].currency != self.request.user.main_currency.currency else 1
        
        context['totals'] = {
            'total_account': sum([ x['total'] for x in convert_each(
                MoneyTag.objects.filter(account=context['account']).annotate(
                    total=F('amount'), currency=F('account__currency__pk')
                ).values('total', 'currency'), 
                context['account'].currency.pk
            )]),
            'total_tags': round(sum([ x['total'] for x in convert_each(
                    MoneyTag.objects.filter(tag__in=Tag.objects.filter(user=self.request.user)).annotate(
                        total=F('amount'), currency=F('account__currency__pk')
                    ).values('total', 'currency'),
                    context['account'].currency.pk
                )]
            ) * context['exchange_rate'], 2),
        }
        context['totals']['not_assigned'] = round(context['account'].current_balance * context['exchange_rate'] - context['totals']['total_account'] * context['exchange_rate'], 2)
        context['totals']['not_assigned_ac'] = round(context['account'].current_balance - context['totals']['total_account'], 2)
        return context

    def get(self, request, *args, **kwargs):
        """
        Summary:
        Handles GET requests by rendering the template with the context data.

        Returns:
        HttpResponse: The rendered template with the context data.
        """
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, pk):
        """
        Summary:
        Handles POST requests by saving the data of the selected tags in the database and redirecting to the previous page.

        Returns:
        HttpResponse: A redirect response to the previous page after the form is successfully processed.
        """
        
        account = Account.objects.get(pk=pk)
        tags = Tag.objects.filter(user=self.request.user)

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

                update_tag_history(tag.pk) # Update tag history for the current month
            
            messages.success(request, "Your tags have been successfully updated.")            

        return redirect(f"/transactions/{account.pk}/")

def logout_view(request):
    """
    Summary:
    Logs out the user and redirects to the login page.

    Returns:
    HttpResponse: A redirect response to the login page after the user is logged out.
    """
    logout(request)
    return redirect("/login")

def graph_by_accounts(request):
    """
    Summary:
    Retrieves the filtered and annotated account data in the form of a sorted
    list of dictionaries, where each dictionary contains the name, currency, and
    total balance of the account. The total balance is converted to the user's
    main currency.

    Parameters:
    request (HttpRequest): The request object.

    Returns:
    JsonResponse: A JSON response containing the sorted list of dictionaries.
    """
    accounts = AccountFilter(request.GET, queryset=Account.objects.filter(visible=True, owner=request.user).select_related('currency')).qs.annotate(total=F('current_balance')).values('name', 'currency', 'total')
    accounts = sorted(
        convert_each(
            accounts, request.user.main_currency.currency.pk
        ), 
        key=lambda x: x['total'], 
        reverse=True
    )

    return JsonResponse(accounts, safe=False)

def graph_by_tags(request):
    """
    Summary:
    Retrieves a list of accounts with their total balance in the user's main currency.

    This method applies the AccountFilter to filter accounts that are visible and
    owned by the current user. It annotates each account with its current balance,
    converts the total balance to the user's main currency, and returns the data
    as a JSON response.

    Parameters:
    request (HttpRequest): The request object containing the user data and query parameters.

    Returns:
    JsonResponse: A JSON response containing a list of accounts with their name, 
    currency, and total balance in the user's main currency.
    """

    accounts = AccountFilter(request.GET, queryset=MoneyTag.objects.filter(account__visible=True, account__owner=request.user).select_related('currency')).qs.annotate(total=F('current_balance')).values('name', 'currency', 'total')
    accounts = convert_each(accounts, request.user.main_currency.currency.pk)

    return JsonResponse(accounts, safe=False)

def daily_balance_graph(request, pk):
    """
    Summary:
    Generates a JSON response containing the daily balances of the specified account for the past 30 days.

    For each day in the past 30 days, this function calculates the balance by summing the transactions
    of the account. It considers transaction types to adjust the balance accordingly and then returns
    the result as a JSON response.

    Parameters:
    request (HttpRequest): The request object.
    pk (int): The primary key of the account whose daily balances are to be calculated.

    Returns:
    JsonResponse: A JSON response containing a list of dictionaries, each with the date and the balance
    for that day.
    """

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
    """
    Summary:
    Generates a JSON response containing the balance for each tag associated with a specified account.

    This function retrieves all MoneyTags associated with the given account and calculates their
    balances. It includes the available balance that is not assigned to any tag, labeling it as
    "AVAILABLE". The results are sorted by balance in descending order and returned as a JSON response.

    Parameters:
    request (HttpRequest): The request object.
    pk (int): The primary key of the account for which the tag balances are to be calculated.

    Returns:
    JsonResponse: A JSON response containing the balances of each tag and the available balance.
    """

    account = Account.objects.get(pk=pk)
    
    balances = []
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
    """
    Summary:
    A view for changing the password of the user.

    Properties:
    template_name (str): The template to render for this view.
    form_class (Form): The form class to validate the password change.

    Methods:
    get(self, request): Handles the GET request by rendering the template with the form.
    form_valid(self, form): Handles the successful submission of the form by changing the user's password and redirecting to the login page.
    form_invalid(self, form): Handles the unsuccessful submission of the form by re-rendering the template with the form and its errors.
    """
    
    template_name = 'partials/user_management/change_password.html'
    form_class = ChangePasswordForm

    def get(self, request):
        """
        Summary:
        Handles the GET request by rendering the password change form template.

        This method retrieves the form instance and renders the template with the form as context data.

        Parameters:
        request (HttpRequest): The request object containing the user data and HTTP method.

        Returns:
        HttpResponse: The response object containing the rendered template with the form.
        """
        form = self.get_form()
        return render(request, self.template_name, {'form': form})

    def form_valid(self, form):
        """
        Summary:
        Handles the successful submission of the form by changing the user's password and redirecting to the login page.

        This method retrieves the user instance and checks if the provided current password matches the user's current password.
        If it does, it changes the user's password to the new one and saves the changes.
        It adds a success message to the messages and redirects to the login page with a 201 status code.
        If the current password does not match, it displays an error message and renders the template with the form and its errors.

        Returns:
        HttpResponse: The response object containing the rendered template with the form or a redirect to the login page.
        """
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
        """
        Summary:
        Handles the case where the form submission fails validation by rendering the form template with error messages.

        This method checks if the new password and repeat password fields match. If they do not,
        it adds an error message indicating the mismatch. It renders the form template with the existing form data
        and errors to allow the user to correct the input.

        Parameters:
        form (Any): The form containing the submitted data that failed validation.

        Returns:
        HttpResponse: The response object containing the rendered template with the form and its errors.
        """

        if form.cleaned_data['new_password'] != form.cleaned_data['repeat_password']:
            messages.error(self.request, 'The new passwords do not match.')
    
        return render(self.request, self.template_name, {'form': form})

class HistoricBalanceListView(GeneralListView):
    """
    Summary:
    This view is responsible for listing the historic balances of the user's accounts. It filters 
    the historic balances based on year and month and supports pagination.

    Properties:
    - filter_class (Type[FilterSet]): The filter class used to filter the historic balances.
    - model (Model): The Django model `HistoricBalance` used to retrieve and display historic balance data.
    - template_name (str): The template used to render the historic balance list.
    - paginate_by (int): The number of items to display per page.

    Methods:
    - get_queryset(self): Retrieves the filtered queryset of historic balances visible to the user.
    - get_context_data(self, **kwargs): Retrieves the context data necessary for rendering the historic balance list view.
    """

    filter_class = HistoricBalanceFilter
    model = HistoricBalance
    template_name = 'partials/accounts/historic-balance.html'
    paginate_by = 100

    def get_queryset(self):
        """
        Retrieves the filtered queryset of historic balances visible to the user.

        This method extends the default method by using the filter class to filter the historic
        balances based on the year and month provided in the request GET parameters. If the year
        and month are not provided, it defaults to the current year and month.

        Returns:
        QuerySet[HistoricBalance]: The filtered queryset of historic balances visible to the user.
        """
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
            queryset=self.model.objects.select_related('account').filter(account__owner=self.request.user).order_by('account__name')
        )
    
    def get_context_data(self, **kwargs):
        """
        Summary:
        Retrieves the context data necessary for rendering the historic balance list view.

        This method extends the default method by retrieving the filtered queryset of historic balances
        visible to the user. It annotates the queryset with the sum of all the income and expenses of the
        transactions associated with each account. It also annotates the queryset with the total sum of
        all the income and expenses of the transactions that do not have an account associated. The sums
        are converted to the user's main currency before being added to the context data.

        Parameters:
        kwargs (dict): Additional keyword arguments passed to the method.

        Returns:
        dict[str, Any]: The context data necessary for rendering the historic balance list view.
        """
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
            exchange_rates = get_current_exchange_rates().order_by(
                'currency1', 'currency2', '-date'
            )
        
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
            date__month=int(self.request.GET.get('month', datetime.date.today().month)),
            hold=False,
            opening=False
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
        context['totals']['total_out'] += abs(transactions_without_account['total_out']) or 0
        context['totals']['total_external_in'] += transactions_without_account['total_in'] or 0
        context['totals']['total_external_out'] += abs(transactions_without_account['total_out']) or 0
        context['exchange_diffs'] = transactions_without_account 
        context['total_exchange_diff'] = (context['exchange_diffs']['total_in'] or 0) - (context['exchange_diffs']['total_out'] or 0)

        context['total_cash_flow'] = context['totals']['total_in'] - context['totals']['total_out']

        return context
    
class TransferCreationView(TransactionCreation):
    """
    Summary:
    This class is a Django View that handles the creation of transfer transactions between accounts.

    Properties:
    template_name (str): The template used to render the transfer form.
    form_class (Form): The form class used to create a transfer transaction.

    Methods:
    get_form(self, form_class=None): Returns an instance of the form class initialized with the current date.
    get(self, request, *args, **kwargs): Renders the transfer form template with the form and account data.
    post(self, request, *args, **kwargs): Processes the transfer transaction by updating the accounts and handling the conversion and fees.
    """

    template_name = 'partials/transactions/transfer_form.html'
    form_class = TransferForm

    def get_form(self, form_class = None):
        """
        Returns an instance of the form class initialized with the current date.

        Parameters:
        form_class (Form): The form class to be used.

        Returns:
        Form: The instance of the form class initialized with the current date.
        """
        form = self.form_class({
            'pk': self.kwargs['pk'],
            'user': self.request.user
        }, initial={
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        form.fields['tag'].queryset = Tag.objects.filter(user=self.request.user)
        form.fields['tag'].empty_label = '--------------------'
        return form

    def get(self, request, *args, **kwargs):
        """
        Summary:
        Renders the transfer form template with the form and account data.

        Parameters:
        request (HttpRequest): The request object.
        *args (list): Additional positional arguments.
        **kwargs (dict): Additional keyword arguments.

        Returns:
        HttpResponse: The rendered template as a response.
        """
        return render(request, self.template_name, {'form': self.get_form(), 'account': Account.objects.get(pk=self.kwargs['pk'])})
    
    def post(self, request, *args, **kwargs):
        """
        Summary:
        Processes the transfer transaction by updating the accounts and handling the conversion and fees.

        Parameters:
        request (HttpRequest): The request object.
        *args (list): Additional positional arguments.
        **kwargs (dict): Additional keyword arguments.

        Returns:
        HttpResponse: A redirect response after the form is successfully processed.
        """
        try:
            with transaction.atomic():
                from_account = Account.objects.get(pk=self.kwargs['pk']) 
                to_account = Account.objects.get(pk=request.POST.get('to_account'))
                base_amount = Decimal(request.POST.get('amount'))
                base_amount_converted = convert_all(
                    [{'total': base_amount, 'currency': from_account.currency.pk}],
                    to_account.currency.pk
                )
                received_amount = Decimal(request.POST.get('received_amount', 0))
                transformed_received =  round(received_amount * base_amount / base_amount_converted, 2)
                
                fee = round(base_amount - transformed_received, 2)

                if(fee < 0):
                    fee_converted = (-fee) * base_amount_converted / base_amount

                pctg = round(fee / base_amount * 100, 2)
                date = datetime.datetime.now()

                receive_transaction = TransactionForm({
                    'description': request.POST.get('description'),
                    'reference': request.POST.get('reference'),
                    'amount': received_amount if fee >= 0 else round(received_amount - fee_converted, 2),
                    'transaction_type': '+',
                    'from_account': to_account.pk,
                    'internal': True,
                    'hold': False,
                    'tag': request.POST.get('tag') if request.POST.get('tag') and request.POST.get('tag') != '' else None,
                    'date': date,
                })

                if(receive_transaction.is_valid()):
                    self.form_valid(receive_transaction, to_account.pk)
                else:
                    print(receive_transaction.errors)
                    raise Exception("The transference is invalid.")
                
                send_transaction = TransactionForm({
                    'description': request.POST.get('description'),
                    'reference': request.POST.get('reference'),
                    'amount': transformed_received if fee >= 0 else base_amount,
                    'transaction_type': '-',
                    'from_account': from_account.pk,
                    'internal': True,
                    'hold': False,
                    'tag': request.POST.get('tag') if request.POST.get('tag') and request.POST.get('tag') != '' else None,
                    'voucher': request.POST.get('voucher'),
                    'date': date,
                })

                if(send_transaction.is_valid()):
                    self.form_valid(send_transaction, from_account.pk)
                else:
                    print(send_transaction.errors)
                    print("SEND")
                    raise Exception("The transference is invalid.")
                
                print(request.POST.get('deduce_from_tag'))
                
                if(fee > 0):
                    fee_transaction = TransactionForm({
                        'description': f"Transfer fee {pctg}%", 
                        'reference': request.POST.get('reference'),
                        'amount': fee,
                        'transaction_type': '-',
                        'from_account': from_account.pk,
                        'internal': False,
                        'hold': False,
                        'tag': request.POST.get('deduce_from_tag'),
                        'date': date,
                    })

                    if(fee_transaction.is_valid()):
                        self.form_valid(fee_transaction, from_account.pk)
                    else:
                        print("FEE")
                        print(fee_transaction.errors)
                        raise Exception("The transference is invalid.")
                elif(fee < 0):                   
                    fee_transaction = TransactionForm({
                        'description': f"Transfer extra {abs(pctg)}%", 
                        'reference': request.POST.get('reference'),
                        'amount': round(fee_converted, 2),
                        'transaction_type': '+',
                        'from_account': to_account.pk,
                        'internal': False,
                        'hold': False,
                        'tag': request.POST.get('deduce_from_tag'),
                        'date': date,
                    })

                    if(fee_transaction.is_valid()):
                        self.form_valid(fee_transaction, to_account.pk)
                    else:
                        print("FEE")
                        print(fee_transaction.errors)
                        raise Exception("The transference is invalid.")
        except Exception as e:
            print(str(e))
            messages.error(request, "An error has occurred while transferring the money.")
            return render(request, self.template_name, {'form': self.get_form(), 'account': Account.objects.get(pk=self.kwargs['pk'])})
        
        storage = messages.get_messages(request)
        for _ in storage:
            storage.used = True
            
        messages.success(request, "The transfer was successful.")
        print(f"/transactions/{self.kwargs['pk']}/")
        return redirect(f"/transactions/{self.kwargs['pk']}/")
    
def transfer_update(request, pk):
    """
    Summary:
    This view is used to update a transfer form based on the sent and received amounts.
    It calculates the final balance for both accounts, the effective exchange rate, and
    the fee for the transfer.

    Parameters:
    request (HttpRequest): The request object containing the sent and received amounts.
    pk (int): The primary key of the account that is making the transfer.

    Returns:
    HttpResponse: A rendered template containing the updated form data.
    """
    if(request.method != 'GET' or not request.GET.get('to_account') or not request.GET.get('amount')):
        return HttpResponseBadRequest("Invalid request method or missing parameters.")
   
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

    if(fee <= 0):
        fee = 0

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

def set_tag_amount(request, tag_id):
    """
    Summary:
    Sets the amount for a specified tag in a given account.

    This function sets the amount for a MoneyTag associated with a specified tag
    and account. It ensures that the total amount of the tag is converted to the
    currency of the specified account and updates the MoneyTag instances in the
    database accordingly.

    Parameters:
    request (HttpRequest): The request object containing POST data with the account ID.
    tag_id (int): The primary key of the tag whose amount is to be set.

    Returns:
    HttpResponse: Redirects to the tags page upon success or failure.
    """

    tag = Tag.objects.get(pk=tag_id)
    account = Account.objects.filter(pk=request.POST.get('account')).select_related('currency').first()

    if(account.owner != request.user or tag.user != request.user):
        return HttpResponseForbidden()
    
    if not account:
        messages.error(request, "The account does not exist or you do not have permission to access it.")
        return redirect(f'/tags/')
    
    if request.method != 'POST' and request.POST.get('amount') == None or request.POST.get('amount') == '':
        messages.error(request, "The amount is required to set the tag amount.")
        return redirect(f'/tags/')
    
    try:
        with transaction.atomic():
            if request.method == 'POST':
                money_tags = MoneyTag.objects.filter(tag=tag).annotate(currency=F('account__currency'), total=F('amount')).values('currency', 'total')

                total = convert_all(
                    money_tags,
                    account.currency.pk
                )

                MoneyTag.objects.filter(tag=tag, account=account).update(amount=total)
                MoneyTag.objects.filter(tag=tag).exclude(account=account).update(amount=0)

                messages.success(request, "The tag amount has been set successfully.")
                return redirect(f'/tags/')    
    except Exception as e:
        print(str(e))
        messages.error(request, "An error has occurred while setting the tag amount.")
        return redirect(f'/tags/')
  
def reassign_tag(request, tag_id):
    """
    Summary:
    Reassigns a tag to another tag by redistributing the amounts
    in the MoneyTags associated with the accounts of the two tags.

    Parameters:
    request (HttpRequest): The request object containing the POST data with the tag2 id.
    tag_id (int): The primary key of the tag to be reassigned.

    Returns:
    HttpResponse: Redirects to the tags page upon success or failure.
    """
    if(request.user != Tag.objects.get(pk=tag_id).user):
        return HttpResponseForbidden()
    
    tag2_id = request.POST.get('tag2_id')

    if request.method != 'POST' or not tag2_id:
        messages.error(request, "Invalid request method or missing tag.")
        return redirect(f'/tags/')
    
    try:
        with transaction.atomic():
                tag = Tag.objects.get(pk=tag_id)
                tag2 = Tag.objects.get(pk=tag2_id)

                money_tags1 = MoneyTag.objects.filter(tag=tag).select_related('account').order_by('account')
                money_tags2 = MoneyTag.objects.filter(tag=tag2).exclude(tag=tag).select_related('account').order_by('account')

                for money_tag1, money_tag2 in zip(money_tags1, money_tags2):
                    money_tag2.amount += money_tag1.amount
                    money_tag2.save()
                    money_tag1.amount = 0
                    money_tag1.save()
                
                messages.success(request, "The tag has been reassigned successfully.")
    except Exception as e:
        print(str(e))
        messages.error(request, "An error has occurred while reassigning the tag.")

    return redirect(f'/tags/')