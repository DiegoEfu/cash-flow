from django.core.management.base import BaseCommand
from core.models import ExchangeRate, Currency, Account, Transaction
from django.contrib.auth import get_user_model
from django.db import transaction

from bs4 import BeautifulSoup
import requests
import urllib3
import datetime

class Command(BaseCommand):

    def get_current_balance(self):
        User = get_user_model()
        users = User.objects.prefetch_related('main_currency__currency').filter(main_currency__isnull=False)
        totals = {}
        for user in users:
            main_currency = user.main_currency
            if not main_currency:
                continue
            accounts = Account.objects.filter(owner=user).prefetch_related('currency')
            total_balance = 0
            for account in accounts:
                currency = account.currency
                exchange_rate = ExchangeRate.objects.filter(currency1=main_currency.currency, currency2=currency, active=True).last()
                exchange_rate = exchange_rate.exchange_rate if exchange_rate else 1
                if exchange_rate:
                    total_balance += account.current_balance * exchange_rate
            
            totals[user] = total_balance
        
        return totals

    def handle(self, *args, **options):
        # Desactiva advertencia por poblemas de SSL en la página del BCV
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) 

        def numero_mes(mes):
            if mes == 'Diciembre':
                return 12
            elif mes == 'Noviembre':
                return 11
            elif mes == 'Octubre':
                return 10
            elif mes == 'Septiembre':
                return 9
            elif mes == 'Octubre':
                return 8
            elif mes == 'Julio':
                return 7
            elif mes == 'Junio':
                return 6
            elif mes == 'Mayo':
                return 5
            elif mes == 'Abril':
                return 4
            elif mes == 'Marzo':
                return 3
            elif mes == 'Febrero':
                return 2
            else:
                return 1

        def separar_fecha(fecha):
            fecha = fecha[fecha.index(',') + 2:]
            fecha = fecha.replace('  ', ' ').split(' ')[::-1]
            fecha[1] = str(numero_mes(fecha[1]))
            return '-'.join(fecha)

        response = ''
        while response == '':
            try:
                response = requests.get('https://www.bcv.org.ve/', verify=False)
                break
            except Exception as e:
                return None

        content = response.text
        soup = BeautifulSoup(content, 'lxml')

        def get_currency_value(soup, currency_id):
            currency_div = soup.find('div', id=currency_id)
            if currency_div and currency_div.find('strong'):
                return round(float(currency_div.find('strong').text.replace(',', '.')), 6)
            return None
        
        fecha = '2025-03-16'

        previous_balances = self.get_current_balance()
        
        currencies = Currency.objects.all()
        dolar = currencies.get(pk=1)
        euro = currencies.get(pk=2)
        ves = currencies.get(pk=3)
        yuan = currencies.get(pk=4)
        lira = currencies.get(pk=5)
        rublo = currencies.get(pk=6)
        paralelo = currencies.get(pk=7)

        with transaction.atomic():
            currencies = [ves, dolar, euro, yuan, lira, rublo, paralelo]
            valores = {
                ves: 1,
                dolar: 94.32410000,
                euro: 105.52791659,
                yuan: 13.08911646,
                lira: 2.43862592,
                rublo: 1.17181820,
                paralelo: 118.02
            }

            exchange_rate_pairs = []

            for currency in currencies:
                for other_currency in currencies:
                    if currency == other_currency:
                        continue
                    exchange_rate_pairs.append((currency, other_currency, valores[other_currency]/valores[currency]))

            for currency1, currency2, rate in exchange_rate_pairs:
                ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, active=True).update(active=False)
                ExchangeRate.objects.create(currency1=currency1, currency2=currency2, exchange_rate=rate, date=fecha)

        with transaction.atomic():
            new_balances = self.get_current_balance()

            for user, balance in new_balances.items():
                difference = balance - previous_balances[user]
                if difference != 0:
                    Transaction.objects.create(
                        user=user,
                        amount=abs(difference),
                        description='Automatic Reconciliation of Exchange Rates Values',
                        from_account=None,
                        transaction_type='+',
                        date=fecha,
                    )
                    print(f'User {user} had a balance of {previous_balances[user]:.2f} and now has {balance:.2f}, a difference of {difference:.2f}')
