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

def convert_transactions(transactions, main_currency_pk, exchange_rates = None):
    if not exchange_rates:
        exchange_rates = ExchangeRate.objects.filter(active=True) \
            .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
    
    new_transactions = []
    for transaction in transactions:
        new_transactions.append(transaction)
        if transaction['from_account__currency'] != main_currency_pk:
            exchange_rate = find_transaction_fitting_exchange_rate(
                transaction['from_account__currency'], main_currency_pk, transaction['date']
            )
            if not exchange_rate:
                exchange_rate = 1 / find_transaction_fitting_exchange_rate(
                    main_currency_pk, transaction['from_account__currency'], transaction['date']
                )
            
            new_transactions[-1]['mc_amount'] = convert(transaction['amount'], exchange_rate)
            del new_transactions[-1]['from_account__currency']
    
    return new_transactions

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
        valor_yuan = get_currency_value(soup, 'yuan')
        valor_lira = get_currency_value(soup, 'lira')
        valor_rublo = get_currency_value(soup, 'rublo')

        fecha = separar_fecha(soup.find('span', class_='date-display-single').text)

        currencies = Currency.objects.all()
        dolar = currencies.get(pk=1)
        euro = currencies.get(pk=2)
        ves = currencies.get(pk=3)
        yuan = currencies.get(pk=4)
        lira = currencies.get(pk=5)
        rublo = currencies.get(pk=6)

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
                (euro, dolar, valor_dolar / valor_euro),
                (euro, ves, 1 / valor_euro),
                (euro, yuan, valor_yuan / valor_euro),
                (euro, lira, valor_lira / valor_euro),
                (euro, rublo, valor_rublo / valor_euro),
                (yuan, ves, 1 / valor_yuan),
                (yuan, dolar, valor_dolar / valor_yuan),
                (yuan, euro, valor_euro / valor_yuan),
                (yuan, lira, valor_lira / valor_yuan),
                (yuan, rublo, valor_rublo / valor_yuan),
                (lira, ves, 1 / valor_lira),
                (lira, dolar, valor_dolar / valor_lira),
                (lira, euro, valor_euro / valor_lira),
                (lira, yuan, valor_yuan / valor_lira),
                (lira, rublo, valor_rublo / valor_lira),
                (rublo, ves, 1 / valor_rublo),
                (rublo, dolar, valor_dolar / valor_rublo),
                (rublo, euro, valor_euro / valor_rublo),
                (rublo, yuan, valor_yuan / valor_rublo),
                (rublo, lira, valor_lira / valor_rublo),
            ]
            for currency1, currency2, rate in exchange_rate_pairs:
                if not ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, date__gte=datetime.date.today(), active=True).exists():
                    ExchangeRate.objects.filter(currency1=currency1, currency2=currency2, active=True).update(active=False)
                    ExchangeRate.objects.create(currency1=currency1, currency2=currency2, exchange_rate=rate, date=fecha)

def convert_all_transactions_amounts_to_main_currency_precisely(transactions, main_currency):
    exchange_rates = ExchangeRate.objects.filter(
        id__in = [transaction['exchange_rate'] for transaction in transactions],
    ).select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')

    total = 0
    for transaction in transactions:
        if transaction['from_account__currency'] != main_currency:
            exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if rate['currency1'] == transaction['from_account__currency'] and rate['currency2'] == main_currency), None)
            if not exchange_rate:
                exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if rate['currency1'] == main_currency and rate['currency2'] == transaction['from_account__currency']), None)
                if not exchange_rate:
                    exchange_rate = ExchangeRate.objects.filter(
                        currency1__pk=main_currency, 
                        currency2__pk=transaction['from_account__currency'],
                        date__gte=transaction['date'].date()
                    ).first().exchange_rate
               
                exchange_rate = 1 / exchange_rate
            
            transaction['amount'] = transaction['amount'] / exchange_rate
        
        total += transaction['amount']
    
    return total

def figures_size(amount):
    nfigures = len(str(abs(int(amount)))) if amount >= 1 else 0

    if(amount < 1):
        amount *= 100

    LOW_MAX = 3.5*10**(nfigures-1) if nfigures > 0 else 35
    MEDIUM_MAX = 6.5*10**(nfigures-1) if nfigures > 0 else 65

    if((amount <= LOW_MAX)):
        return f"{nfigures} low figure{'s' if nfigures != 1 else ''}"
    elif(amount > LOW_MAX and amount <= MEDIUM_MAX):
        return f"{nfigures} medium figure{'s' if nfigures != 1 else ''}"
    else:
        return f"{nfigures} high figure{'s' if nfigures != 1 else ''}"
