import pytest
import hashlib
from django.conf import settings
from django.db import connection
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email='user@finsecure.net',
        password='Password123!',
        nickname='tester',
        phone_number='+380501112233'
    )

@pytest.mark.django_db
def test_user_model_field_encryption_at_rest(test_user):
    with connection.cursor() as cursor:
        cursor.execute("SELECT email, phone_number FROM accounts_customuser WHERE id = %s", [test_user.id])
        row = cursor.fetchone()
        raw_db_email = row[0]
        raw_db_phone = row[1]
    
    assert raw_db_email != 'user@finsecure.net'
    assert raw_db_phone != '+380501112233'
    assert test_user.decrypted_email == 'user@finsecure.net'
    assert test_user.decrypted_phone_number == '+380501112233'

@pytest.mark.django_db
def test_blind_indexing_deterministic_search():
    email = 'search@finsecure.net'
    salt = getattr(settings, 'SECRET_KEY', 'default-salt')
    expected_hash = hashlib.sha256((email + salt).encode()).hexdigest()
    
    user = User.objects.create_user(email=email, password='Password123!', phone_number='+38000000000')
    assert user.email_hash == expected_hash