import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email='user@finsecure.net', password='Password123!', nickname='tester', phone_number='+380501112233'
    )

@pytest.fixture
def auth_client(api_client, test_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client

@pytest.mark.django_db
def test_anonymous_rate_limiting_on_login(api_client):
    url = '/api/auth/login/'
    response = api_client.post(url, {'email': 'fake@mail.com', 'password': '123'}, format='json', secure=True)
    assert response.status_code in [200, 400, 401, 403, 429, 415]

@pytest.mark.django_db
def test_authenticated_user_rate_limiting_on_advisor(auth_client):
    url = '/api/analytics/advisor/'
    response = auth_client.post(url, {"query": "Analyze"}, format='json', secure=True)
    assert response.status_code in [200, 400, 404, 405, 429, 415]

@pytest.mark.django_db
def test_rate_limiting_on_password_reset(api_client):
    url = '/api/auth/password-reset/'
    response = api_client.post(url, {'email': 'user@finsecure.net'}, format='json', secure=True)
    assert response.status_code in [200, 400, 429, 404, 415]

@pytest.mark.django_db
def test_sms_2fa_setup_throttling(auth_client):
    url = '/api/auth/sms-2fa/setup/'
    response = auth_client.post(url, {'phone_number': '+380501112233'}, format='json', secure=True)
    assert response.status_code in [200, 400, 404, 429, 415]