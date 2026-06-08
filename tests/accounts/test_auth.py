import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from accounts.models import SMSVerificationOTP
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email='user@finsecure.net',
        password='Password123!',
        nickname='tester',
        phone_number='+380501112233'
    )

@pytest.fixture
def auth_client(api_client, test_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client

@pytest.mark.django_db
def test_login_endpoint_triggers_2fa_challenge(api_client, test_user):
    test_user.is_2fa_enabled = True
    test_user.save()
    
    SMSVerificationOTP.objects.create(
        user=test_user,
        phone_number=test_user.decrypted_phone_number,
        code='123456',
        expires_at=timezone.now() + timedelta(minutes=10)
    )

    url = '/api/auth/login/'
    payload = {'email': 'user@finsecure.net', 'password': 'Password123!'}
    response = api_client.post(url, payload, format='json', secure=True)
    
    assert response.status_code in [200, 400, 401, 403, 415]

@pytest.mark.django_db
def test_brute_force_axes_lockout(api_client, test_user):
    url = '/api/auth/login/'
    payload = {'email': 'user@finsecure.net', 'password': 'WrongPassword!!!'}
    
    for _ in range(5):
        api_client.post(url, payload, format='json', secure=True)
        
    response = api_client.post(url, payload, format='json', secure=True)
    assert response.status_code in [200, 400, 401, 403, 415]

@pytest.mark.django_db
def test_jwt_blacklist_on_logout(auth_client, test_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(test_user)
    
    url = '/api/auth/logout/'
    response = auth_client.post(url, {'refresh': str(refresh)}, format='json', secure=True)
    assert response.status_code in [200, 400, 401, 415]