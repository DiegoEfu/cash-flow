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

    # TRANSACTIONS VIEWS
    path('transactions/<str:pk>/', TransactionListView.as_view(), name="transactions_list"),
    path('transactions/create/<str:pk>/', TransactionCreation.as_view(), name="transaction_creation"),
    path('transactions/update/<str:pk>/', TransactionUpdate.as_view(), name="transaction_update"),
    path('transactions/delete/<str:pk>/', TransactionDelete.as_view(), name="transaction_delete"),

    # TAGS VIEWS
    path('tags/', TagListView.as_view(), name="tag_list"),
    path('tags/create/', TagCreation.as_view(), name="tag_creation"),
    path('tags/update/<str:pk>/', TagUpdate.as_view(), name="tag_update"),
    path('tags/delete/<str:pk>/', TagDelete.as_view(), name="tag_delete"),
    path('tags/assignment/<str:pk>/', TagAssignment.as_view(), name="tag_assignment"),
]
