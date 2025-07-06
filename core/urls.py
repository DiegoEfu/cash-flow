"""
core/urls.py

This module defines the URL patterns for the core application. It maps URL paths to the corresponding views, allowing
users to navigate through different parts of the application. The views handle user requests and return appropriate
responses.

URL Patterns:
- WelcomeView: Handles the welcome page for authenticated users.
- LoginView: Handles user login.
- logout_view: Logs out the user and redirects to the login page.
- SignUpView: Handles user sign-up.

Account Views:
- AccountListView: Lists all user accounts.
- AccountCreation: Handles creation of a new account.
- AccountUpdate: Handles updating an existing account.

Transaction Views:
- GeneralTransactionListView: Lists all transactions.
- TransactionListView: Lists transactions for a specific account.
- TransactionCreation: Handles creation of a new transaction.
- TransactionUpdate: Handles updating an existing transaction.
- TransactionDelete: Handles deletion of a transaction.

Transfer Views:
- TransferCreationView: Handles creation of a new transfer.
- transfer_update: Handles updating an existing transfer.

Tag Views:
- TagListView: Lists all user tags.
- TagCreation: Handles creation of a new tag.
- TagUpdate: Handles updating an existing tag.
- TagDelete: Handles deletion of a tag.
- TagAssignment: Assigns a tag to an account.
- set_tag_amount: Sets the amount for a tag.
- reassign_tag: Reassigns a tag to a different account.

Graph Views:
- graph_by_accounts: Generates graphs by accounts.
- daily_balance_graph: Generates daily balance graphs.
- tag_graph_by_account: Generates tag graphs by account.

Historic Balances:
- HistoricBalanceListView: Lists historic balances for accounts.

Summary Table Views:
- AccountSumaryTableView: Lists account summary tables.

User Management Views:
- ChangePasswordView: Handles password change requests.
"""


from django.urls import path
from .views import *

urlpatterns = [
    path('', WelcomeView.as_view(), name="welcome_view"),
    path('login/', LoginView.as_view(), name="login"),
    path('log-out/', logout_view, name="logout_view"),
    path('sign-up/', SignUpView.as_view(), name="sign_up_view"),

    # ACCOUNT VIEWS
    path('accounts/', AccountListView.as_view(), name="account_list"),
    path('accounts/create/', AccountCreation.as_view(), name="account_creation"),
    path('accounts/update/<str:pk>/', AccountUpdate.as_view(), name="account_update"),

    # TRANSACTIONS VIEWS
    path('transactions/general/', GeneralTransactionListView.as_view(), name="general_transactions_list"),
    path('transactions/<str:pk>/', TransactionListView.as_view(), name="transactions_list"),
    path('transactions/create/<str:pk>/', TransactionCreation.as_view(), name="transaction_creation"),
    path('transactions/update/<str:pk>/', TransactionUpdate.as_view(), name="transaction_update"),
    path('transactions/delete/<str:pk>/', TransactionDelete.as_view(), name="transaction_delete"),

    # TRANSFER VIEWS
    path('transfer/<str:pk>/', TransferCreationView.as_view(), name="transfer_creation"),
    path('transfer/update/<str:pk>/', transfer_update, name="transfer_update"),

    # TAGS VIEWS
    path('tags/', TagListView.as_view(), name="tag_list"),
    path('tags/create/', TagCreation.as_view(), name="tag_creation"),
    path('tags/update/<str:pk>/', TagUpdate.as_view(), name="tag_update"),
    path('tags/delete/<str:pk>/', TagDelete.as_view(), name="tag_delete"),
    path('tags/assignment/<str:pk>/', TagAssignment.as_view(), name="tag_assignment"),
    path('tags/send-tag-account/<str:tag_id>/', set_tag_amount, name="send_tag_account"),
    path('tags/reassign-tag/<str:tag_id>/', reassign_tag, name="reassign_tag"),

    # GRAPH VIEWS
    path('accounts/graph/', graph_by_accounts, name="account_graph_view"),
    path('transactions/graph/<str:pk>/', daily_balance_graph, name="tag_graph_view"),
    path('account/tag/graph/<str:pk>/', tag_graph_by_account, name="tag_graph_by_account"),

    # HISTORIC BALANCES
    path('accounts/historic-balance/', HistoricBalanceListView.as_view(), name="historic_balance_list"),

    # SUMMARY TABLE VIEWS
    path('accounts/summary-table/', AccountSumaryTableView.as_view(), name="account_summary_table"),

    # USER MANAGEMENT VIEWS
    path('user/change-password/', ChangePasswordView.as_view(), name="change_password"),
]
