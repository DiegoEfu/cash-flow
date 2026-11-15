from django.core.management.base import BaseCommand
from core.models import Account, HistoricBalance
import datetime

class Command(BaseCommand):
    help = "Fix all historic balances of all accounts to their current balance"

    def handle(self, *args, **options):
        accounts = Account.objects.filter(visible=True)
        current_month = datetime.date.today().month
        current_year = datetime.date.today().year
        for account in accounts:
            hb, created = HistoricBalance.objects.get_or_create(
                account=account,
                month=current_month,
                year=current_year,
                defaults={'balance': account.current_balance}
            )
            print(f"Account {account.name}: Previous HB: {hb.balance}, Current Account Balance: {account.current_balance}")
            hb.balance = account.current_balance
            hb.save()
            print(f"New Historic Balance: {hb.balance}")
        self.stdout.write(self.style.SUCCESS("All historic balances have been updated"))
