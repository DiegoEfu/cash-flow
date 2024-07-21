from .models import ExchangeRate

def convert(amount, exchange_rate):
    return amount / exchange_rate

def convert_all(amounts, main_currency_pk):
    acc = 0
    exchange_rates = ExchangeRate.objects.filter(active=True) \
        .select_related('currency1', 'currency2').values('exchange_rate', 'currency1', 'currency2')
    
    for amount in amounts:
        print(amount['currency'], main_currency_pk)
        if amount['currency'] != main_currency_pk:
            exchange_rate = next((rate['exchange_rate'] for rate in exchange_rates if \
                                  rate['currency1'] == amount['currency'] and rate['currency2'] == main_currency_pk
                                ), None)
            
            print(exchange_rate)

            if not exchange_rate:
                exchange_rate = 1/next((rate['exchange_rate'] for rate in exchange_rates if \
                                      amount['currency1'] == main_currency_pk and amount['currency2'] == amount['currency']
                                    ), None)
            
            acc += convert(amount['total'], exchange_rate)
        else:
            acc += amount['total']
    
    return acc