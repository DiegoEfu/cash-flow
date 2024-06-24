from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path('', welcome_view, name="welcome_view"),
    path('login', LoginView.as_view(), name="login_view"),
    path('log-out', logout_view, name="logout_view")
]
