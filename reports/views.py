from django.http import HttpResponseForbidden

from reports.pdf import *
from core.models import Account

# Create your views here.

def monthly_transactions_report(request, account):
    '''
    Summary:
        This function generates a PDF report of the monthly transactions.

    Parameters:
        request: The HTTP request object.
        account: The ID of the account for which the report is generated.

    Returns:
        HttpResponse: A PDF response containing the monthly transactions report.
    '''

    year = request.GET.get('year')
    month = request.GET.get('month')
    account = Account.objects.get(id=account)
    
    if account.owner != request.user:
        return HttpResponseForbidden()

    return generate_monthly_transactions_report(request, account, year, month)

def monthly_report_general(request):
    '''
    Summary:
        This function generates a PDF report of the monthly transactions for all accounts.

    Parameters:
        request: The HTTP request object.

    Returns:
        HttpResponse: A PDF response containing the monthly transactions report for all accounts.
    '''

    year = request.GET.get('year')
    month = request.GET.get('month')
    
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    return generate_monthly_transactions_report_all_accounts(request, year, month)

def yearly_report_general(request):
    '''
    Summary:
        This function generates a PDF report of the yearly transactions for all accounts.

    Parameters:
        request: The HTTP request object.

    Returns:
        HttpResponse: A PDF response containing the yearly transactions report for all accounts.
    '''

    year = request.GET.get('year')
    
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    return generate_yearly_transactions_report_all_accounts(request, year)

def yearly_transactions_report(request, account):
    '''
    Summary:
        This function generates a PDF report of the yearly transactions.

    Parameters:
        request: The HTTP request object.
        account: The ID of the account for which the report is generated.

    Returns:
        HttpResponse: A PDF response containing the yearly transactions report.
    '''

    year = request.GET.get('year')
    account = Account.objects.get(id=account)
    
    if account.owner != request.user:
        return HttpResponseForbidden()

    return generate_yearly_transactions_report(request, account, year)

def tag_report(request):
    '''
    Summary:
        This function generates a PDF report of the tag distribution.

    Parameters:
        request: The HTTP request object.

    Returns:
        HttpResponse: A PDF response containing the tag distribution report.
    '''
    
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    return generate_current_tags_report(request)

def current_balances_accounts(request):
    '''
    Summary:
        This function generates a PDF report of the current balances of all accounts.

    Parameters:
        request: The HTTP request object.

    Returns:
        HttpResponse: A PDF response containing the current balances report.
    '''

    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    return current_balances_report_accounts(request)