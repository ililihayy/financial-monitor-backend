"""
URL configuration for analytics endpoints.
"""

from django.urls import path
from .views import dashboard_view, forecast_view, balance_view

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('forecast/', forecast_view, name='forecast'),
    path('balance/', balance_view, name='balance'),
]
