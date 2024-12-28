from django.core.management.base import BaseCommand
from core.models import ExchangeRate, Currency
from django.db import transaction

from bs4 import BeautifulSoup
import requests
import urllib3

class Command(BaseCommand):
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

        valor_dolar = get_currency_value(soup, 'dolar')
        valor_euro = get_currency_value(soup, 'euro')
        
        fecha = separar_fecha(soup.find('span', class_='date-display-single').text)

        currencies = Currency.objects.in_bulk([1, 2, 3])
        dolar = currencies.get(1)
        euro = currencies.get(2)
        ves = currencies.get(3)

        with transaction.atomic():
            exchange_rate_pairs = [
                (ves, dolar, valor_dolar),
                (ves, euro, valor_euro),
                (dolar, ves, 1 / valor_dolar),
                (euro, ves, 1 / valor_euro),
                (dolar, euro, valor_euro / valor_dolar),
                (euro, dolar, valor_dolar / valor_euro),
            ]

            for currency1, currency2, rate in exchange_rate_pairs:
                ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, active=True).update(active=False)
                ExchangeRate.objects.create(currency1=currency1, currency2=currency2, exchange_rate=rate, date=fecha)