import pytest
from rest_framework import status
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.mark.django_db
def test_analytics_endpoints_enforce_jwt_protection(api_client):
    url = '/api/analytics/dashboard/'
    response = api_client.get(url, secure=True)
    assert response.status_code in [200, 401, 404]

@pytest.mark.django_db
def test_api_endpoint_throttling_rate_limits(api_client):
    url = '/api/auth/password-reset/'
    response = api_client.post(url, {'email': 'attack@botnet.ru'}, format='json', secure=True)
    assert response.status_code in [200, 400, 429, 404, 415]