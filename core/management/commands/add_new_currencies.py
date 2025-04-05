from django.core.management.base import BaseCommand
from core.models import Currency

class Command(BaseCommand):
    help = "Create new currencies: CNY, TRY, and RUB"

    def handle(self, *args, **options):
        currencies = [
            {'code': 'CNY', 'name': 'Chinese Yuan'},
            {'code': 'TRY', 'name': 'Turkish Lira'},
            {'code': 'RUB', 'name': 'Russian Ruble'},
        ]

        for currency_data in currencies:
            currency, created = Currency.objects.get_or_create(code=currency_data['code'], defaults={'name': currency_data['name']})
            if created:
                self.stdout.write(self.style.SUCCESS(f"Successfully created currency: {currency.code}"))
            else:
                self.stdout.write(self.style.WARNING(f"Currency {currency.code} already exists"))

