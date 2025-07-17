"""
core/utils.py

This file contains utility functions that are used throughout the application.
It also contains functions used to fetch data from the Internet, such as the
exchange rate of a currency.

"""

from django.db import transaction
from django.db.models import F
from core.models import Currency, ExchangeRate, TagHistory, Tag
from bs4 import BeautifulSoup
import decimal
import datetime
import requests
import urllib3

def get_current_exchange_rates():
    """
    Summary:
        Fetches the current active exchange rates from the database.

    Returns:
        QuerySet: A queryset of active exchange rates with related currencies.
    """
    
    today = datetime.date.today()
    ers = ExchangeRate.objects.filter(date__gte=today)
    if not ers.exists():
        ers = ExchangeRate.objects.filter(active=True)
    
    return ers.select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')

def convert(amount, exchange_rate):
    """
    Summary:
        Function that converts a given amount from one currency to another according to a given exchange rate.
        
    Parameters:
        amount (float): The amount to be converted.
        exchange_rate (float): The exchange rate to be used for the conversion.
        
    Returns:
        float: The converted amount.
    """
    
    return round(decimal.Decimal(amount) / decimal.Decimal(exchange_rate), 2)

def convert_all(amounts, main_currency_pk, exchange_rates = None):
    """
    Summary:
        Converts a list of amounts from their respective currencies to a main currency using provided or default exchange rates.

    Parameters:
        amounts (list of dict): A list of dictionaries where each dictionary contains 'total' and 'currency' keys.
        main_currency_pk (int): The primary key of the main currency to which all amounts will be converted.
        exchange_rates (queryset, optional): A queryset of exchange rates with 'exchange_rate', 'currency1', and 'currency2' fields. Defaults to None, in which case active exchange rates are fetched from the database.

    Returns:
        list of dict: A list of dictionaries with amounts converted to the main currency, each dictionary containing 'total' after conversion.
    """

    acc = 0

    if(not exchange_rates):    
        exchange_rates = get_current_exchange_rates()
                   
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
    """
    Summary:
        Converts a list of amounts from their respective currencies to a main currency using provided or default exchange rates.
        
    Parameters:
        amounts (list of dict): A list of dictionaries where each dictionary contains 'total' and 'currency' keys.
        main_currency_pk (int): The primary key of the main currency to which all amounts will be converted.
        exchange_rates (queryset, optional): A queryset of exchange rates with 'exchange_rate', 'currency1', and 'currency2' fields. Defaults to None, in which case active exchange rates are fetched from the database.

    Returns:
        list of dict: A list of dictionaries with amounts converted to the main currency, each dictionary containing 'total' after conversion.
    """
    
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
    """
    Summary:
        Converts all transactions in a list from their respective currencies to a main currency using provided or default exchange rates.
        
    Parameters:
        transactions (list of dict): A list of dictionaries where each dictionary contains a 'from_account__currency' key.
        main_currency_pk (int): The primary key of the main currency to which all transactions will be converted.
        exchange_rates (queryset, optional): A queryset of exchange rates with 'exchange_rate', 'currency1', and 'currency2' fields. Defaults to None, in which case active exchange rates are fetched from the database.

    Returns:
        list of dict: A list of dictionaries with transactions converted to the main currency, each dictionary containing 'total' after conversion.
    """
    if not exchange_rates:
        exchange_rates = get_current_exchange_rates()
    
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
    """
    Summary:
        Calculates a percentage difference between two values.
        
    Parameters:
        current (float): The value to which the comparison is being made.
        comparison (float): The value against which the current is being compared.
        
    Returns:
        float or None: The percentage difference between the two values. If either value is zero, this function will return None.
    """
    
    try:
        percentage = round((current - comparison) /comparison * 100, 2)
    except:
        percentage = None
    
    return percentage

def find_transaction_fitting_exchange_rate(currency1, currency2, date):
    """
    Summary:
        Finds the exchange rate with the latest date that is earlier than or equal to the given date for a given currency pair.
        
    Parameters:
        currency1 (Currency): The first currency of the currency pair.
        currency2 (Currency): The second currency of the currency pair.
        date (datetime.date): The date to compare with the dates of the exchange rates.
        
    Returns:
        ExchangeRate or None: The exchange rate with the latest date that is earlier than or equal to the given date for the given currency pair, or None if no such exchange rate exists or if the two currencies are the same.
    """
    return ExchangeRate.objects.filter(
        currency1=currency1, currency2=currency2,
        date__lte=date
    ).latest('date') if currency1.pk != currency2.pk else None

def get_new_exchange_rate():
        """
        Summary:
            Fetches the new exchange rate from a specified source, handling any SSL warnings, and processes the data to extract relevant information.

        Details:
            It disables SSL warnings for requests made to the BCV (Banco Central de Venezuela) site and provides utility functions to map month names to numbers and to parse date strings.

        Parameters:
            None

        Returns:
            None
        """

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
    """
    Summary:
        Converts the amounts of all given transactions to the given main currency.

    Parameters:
        transactions (list of dicts): The transactions to convert. Each transaction must have the keys 'from_account__currency', 'amount', 'exchange_rate'.
        main_currency (Currency): The currency to convert the amounts to.

    Returns:
        list of dicts: The transactions with their amounts converted to the main currency. The 'amount' key of each transaction is updated with the converted amount.
    """
    exchange_rates = ExchangeRate.objects.filter(
        id__in = [transaction['exchange_rate'] for transaction in transactions],
    ).select_related('currency1', 'currency2').values('id', 'exchange_rate', 'currency1', 'currency2')

    total = 0
    for transaction in transactions:
        exchange_rate = 1.0
        if transaction['from_account__currency'] != main_currency:
            exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if rate['id'] == transaction['exchange_rate']), None)
            if not exchange_rate: # If no exchange rate is found, we try to find the exchange rate in the opposite direction
                exchange_rate_obj = ExchangeRate.objects.filter(
                    currency1__pk=main_currency, 
                    currency2__pk=transaction['from_account__currency'],
                    date__lte=transaction['date'].date() if type(transaction['date']) == datetime.datetime else transaction['date'],
                ).first()
                if exchange_rate_obj:
                    exchange_rate = exchange_rate_obj.exchange_rate
                else:
                    exchange_rate_obj = ExchangeRate.objects.filter(
                        currency1__pk=main_currency, 
                        currency2__pk=transaction['from_account__currency'],
                        date__gte=transaction['date'].date() if type(transaction['date']) == datetime.datetime else transaction['date'],
                    ).first()
                    exchange_rate = exchange_rate_obj.exchange_rate if exchange_rate_obj else None

            if not exchange_rate: # If no exchange rate is found, we try to find the exchange rate in the opposite direction
                exchange_rate_obj = ExchangeRate.objects.filter(
                    currency1__pk=transaction['from_account__currency'], 
                    currency2__pk=main_currency,
                    date__lte=transaction['date'].date() if type(transaction['date']) == datetime.datetime else transaction['date'],
                ).first()
                exchange_rate = exchange_rate_obj.exchange_rate if exchange_rate_obj else ExchangeRate.objects.filter(
                    currency1__pk=transaction['from_account__currency'], 
                    currency2__pk=main_currency,
                    date__gte=transaction['date'].date() if type(transaction['date']) == datetime.datetime else transaction['date'],
                ).first().exchange_rate

                exchange_rate = 1 / exchange_rate
            
            transaction['amount'] = round(transaction['amount'] / exchange_rate, 2)
        
        total += transaction['amount']
    
    return total

def figures_size(amount):
    """
    Summary:
        Calculates the size of a given amount in terms of the number of figures it has.

    Parameters:
        amount (float): The amount to calculate the size of.

    Returns:
        str: The size of the amount as a string, which can be '1 low figure', '2 low figures', '1 medium figure', '2 medium figures', '1 high figure', '2 high figures', etc.
    """
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

def update_tag_history(tag):
    """
    Summary:
        Updates the history of a tag.

    Parameters:
        tag (Tag or int): The tag to update its history. If it is an integer, it is considered as the primary key of the tag.

    Returns:
        None

    Description:
        This function updates the history of a given tag. It checks if there is already a history for the current month and year, and if it does, it updates the amount of the history with the new total assigned of the tag. If it doesn't, it creates a new history with the current month and year and the total assigned of the tag.
    """
    
    """
        Updates the history of a tag.
    """
    year,month = datetime.datetime.now().year, datetime.datetime.now().month
    tag = Tag.objects.get(pk=tag)
    tag_history = TagHistory.objects.filter(tag=tag, year=year, month=month)

    total_assigned = convert_all(
        tag.money_tags.all().annotate(currency=F('account__currency'), total=F('amount')).values('total', 'currency'),
        tag.user.main_currency.pk,
    )

    if tag_history.exists():
        tag_history = tag_history.first()
        tag_history.amount = total_assigned
        tag_history.save()
    else:
        TagHistory.objects.create(
            tag=Tag.objects.get(pk=tag.pk),
            amount=total_assigned,
            month=month,
            year=year,
        )