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
                print(f'{main_currency.currency} -> {currency} = {exchange_rate if exchange_rate else "N/A"}')
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

        valor_dolar = 76.88
        valor_euro = 90.81
        valor_yuan = None
        valor_lira = None
        valor_rublo = None
        valor_paralelo = None
        
        fecha = '2025-03-25'

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
            exchange_rate_pairs = [
                (ves, dolar, valor_dolar),
                (ves, euro, valor_euro),
                (ves, yuan, valor_yuan),
                (ves, lira, valor_lira),
                (ves, rublo, valor_rublo),
                (dolar, ves, 1 / valor_dolar),
                (dolar, euro, valor_euro / valor_dolar),
                (dolar, yuan, valor_yuan / valor_dolar),
                (dolar, lira, valor_lira / valor_dolar),
                (dolar, rublo, valor_rublo / valor_dolar),
                (dolar, paralelo, valor_paralelo / valor_dolar),
                (euro, dolar, valor_dolar / valor_euro),
                (euro, ves, 1 / valor_euro),
                (euro, yuan, valor_yuan / valor_euro),
                (euro, lira, valor_lira / valor_euro),
                (euro, rublo, valor_rublo / valor_euro),
                (euro, paralelo, valor_paralelo / valor_euro),
                (yuan, ves, 1 / valor_yuan),
                (yuan, dolar, valor_dolar / valor_yuan),
                (yuan, euro, valor_euro / valor_yuan),
                (yuan, lira, valor_lira / valor_yuan),
                (yuan, rublo, valor_rublo / valor_yuan),
                (yuan, paralelo, valor_paralelo / valor_yuan),
                (lira, ves, 1 / valor_lira),
                (lira, dolar, valor_dolar / valor_lira),
                (lira, euro, valor_euro / valor_lira),
                (lira, yuan, valor_yuan / valor_lira),
                (lira, rublo, valor_rublo / valor_lira),
                (lira, paralelo, valor_paralelo / valor_lira),
                (rublo, ves, 1 / valor_rublo),
                (rublo, dolar, valor_dolar / valor_rublo),
                (rublo, euro, valor_euro / valor_rublo),
                (rublo, yuan, valor_yuan / valor_rublo),
                (rublo, lira, valor_lira / valor_rublo),
                (rublo, paralelo, valor_paralelo / valor_rublo),
                (paralelo, ves, 1 / valor_paralelo),
                (paralelo, dolar, valor_dolar / valor_paralelo),
                (paralelo, euro, valor_euro / valor_paralelo),
                (paralelo, yuan, valor_yuan / valor_paralelo),
                (paralelo, lira, valor_lira / valor_paralelo),
                (paralelo, rublo, valor_rublo / valor_paralelo),
            ]

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
                        date=datetime.datetime.combine(datetime.date.today(), datetime.time.max),
                    )
                    print(f'User {user} had a balance of {previous_balances[user]:.2f} and now has {balance:.2f}, a difference of {difference:.2f}')
