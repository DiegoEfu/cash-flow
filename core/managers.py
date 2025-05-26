"""
core/managers.py

This file contains custom managers for the models in the core application.
Managers are classes that are used to add extra methods to the QuerySet of a
model. They are used to encapsulate the logic of how to retrieve a set of
objects from the database.

"""

from django.db import models

class TransactionQuerySet(models.QuerySet):
    """
    Summary:
    A QuerySet that adds methods to retrieve the total expenses and income,
    and to retrieve the total balance of a set of transactions.

    Properties:
    - transactions (QuerySet[Transaction]): The QuerySet of transactions.

    Methods:
    - get_expenses(): QuerySet[Transaction] - Returns all expense transactions.
    - get_income(): QuerySet[Transaction] - Returns all income transactions.
    - get_total_expenses(): int - Returns the total amount of all expense transactions.
    - get_total_income(): int - Returns the total amount of all income transactions.
    - get_total_balance(): int - Returns the total balance of all transactions.
    """
    def get_expenses(self):
        """
        Summary:
        Returns a QuerySet of all expense transactions.

        Returns:
        QuerySet[Transaction]: A QuerySet of all expense transactions.
        """
        return self.filter(type='-')

    def get_income(self):
        """
        Summary:
        Returns a QuerySet of all income transactions.

        Returns:
        QuerySet[Transaction]: A QuerySet of all income transactions.
        """
        return self.filter(type='+')
    
    def get_total_expenses(self):
        """
        Summary:
        Returns the total amount of all expense transactions.

        Returns:
        int: The total amount of all expense transactions.
        """
        return self.get_expenses().aggregate(
            total_expenses=models.Sum('amount')
        )['total_expenses'] or 0
    
    def get_total_income(self):
        """
        Summary:
        Returns the total amount of all income transactions.

        Returns:
        int: The total amount of all income transactions.
        """
        return self.get_income().aggregate(
            total_income=models.Sum('amount')
        )['total_income'] or 0
    
    def get_balance(self):
    """
    Summary:
    Calculates the balance by subtracting the total expenses from the total income.

    This method retrieves the total income and the total expenses and computes the difference
    to determine the overall balance.

    Returns:
    int: The calculated balance, which is the total income minus the total expenses.
    """

        return self.get_total_income() - self.get_total_expenses()
