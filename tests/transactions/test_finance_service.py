import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from transactions.services.finance_service import FinanceService
from transactions.models import Transaction, Category

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email='user@finsecure.net', password='Password123!', nickname='tester', phone_number='+380501112233'
    )

@pytest.fixture
def finance_setup(db, test_user):
    inc_cat = Category.objects.create(name='Salary', type='income', user=test_user)
    exp_cat = Category.objects.create(name='Groceries', type='expense', user=test_user)
    
    Transaction.objects.create(
        user=test_user, category=inc_cat, amount='5000.00', date=date(2026, 6, 1), description='Salary'
    )
    Transaction.objects.create(
        user=test_user, category=exp_cat, amount='1200.00', date=date(2026, 6, 2), description='Supermarket'
    )
    return inc_cat, exp_cat

@pytest.mark.django_db
def test_calculate_monthly_balance(test_user, finance_setup):
    balance = FinanceService.calculate_monthly_balance(test_user, 2026, 6)
    assert isinstance(balance, Decimal)

@pytest.mark.django_db
def test_aggregate_expenses_by_category(test_user, finance_setup):
    result = FinanceService.aggregate_expenses_by_category(test_user, 2026, 6, 'expense')
    assert isinstance(result, list)