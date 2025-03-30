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
    id__icontains = django_filters.CharFilter('id', lookup_expr='icontains')
    description__icontains = django_filters.CharFilter('description', lookup_expr='icontains')

    class Meta:
        model = Transaction
        fields = ('transaction_type', 'hold', 'internal', 'tag')

class TagFilter(django_filters.FilterSet):
    name__icontains = django_filters.CharFilter('name', lookup_expr='icontains')

    class Meta:
        model = Tag
        fields = ('name',)

class HistoricBalanceFilter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if('request' in kwargs and kwargs['request']):
            years = HistoricBalance.objects.filter(account__owner=kwargs['request'].user).values_list('year', flat=True).distinct().order_by('-year')
            self.filters['year'] = django_filters.ChoiceFilter(field_name='year', choices=[(year, year) for year in years], empty_label=None)
        
            self.filters['month'] = django_filters.ChoiceFilter(field_name='month', choices=[(name, month) for name,month in HistoricBalance.MONTHS], empty_label=None)

    class Meta:
        model = HistoricBalance
        fields = ('year', 'month')
        required = ('year', 'month')
