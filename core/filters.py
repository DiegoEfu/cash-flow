import django_filters

from core.models import *

class AccountFilter(django_filters.FilterSet):
    name__icontains = django_filters.CharFilter('name', lookup_expr='icontains')
    description__icontains = django_filters.CharFilter('description', lookup_expr='icontains')

    class Meta:
        model = Account
        fields = ('currency',)



class TransactionFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='date', lookup_expr='gte')
    date_until = django_filters.DateTimeFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = Transaction
        fields = ('transaction_type',)
