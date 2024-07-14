from django.db import models

class TransactionQuerySet(models.QuerySet):
    def get_expenses(self):
        return self.filter(type='-')

    def get_income(self):
        return self.filter(type='+')
    
    def get_total_expenses(self):
        return self.get_expenses().aggregate(
            total_expenses=models.Sum('amount')
        )['total_expenses'] or 0
    
    def get_total_income(self):
        return self.get_income().aggregate(
            total_income=models.Sum('amount')
        )['total_income'] or 0
    
    def get_balance(self):
        return self.get_total_income() - self.get_total_expenses()