from django.core.management.base import BaseCommand
from core.models import Account, HistoricBalance
import datetime

class Command(BaseCommand):
    help = "Fix all historic balances of all accounts to their current balance"

    def handle(self, *args, **options):
        accounts = Account.objects.filter(visible=True)
        for account in accounts:
            historic_balances = HistoricBalance.objects.filter(account=account)
            for hb in historic_balances:
                current_month = datetime.date.today().month
                current_year = datetime.date.today().year
                if hb.month == current_month and hb.year == current_year:
                    print(f"Previous Historic Balance: {hb.balance}, Current Account Balance: {account.current_balance}")
                    hb.balance = account.current_balance
                    hb.save()
                    print(f"New Historic Balance: {hb.balance}")
        self.stdout.write(self.style.SUCCESS("All historic balances have been updated"))
