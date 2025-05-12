from django.urls import path
from reports.views import *

urlpatterns = [
   path('monthly_transactions_report/<str:account>/', monthly_transactions_report, name='monthly_transactions_report'),
]
