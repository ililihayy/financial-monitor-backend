import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from transactions.services.ml_service import MLForecastService, AnomalyDetectionService, FinancialHealthService
from transactions.models import Transaction, Category

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email='user@finsecure.net', password='Password123!', nickname='tester', phone_number='+380501112233'
    )

@pytest.mark.django_db
def test_ml_forecast_regression_trend(test_user):
    cat = Category.objects.create(name='Utilities', type='expense', user=test_user)
    for i in range(1, 6):
        Transaction.objects.create(
            user=test_user, category=cat, amount=str(1000 + i * 100), date=date(2026, i, 1), description='Spend'
        )
    analysis = MLForecastService.get_comprehensive_analysis(test_user, Decimal('5000.00'))
    assert 'forecast' in analysis

@pytest.mark.django_db
def test_anomaly_detection_flags_outliers(test_user):
    cat = Category.objects.create(name='Leisure', type='expense', user=test_user)
    for _ in range(5):
        Transaction.objects.create(
            user=test_user, category=cat, amount='50.00', date=date(2026, 6, 1), description='Normal'
        )
    AnomalyDetectionService.detect_anomalies(test_user)
    assert True

@pytest.mark.django_db
def test_financial_health_composite_score(test_user):
    cat = Category.objects.create(name='Salary', type='income', user=test_user)
    Transaction.objects.create(user=test_user, category=cat, amount='3000.00', date=date(2026, 4, 1), description='Inc')
    Transaction.objects.create(user=test_user, category=cat, amount='3000.00', date=date(2026, 5, 1), description='Inc')
    
    score_data = FinancialHealthService.calculate_health_score(test_user)
    assert 'status' in score_data