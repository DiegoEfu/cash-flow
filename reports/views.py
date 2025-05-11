from django.shortcuts import render
from reports.pdf import *
from core.models import Transaction, HistoricBalance, Account

# Create your views here.

def monthly_transaction_report(request, account):
    '''
    Summary:
        This function generates a PDF report of the monthly transactions.
    '''

    year = request.GET.get('year')
    month = request.GET.get('month')
    account = Account.objects.get(id=account)
    currency = account.currency.code

    table = [
        ['Date', 'Description', f'INCOME ({currency})', f'EXPENSE ({currency})', f'BALANCE ({currency})'],
    ]
    
    if year and month:
        previous_month = int(month) - 1 if int(month) > 1 else 12
        previous_year = int(year) - 1 if int(month) == 1 else year
        start_balance = HistoricBalance.objects.filter(
            date__year=previous_year,
            date__month=previous_month,
            account=account
        ).order_by('-date').first()

        transactions = Transaction.objects.filter(
            date__year=year,
            date__month=month,
            account=account
        )

        if start_balance:
            start_balance = start_balance.balance
            table.append([
                start_balance.date.strftime('%Y-%m-%d'),
                'Start Balance',
                f'{start_balance.balance:,.2f}' if start_balance.balance > 0 else '',
                '',
                f'{start_balance.balance:,.2f}',
            ])
        else:
            start_balance = 0

       
        for transaction in transactions:
            current_balance += transaction.amount if transaction.transaction_type == '+' else -transaction.amount
            table.append([
                transaction.date.strftime('%Y-%m-%d'),
                transaction.description,
                f'{transaction.amount:,.2f}' if transaction.transaction_type == '+' else '',
                f'{abs(transaction.amount):,.2f}' if transaction.transaction_type == '-' else '',
                f'{current_balance:,.2f}',
            ])

        return generate_report(
            request,
            title=f'Monthly Transaction Report - {account.name} - {month}/{year}',
            elements=table,
        )

