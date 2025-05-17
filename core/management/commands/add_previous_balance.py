from django.core.management.base import BaseCommand
from django.db.models import F
from datetime import datetime, timedelta
from core.models import TagHistory, Tag
from core.utils import convert_all

class Command(BaseCommand):
    help = "Create all historic balances from dec 2024 to may 2025 with 0 as initial value"

    def handle(self, *args, **options):

        year = 2024
        month = 12
        while True:
            for tag in Tag.objects.all():
                total_assigned_main_currency = sum(
                    convert_all(
                        [{'total': moneytag.amount, 'currency': moneytag.account.currency.pk}],
                        tag.user.main_currency.pk
                    )
                    for moneytag in tag.money_tags.all()
                )

                if(month == 5):
                    TagHistory.objects.create(
                        tag=tag,
                        amount=total_assigned_main_currency,
                        year=year,
                        month=month,
                    )
                elif(month == 4 and tag.name.upper() == "AHORROS ASEGURADOS"):
                    TagHistory.objects.create(
                        tag=tag,
                        amount=6800,
                        year=year,
                        month=month,
                    )
                else:
                    TagHistory.objects.create(
                        tag=tag,
                        amount=0,
                        year=year,
                        month=month,
                    )
            month = month + 1 if month < 12 else 1
            if(month == 1):
                year += 1

            if(month == 6):
                print("Finished")
                break
