"""
URL configuration for financial_monitor project.

Main URL routing that includes all app-level URL configurations.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/categories/', include('transactions.urls_categories')),
    path('api/transactions/', include('transactions.urls_transactions')),
    path('api/analytics/', include('transactions.urls_analytics')),
]
