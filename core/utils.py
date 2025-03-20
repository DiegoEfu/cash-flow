from django.db import transaction
from core.models import Currency, ExchangeRate, HistoricBalance
from bs4 import BeautifulSoup
import decimal
import datetime
import requests
import urllib3

def convert(amount, exchange_rate):
    return round(decimal.Decimal(amount) / decimal.Decimal(exchange_rate), 2)

def convert_all(amounts, main_currency_pk, exchange_rates = None):
    acc = 0

    if(not exchange_rates):    
        exchange_rates = ExchangeRate.objects.filter(active=True) \
            .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
    
    for amount in amounts:
        if amount['currency'] != main_currency_pk:
            exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if \
                                  rate['currency1'] == amount['currency'] and rate['currency2'] == main_currency_pk
                                ), None)

            if not exchange_rate:
                exchange_rate = 1/next((rate['exchange_rate'] for rate in exchange_rates if \
                                      rate['currency1'] == main_currency_pk and rate['currency2'] == amount['currency']
                                    ), 1)
            
            acc += convert(amount['total'], exchange_rate)
        else:
            acc += amount['total']
    
    return acc

def convert_each(amounts, main_currency_pk, exchange_rates = None):
    if(not exchange_rates):    
        exchange_rates = ExchangeRate.objects.filter(active=True) \
            .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
    
    new_amounts = []
    for amount in amounts:
        new_amounts.append(amount)
        if amount['currency'] != main_currency_pk:
            exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if \
                                  rate['currency1'] == amount['currency'] and rate['currency2'] == main_currency_pk
                                ), None)

            if not exchange_rate:
                exchange_rate = 1/next((rate['exchange_rate'] for rate in exchange_rates if \
                                      rate['currency1'] == main_currency_pk and rate['currency2'] == amount['currency']
                                    ), None)
            
            new_amounts[-1]['total'] = convert(amount['total'], exchange_rate)
        
        del(new_amounts[-1]['currency'])

    return new_amounts

def calculate_percentage(current, comparison):
    try:
        percentage = round((current - comparison) /comparison * 100, 2)
    except:
        percentage = None
    
    return percentage

def find_transaction_fitting_exchange_rate(currency1, currency2, date):
    return ExchangeRate.objects.filter(
        currency1=currency1, currency2=currency2,
        date__lte=date
    ).latest('date') if currency1.pk != currency2.pk else None

def get_new_exchange_rate():
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
                print(ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, date__gte=datetime.date.today(), active=True))
                if not ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, date__gte=datetime.date.today(), active=True).exists():
                    ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, active=True).update(active=False)
                    ExchangeRate.objects.create(currency1=currency1, currency2=currency2, exchange_rate=rate, date=fecha)