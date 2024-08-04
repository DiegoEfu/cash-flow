from .models import ExchangeRate

def convert(amount, exchange_rate):
    return round(amount / exchange_rate, 2)

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
                                      amount['currency1'] == main_currency_pk and amount['currency2'] == amount['currency']
                                    ), None)
            
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
                                      amount['currency1'] == main_currency_pk and amount['currency2'] == amount['currency']
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