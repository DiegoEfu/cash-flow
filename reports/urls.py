"""
reports/urls.py

This file contains the URL configurations for the reports app.
The URLs are for generating PDF reports of transactions.
"""

from django.urls import path
from reports.views import *

urlpatterns = [
   path('monthly_transactions_report/<str:account>/', monthly_transactions_report, name='monthly_transactions_report'),
   path('yearly_transactions_report/<str:account>/', yearly_transactions_report, name='yearly_transactions_report'),
   
   path('monthly_transactions_report/', monthly_report_general, name='monthly_report_general'),
   path('yearly_transactions_report/', yearly_report_general, name='yearly_report_general'),
   
   path('tag_report/', tag_report, name='tag_report'),
   path('balance_report/', current_balances_accounts, name='balance_report'),
]
