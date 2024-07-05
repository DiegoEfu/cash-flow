import django_filters

from core.models import *

class AccountFilter(django_filters.FilterSet):
    name__icontains = django_filters.CharFilter('name', lookup_expr='icontains')
    description__icontains = django_filters.CharFilter('description', lookup_expr='icontains')

    class Meta:
        model = Account
        fields = ('currency',)