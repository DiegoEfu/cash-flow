from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path('', welcome_view, name="welcome_view")
]
