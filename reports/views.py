from django.shortcuts import render
from reports.pdf import *
from core.models import Transaction, HistoricBalance, Account
from core.utils import convert_all, convert_all_transactions_amounts_to_main_currency_precisely, figures_size

# Create your views here.

def monthly_transactions_report(request, account):
    '''
    Summary:
        This function generates a PDF report of the monthly transactions.
    '''

    year = request.GET.get('year')
    month = request.GET.get('month')
    account = Account.objects.get(id=account)
    currency = account.currency.code
    main_currency = request.user.main_currency
    print(request.GET)

    table_transactions = [
        ['Date', 'Description', 'Tag', f'Income ({currency})', f'Expense ({currency})', f'Balance ({currency})'],
    ]

    table_tags = [
        ['Tag', f'Income ({currency} / {main_currency})', f'Expense ({currency} / {main_currency})'],
    ]

    table_summary = [
        ['Concept', f'Value ({currency} / {main_currency})'],
    ]
    
    if year and month:
        previous_month = int(month) - 1 if int(month) > 1 else 12
        previous_year = int(year) - 1 if int(month) == 1 else year
        start_balance = HistoricBalance.objects.filter(
            year=previous_year,
            month=previous_month,
            account=account
        ).first()

        transactions = Transaction.objects.filter(
            date__year=year,
            date__month=month,
            from_account=account,
            hold=False,
        ).order_by('date')

        if start_balance:
            start_balance = start_balance.balance
            table_transactions.append([
                f'{year}-{month if int(month) > 9 else "0" + str(month)}-01',
                'Start Balance',
                '',
                f'{start_balance:,.2f}' if start_balance > 0 else '',
                '',
                f'{start_balance:,.2f}'
            ])
        else:
            start_balance = 0

        tags = {}
        sums = {
            'in_int': 0,
            'out_int': 0,
            'in_ex': 0,
            'out_ex': 0,
            'in_mc': 0,
            'out_mc': 0,
            'in_ex_mc': 0,
            'out_ex_mc': 0,
            'cash_flow': 0,
            'cash_flow_mc': 0,
            'avg_balance': 0,
            'avg_balance_mc': 0,
        }
        current_balance = start_balance

        prev_day = f'01-{month}-{year}'
        for transaction in transactions:
            current_balance += transaction.amount if transaction.transaction_type == '+' else -transaction.amount
            current_day = transaction.date.strftime('%d-%m-%Y')
            if current_day != prev_day:
                prev_day = current_day
                sums['avg_balance'] += current_balance
                sums['avg_balance_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                    [{'amount': current_balance, 'date': transaction.date, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency
                )
            
            table_transactions.append([
                Paragraph(transaction.date.strftime('%Y-%m-%d %H:%M')),
                Paragraph((transaction.description if transaction.description else '-') + " " + (f"[I]" if transaction.internal else '[E]')),
                Paragraph(transaction.tag.name if transaction.tag else '-'),
                Paragraph(f'{transaction.amount:,.2f}') if transaction.transaction_type == '+' else '',
                Paragraph(f'{abs(transaction.amount):,.2f}') if transaction.transaction_type == '-' else '',
                Paragraph(f'{current_balance:,.2f}'),
            ])

            sums['in_int'] += transaction.amount if transaction.transaction_type == '+' and transaction.internal else 0
            sums['out_int'] += abs(transaction.amount) if transaction.transaction_type == '-' and transaction.internal else 0
            sums['in_ex'] += transaction.amount if transaction.transaction_type == '+' and not transaction.internal else 0
            sums['out_ex'] += abs(transaction.amount) if transaction.transaction_type == '-' and not transaction.internal else 0
            sums['in_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
            ) if transaction.transaction_type == '+' and transaction.internal else 0
            sums['out_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
            ) if transaction.transaction_type == '-' and transaction.internal else 0
            sums['in_ex_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
            ) if transaction.transaction_type == '+' and not transaction.internal else 0
            sums['out_ex_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
            ) if transaction.transaction_type == '-' and not transaction.internal else 0
            
            if transaction.tag:
                if transaction.tag.name not in tags:
                    tags[transaction.tag.name] = {
                        'in': 0,
                        'out': 0,
                        'in_mc': 0,
                        'out_mc': 0,
                    }
                if transaction.transaction_type == '+':
                    tags[transaction.tag.name]['in'] += transaction.amount
                    tags[transaction.tag.name]['in_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                        [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
                    )
                else:
                    tags[transaction.tag.name]['out'] += abs(transaction.amount)
                    tags[transaction.tag.name]['out_mc'] += convert_all_transactions_amounts_to_main_currency_precisely(
                       [{'amount': transaction.amount, 'from_account__currency': transaction.from_account.currency.pk, 'exchange_rate': transaction.exchange_rate.pk}], request.user.main_currency.pk
                    )            

        sums['cash_flow'] = current_balance - start_balance
        sums['cash_flow_mc'] = sums['in_ex_mc'] + sums['in_mc'] - sums['out_ex_mc'] - sums['out_mc']

        import calendar
        _, num_days = calendar.monthrange(int(year), int(month))
        sums['avg_balance'] = sums['avg_balance'] / num_days
        sums['avg_balance_mc'] = sums['avg_balance_mc'] / num_days

        table_tags += [
            [tag, f'{values["in"]:,.2f} / {values["in_mc"]:,.2f}', f'{values["out"]:,.2f} / {values["out_mc"]:,.2f}']
            for tag, values in tags.items()
        ]

        table_summary += [
            ['Total Income (Internal)', f'{sums["in_int"]:,.2f} / {abs(sums["in_mc"]):,.2f}'],
            ['Total Income (External)', f'{sums["in_ex"]:,.2f} / {abs(sums["in_ex_mc"]):,.2f}'],
            ['Total Expense (Internal)', f'{sums["out_int"]:,.2f} / {abs(sums["out_mc"]):,.2f}'],
            ['Total Expense (External)', f'{sums["out_ex"]:,.2f} / {abs(sums["out_ex_mc"]):,.2f}'],
            ['Cash Flow', f'{sums["cash_flow"]:,.2f} / {sums["cash_flow_mc"]:,.2f}'],
            ['Average Balance', f'{sums["avg_balance"] :,.2f} / {sums["avg_balance_mc"]:,.2f}'],
            ['Avg. Figures', f'{figures_size(sums["avg_balance"])}'],
            [f'Avg. Figures ({main_currency})', f'{figures_size(sums["avg_balance_mc"])}'],
        ]

        return generate_report(
            request,
            title=f'Monthly Transaction Report - {account.name} - {month}/{year}',
            elements=[
                Table(table_transactions, colWidths=(1*inch, 2.5*inch, 1*inch, 1*inch, 1*inch, 1*inch), style=[
                    ('BACKGROUND', (0, 0), (-1, 0), '#DDDDDD'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, '#000000'),
                ]),
                Spacer(0, 0.1 * inch),
                Table(table_tags, style=[
                    ('BACKGROUND', (0, 0), (-1, 0), '#DDDDDD'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, '#000000'),
                ]) if tags else Paragraph('No tags found for this month.'),
                Spacer(0, 0.1 * inch),
                Table(table_summary, style=[
                    ('BACKGROUND', (0, 0), (-1, 0), '#DDDDDD'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, '#000000'),
                ]),
            ],
        )
