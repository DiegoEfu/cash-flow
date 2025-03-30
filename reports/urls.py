from django.urls import path, include
from reports.views import *

urlpatterns = [
    path('', index, name="index_report"),
]
