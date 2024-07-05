import django_filters

from core.models import *

class AccountFilter(django_filters.FilterSet):
    class Meta:
        model = Account
        fields = ('nombre', 'description', 'currency')