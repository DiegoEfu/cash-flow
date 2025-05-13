from django.urls import path
from reports.views import *

urlpatterns = [
   path('monthly_transactions_report/<str:account>/', monthly_transactions_report, name='monthly_transactions_report'),
   path('yearly_transactions_report/<str:account>/', yearly_transactions_report, name='yearly_transactions_report'),
   path('tag_report/', tag_report, name='tag_report'),
]
