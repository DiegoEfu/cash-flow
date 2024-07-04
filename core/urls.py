from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path('', welcome_view, name="welcome_view"),
    path('login', LoginView.as_view(), name="login_view"),
    path('log-out', logout_view, name="logout_view"),
    path('sign-up', SignUpView.as_view(), name="sign_up_view"),

    # ACCOUNT VIEWS
    path('accounts/', AccountListView.as_view(), name="account_list"),
    path('accounts/create/', AccountCreation.as_view(), name="account_creation"),
    path('accounts/update/<str:pk>/', AccountUpdate.as_view(), name="account_update"),
]
