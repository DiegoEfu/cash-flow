"""
This file contains the filter classes used to filter the data in the core application.
Filter classes are used to filter the data in the views based on the parameters provided by the user.
"""

import django_filters
from core.models import *

class AccountFilter(django_filters.FilterSet):
    """
    Summary:
    This class is a Django FilterSet that can be used to filter the accounts of a user.
    It supports filtering by name, description, and currency.

    Properties:
    name (str): The name of the account. Supports filtering by substring.
    description (str): The description of the account. Supports filtering by substring.
    currency (str): The currency of the account. Supports filtering by exact match.

    Methods:
    No methods are defined in this class.

    Meta:
    model (Model): The model used in the filter set.
    fields (tuple): The fields that can be used to filter the accounts.
    """
    name__icontains = django_filters.CharFilter('name', lookup_expr='icontains')
    description__icontains = django_filters.CharFilter('description', lookup_expr='icontains')

    class Meta:
        model = Account
        fields = ('currency',)

class TransactionFilter(django_filters.FilterSet):
    """
    Summary:
    This class is a Django FilterSet that can be used to filter transactions.
    It supports filtering by date, transaction type, hold, internal, id, description, reference, and tag.

    Properties:
    date_from (datetime): The earliest date for which a transaction should be included.
    date_until (datetime): The latest date for which a transaction should be included.
    id__icontains (str): The id of the transaction. Supports filtering by substring.
    description__icontains (str): The description of the transaction. Supports filtering by substring.
    reference__icontains (str): The reference of the transaction. Supports filtering by substring.
    transaction_type (TransactionType): The type of the transaction. Supports filtering by exact match.
    hold (bool): The hold status of the transaction. Supports filtering by exact match.
    internal (bool): The internal status of the transaction. Supports filtering by exact match.
    tag (Tag): The tag of the transaction. Supports filtering by exact match.

    Methods:
    No methods are defined in this class.

    Meta:
    model (Model): The model used in the filter set.
    fields (tuple): The fields that can be used to filter the transactions.
    """
    date_from = django_filters.DateTimeFilter(field_name='date', lookup_expr='gte')
    date_until = django_filters.DateTimeFilter(field_name='date', lookup_expr='lte')
    id__icontains = django_filters.CharFilter('id', lookup_expr='icontains')
    description__icontains = django_filters.CharFilter('description', lookup_expr='icontains')
    reference__icontains = django_filters.CharFilter('reference', lookup_expr='icontains')

    class Meta:
        model = Transaction
        fields = ('transaction_type', 'hold', 'internal', 'tag', 'reference')

class TagFilter(django_filters.FilterSet):
    """
    Summary:
    This class is a Django FilterSet used to filter tags based on user input.
    It supports filtering by name, allowing partial matches for flexibility in search.

    Properties:
    name__icontains (str): The name of the tag. Supports filtering by substring.

    Methods:
    No methods are defined in this class.

    Meta:
    model (Model): The model used in the filter set.
    fields (tuple): The fields that can be used to filter the tags.
    """

    name__icontains = django_filters.CharFilter('name', lookup_expr='icontains')

    class Meta:
        model = Tag
        fields = ('name',)

class HistoricBalanceFilter(django_filters.FilterSet):
    """
    Summary:
    This class is a Django FilterSet used to filter historic balances based on year and month.
    It dynamically generates filter choices for year and month based on available data for the user.

    Properties:
    - year (ChoiceFilter): Filters the historic balances by year using choices from the user's data.
    - month (ChoiceFilter): Filters the historic balances by month using predefined month choices.

    Methods:
    - __init__(*args, **kwargs): Initializes the filter set and dynamically populates year choices based on the user's data.

    Meta:
    - model (Model): The model used in the filter set is HistoricBalance.
    - fields (tuple): The fields that can be used to filter the historic balances are 'year' and 'month'.
    - required (tuple): The fields that are required for filtering the historic balances are 'year' and 'month'.
    """

    def __init__(self, *args, **kwargs):
        """
        Summary:
        Initializes the HistoricBalanceFilter filter set.

        This method dynamically populates the year and month choices for filtering
        historic balances based on the user's available data. The year choices are
        retrieved from the user's historic balance data, while the month choices 
        are predefined.

        Parameters:
        *args: Variable length argument list.
        **kwargs: Keyword arguments, expected to contain 'request' to access the user's data.

        Raises:
        KeyError: If 'request' is not in kwargs or is None.

        Returns:
        None
        """

        super().__init__(*args, **kwargs)

        if('request' in kwargs and kwargs['request']):
            years = HistoricBalance.objects.filter(account__owner=kwargs['request'].user).values_list('year', flat=True).distinct().order_by('-year')
            self.filters['year'] = django_filters.ChoiceFilter(field_name='year', choices=[(year, year) for year in years], empty_label=None)
        
            self.filters['month'] = django_filters.ChoiceFilter(field_name='month', choices=[(name, month) for name,month in HistoricBalance.MONTHS], empty_label=None)

    class Meta:
        model = HistoricBalance
        fields = ('year', 'month')
        required = ('year', 'month')
