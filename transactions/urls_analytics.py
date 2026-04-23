"""
URL configuration for analytics endpoints.
"""

from django.urls import path
from .views import (
    dashboard_view, forecast_view, balance_view, ai_insights_view, trend_view,
    anomaly_detection_view, auto_categorize_view, budget_alert_view,
    health_score_view, financial_advisor_view,
)

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('forecast/', forecast_view, name='forecast'),
    path('balance/', balance_view, name='balance'),
    path('insights/', ai_insights_view, name='ai-insights'),
    path('trend/', trend_view, name='trend'),
    # New ML endpoints
    path('anomalies/', anomaly_detection_view, name='anomaly-detection'),
    path('categorize/', auto_categorize_view, name='auto-categorize'),
    path('budget-alert/', budget_alert_view, name='budget-alert'),
    path('health-score/', health_score_view, name='health-score'),
    path('advisor/', financial_advisor_view, name='financial-advisor'),
]
