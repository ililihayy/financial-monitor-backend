"""
Views for authentication endpoints.

Handles user registration, login, token refresh, and logout.
Uses JWT authentication via SimpleJWT.
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db import IntegrityError
from datetime import timedelta
import random
from google.auth.transport import requests
from google.oauth2 import id_token
from .serializers import (
    UserRegistrationSerializer, UserSerializer, LoginSerializer,
    GoogleAuthSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    RegistrationVerifySerializer, SMS2FASetupSerializer, SMS2FAVerifySerializer,
    SMS2FADisableSerializer
)
from accounts.models  import CustomUser, PasswordResetOTP, RegistrationOTP
from .services import AuditService
from disposable_email_checker.validators import validate_disposable_email
from django.core.exceptions import ValidationError


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register_view(request):
    """
    Register a new user and send email verification code.

    POST /api/auth/register/
    Body: {
        "email": "user@example.com",
        "password": "securepassword123",
        "password_confirm": "securepassword123",
        "currency_preference": "USD"  # optional
    }

    Returns: {
        "message": "Verification code sent to your email",
        "email": "user@example.com",
        "requires_verification": true
    }
    """
    serializer = UserRegistrationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = request.data.get('email', '').lower().strip()
    try:
        validate_disposable_email(email)
    except ValidationError:
        return Response(
            {'email': ['The use of temporary email addresses is prohibited.']}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Create user but set as inactive
        user = serializer.save()
        user.is_active = False
        user.save()
    except IntegrityError:
        # Handle race condition where email already registered
        return Response(
            {'email': ['A user with this email address is already registered.']},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get the plain email for storing in OTP (it will be encrypted during save)
    email = request.data.get('email').lower().strip()

    # Generate 6-digit OTP code
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

    # Set expiration (15 minutes from now)
    expires_at = timezone.now() + timedelta(minutes=15)

    # Invalidate any existing OTP codes for this email
    RegistrationOTP.objects.filter(email=email, used=False).update(used=True)

    # Create new OTP record
    otp = RegistrationOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

    # Send email with OTP code
    try:
        send_mail(
            subject='Verify Your Email - Financial Monitor',
            message=f'Your email verification code is: {code}\n\nThis code will expire in 15 minutes.\n\nIf you did not create this account, please ignore this email.',
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(
                settings, 'DEFAULT_FROM_EMAIL') else 'noreply@financialmonitor.com',
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        # If email fails, delete the OTP record and user
        print("------- EMAIL ERROR -------")
        print(e)
        print("---------------------------")

        otp.delete()
        user.delete()
        return Response(
            {'error': 'Failed to send verification email. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'message': 'Verification code sent to your email.',
        'email': email,
        'requires_verification': True,
    }, status=status.HTTP_200_OK)


# views_6.py

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register_verify_view(request):
    serializer = RegistrationVerifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email'].lower().strip()
    code = serializer.validated_data['code']

    # 1. ГЕНЕРУЄМО ХЕШ ДЛЯ ПОШУКУ (Blind Index)
    # Використовуємо той самий метод, що і в менеджері користувачів
    email_hash = CustomUser.objects._generate_email_hash(email)

    # 2. ШУКАЄМО OTP ЗА ХЕШЕМ ТА КОДОМ
    try:
        otp = RegistrationOTP.objects.filter(
            email_hash=email_hash,  # Використовуємо хеш замість email
            code=code,
            used=False
        ).latest('created_at')

        # Перевірка на термін дії
        if not otp.is_valid():
            return Response(
                {'error': 'Verification code has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. ШУКАЄМО КОРИСТУВАЧА ЗА ХЕШЕМ
        try:
            user = CustomUser.objects.get(email_hash=email_hash)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Активуємо користувача
        user.is_active = True
        user.save()

        # Позначаємо OTP як використаний
        otp.mark_as_used()

        # Генеруємо JWT токени[cite: 3]
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Email verified successfully. Welcome!',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    except RegistrationOTP.DoesNotExist:
        # Для дебагу можеш додати: print(f"Search failed for hash: {email_hash} and code: {code}")
        return Response(
            {'error': 'Invalid verification code. Please check your code and try again.'},
            status=status.HTTP_400_BAD_REQUEST
        )


# views_6.py

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_view(request):
    email = request.data.get('email', '').lower().strip()
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Шукаємо користувача за хешем (оскільки email зашифрований)
    email_hash = CustomUser.objects._generate_email_hash(email)
    user = CustomUser.objects.filter(email_hash=email_hash).first()

    # 2. Якщо користувача знайдено, але він неактивний
    if user and not user.is_active:
        # ПЕРЕВІРКА ПАРОЛЯ перед відправкою коду (захист від спаму)
        if user.check_password(password):
            # Генеруємо новий код підтвердження
            code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            expires_at = timezone.now() + timedelta(minutes=15)

            # Анулюємо старі коди та створюємо новий
            RegistrationOTP.objects.filter(
                email_hash=email_hash, used=False).update(used=True)
            RegistrationOTP.objects.create(
                email=email,  # Метод save() в моделі сам створить хеш[cite: 4]
                code=code,
                expires_at=expires_at
            )

            # Повторно надсилаємо лист[cite: 3]
            try:
                send_mail(
                    subject='Verify Your Email - FinSecure',
                    message=f'Your new verification code is: {code}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )
            except Exception:
                pass  # Логування помилки відправки за потреби

            return Response({
                'message': 'Account not verified. A new code has been sent to your email.',
                'requires_verification': True,
                'email': email
            }, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    # 3. Стандартна автентифікація для активних користувачів[cite: 3]
    user = authenticate(request, email=email, password=password)

    if user is not None:
        # Перевірка SMS 2FA (якщо налаштовано)[cite: 3]
        try:
            from accounts.models import SMSVerificationOTP
            from .services.sms_service import SMSService
            import logging

            # Check if SMS 2FA is enabled for this user
            if SMSService.is_2fa_enabled(user):
                # Send new 2FA code to phone
                try:
                    otp = SMSVerificationOTP.objects.get(user=user)
                    new_code = SMSService.generate_otp_code()
                    new_expires = timezone.now() + timedelta(minutes=10)

                    otp.code = new_code
                    otp.expires_at = new_expires
                    otp.used = False
                    otp.used_at = None
                    otp.attempts = 0
                    otp.save()

                    SMSService.send_2fa_code(otp.phone_number, new_code)

                    return Response({
                        '2fa_required': True,
                        'message': f'2FA code sent to {otp.phone_number}',
                        'phone_number': otp.phone_number
                    }, status=status.HTTP_403_FORBIDDEN)
                except SMSVerificationOTP.DoesNotExist:
                    pass  # Should not happen if is_2fa_enabled returned True
        except Exception as e:
            # Log error but don't block login
            logger = logging.getLogger('security')
            logger.error(f'Error checking 2FA status: {str(e)}')

        # Успішний вхід (без 2FA або 2FA не включена)[cite: 3]
        refresh = RefreshToken.for_user(user)
        AuditService.log_login_success(user, _get_client_ip(request))
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    # Помилка входу для всіх інших випадків[cite: 3]
    AuditService.log_login_failed(email, _get_client_ip(request))
    return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """
    Refresh access token using refresh token.

    POST /api/auth/refresh/
    Body: {
        "refresh": "refresh_token_here"
    }

    Returns: {
        "access": "new_access_token"
    }
    """
    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response(
            {'error': 'Refresh token is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)

        return Response({
            'access': access_token
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Invalid refresh token.'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    Logout user (blacklist refresh token).

    POST /api/auth/logout/
    Body: {
        "refresh": "refresh_token_here"
    }

    Returns: {"message": "Successfully logged out"}
    """
    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response(
            {'error': 'Refresh token is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': 'Invalid refresh token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_view(request):
    """
    Get current user profile.

    GET /api/auth/profile/

    Returns: User profile data
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_account_view(request):
    """
    Delete the current user account.

    DELETE /api/auth/delete-account/

    Returns: {
        "message": "Account deleted successfully"
    }
    """
    user = request.user
    email = user.decrypted_email

    try:
        # Log the deletion
        AuditService.log_account_deletion(user, _get_client_ip(request))

        # Delete the user account
        user.delete()

        return Response({
            'message': 'Account deleted successfully'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Failed to delete account. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def google_auth_view(request):
    """
    Authenticate user with Google ID token.

    POST /api/auth/google/
    Body: {
        "credential": "google_id_token_here"
    }

    Returns: {
        "user": {...},
        "tokens": {
            "refresh": "...",
            "access": "..."
        }
    }
    """
    serializer = GoogleAuthSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    credential = serializer.validated_data['credential']
    google_client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)

    if not google_client_id:
        return Response(
            {'error': 'Google OAuth client ID is not configured.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        # Verify Google ID token
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            google_client_id
        )

        # Extract user information from Google token
        google_email = idinfo.get('email')
        google_name = idinfo.get('name', '')

        if not google_email:
            return Response(
                {'error': 'Email not found in Google token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create user
        email_hash = CustomUser.objects._generate_email_hash(google_email)

        # Шукаємо користувача за хешем
        user = CustomUser.objects.filter(email_hash=email_hash).first()
        created = False

        if not user:
            # Якщо користувача немає, створюємо його.
            # Модель сама зашифрує email у методі save()
            user = CustomUser.objects.create(
                email=google_email,
                nickname=idinfo.get('name', f"user_{email_hash[:8]}"),
                currency_preference='USD',
                is_active=True
            )
            created = True

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'created': created,
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        # Invalid token
        return Response(
            {'error': 'Invalid Google token. Please try again.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        return Response(
            {'error': 'An error occurred during Google authentication.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def password_reset_request_view(request):
    """
    Request password reset with email OTP code.

    POST /api/auth/password-reset/
    Body: {
        "email": "user@example.com"
    }

    Returns: {
        "message": "Password reset code has been sent to your email.",
        "email": "user@example.com"
    }
    """
    serializer = PasswordResetRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']

    # Check if user exists (don't reveal if user doesn't exist for security)
    if not CustomUser.objects.filter(email=email).exists():
        # Return success message even if user doesn't exist (security best practice)
        return Response({
            'message': 'If an account with this email exists, a password reset code has been sent.',
            'email': email,
        }, status=status.HTTP_200_OK)

    # Generate 6-digit OTP code
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

    # Set expiration (10 minutes from now)
    expires_at = timezone.now() + timedelta(minutes=10)

    # Invalidate any existing OTP codes for this email
    PasswordResetOTP.objects.filter(email=email, used=False).update(used=True)

    # Create new OTP record
    otp = PasswordResetOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

    # Send email with OTP code
    try:
        send_mail(
            subject='Password Reset Code - Financial Monitor',
            message=f'Your password reset code is: {code}\n\nThis code will expire in 10 minutes.\n\nIf you did not request this, please ignore this email.',
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(
                settings, 'DEFAULT_FROM_EMAIL') else 'noreply@financialmonitor.com',
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        # If email fails, delete the OTP record
        print("------- EMAIL ERROR -------")
        print(e)
        print("---------------------------")

        otp.delete()
        return Response(
            # Додамо опис помилки у відповідь
            {'error': f'Failed to send email: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'message': 'Password reset code has been sent to your email.',
        'email': email,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def password_reset_confirm_view(request):
    """
    Confirm password reset with OTP code and set new password.

    POST /api/auth/password-reset/confirm/
    Body: {
        "email": "user@example.com",
        "code": "123456",
        "new_password": "newSecurePassword123"
    }

    Returns: {
        "message": "Password has been reset successfully."
    }
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    new_password = serializer.validated_data['new_password']

    # Find valid OTP record
    try:
        otp = PasswordResetOTP.objects.filter(
            email=email,
            code=code,
            used=False
        ).latest('created_at')

        # Check if OTP is still valid (not expired)
        if not otp.is_valid():
            return Response(
                {'error': 'OTP code has expired or is invalid. Please request a new code.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update password
        user.set_password(new_password)
        user.save()

        # Mark OTP as used
        otp.mark_as_used()

        # Invalidate all other unused OTP codes for this email
        PasswordResetOTP.objects.filter(
            email=email,
            used=False
        ).exclude(pk=otp.pk).update(used=True)

        return Response({
            'message': 'Password has been reset successfully.',
        }, status=status.HTTP_200_OK)

    except PasswordResetOTP.DoesNotExist:
        return Response(
            {'error': 'Invalid OTP code. Please check your code and try again.'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ========== Helper ==========

def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ========== SMS 2FA Views ==========

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def sms_2fa_setup_view(request):
    """
    Begin SMS 2FA setup: send verification code to phone number.

    POST /api/auth/sms-2fa/setup/
    Body: {
        "phone_number": "+1234567890"
    }

    Returns: {
        "message": "Verification code sent to your phone",
        "phone_number": "+1234567890",
        "expires_in_minutes": 10
    }
    """
    sms_2fa_setup_view.throttle_scope = 'sms_2fa_setup'

    serializer = SMS2FASetupSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_number = serializer.validated_data['phone_number']

    try:
        from .services.sms_service import SMSService
        result = SMSService.setup_2fa_sms(request.user, phone_number)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"------- SMS 2FA SETUP ERROR -------\n{str(e)}\n") 
        return Response(
            {'error': 'Failed to set up SMS 2FA. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def sms_2fa_verify_view(request):
    """
    Verify SMS 2FA code and enable SMS 2FA.

    POST /api/auth/sms-2fa/verify/
    Body: {
        "code": "123456"
    }

    Returns: {
        "message": "SMS 2FA has been enabled successfully",
        "phone_number": "+1234567890"
    }
    """
    sms_2fa_verify_view.throttle_scope = 'sms_2fa_verify'

    serializer = SMS2FAVerifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    code = serializer.validated_data['code']

    try:
        from .services.sms_service import SMSService
        from accounts.models import SMSVerificationOTP

        success, message = SMSService.verify_2fa_code(request.user, code)

        if success:
            AuditService.log_2fa_enabled(request.user, _get_client_ip(request))
            refresh = RefreshToken.for_user(request.user)
            return Response({
                'message': 'Logged in successfully',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserSerializer(request.user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def sms_2fa_disable_view(request):
    """
    Disable SMS 2FA (requires a valid OTP code for security).

    POST /api/auth/sms-2fa/disable/
    Body: {
        "code": "123456"
    }

    Returns: {
        "message": "SMS 2FA has been disabled"
    }
    """
    sms_2fa_disable_view.throttle_scope = 'sms_2fa_disable'

    serializer = SMS2FADisableSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    code = serializer.validated_data['code']

    try:
        from .services.sms_service import SMSService

        success, message = SMSService.verify_2fa_code(request.user, code)

        if success:
            SMSService.disable_2fa(request.user)
            AuditService.log_2fa_disabled(
                request.user, _get_client_ip(request))
            return Response(
                {'message': 'SMS 2FA has been disabled'},
                status=status.HTTP_200_OK
            )
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def sms_2fa_status_view(request):
    """
    Check whether SMS 2FA is enabled for the current user.

    GET /api/auth/sms-2fa/status/

    Returns: {
        "is_2fa_enabled": true,
        "phone_number": "+1234567890"
    }
    """
    try:
        from .services.sms_service import SMSService
        from accounts.models import SMSVerificationOTP

        is_enabled = SMSService.is_2fa_enabled(request.user)

        response_data = {'is_2fa_enabled': is_enabled}

        if is_enabled:
            try:
                otp = SMSVerificationOTP.objects.get(user=request.user)
                response_data['phone_number'] = otp.phone_number
            except SMSVerificationOTP.DoesNotExist:
                pass

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# views_6.py

@api_view(['POST'])
@permission_classes([AllowAny])
# Важливо: обмеж кількість запитів, щоб не заспамити пошту
@throttle_classes([ScopedRateThrottle])
def resend_verification_view(request):
    """
    Повторно надсилає код верифікації для неактивного акаунта.
    """
    resend_verification_view.throttle_scope = 'resend_verification'
    email = request.data.get('email', '').lower().strip()

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Шукаємо користувача за хешем (через зашифрований email)
    email_hash = CustomUser.objects._generate_email_hash(email)
    user = CustomUser.objects.filter(email_hash=email_hash).first()

    # 2. Перевіряємо, чи існує користувач і чи він ще не підтверджений
    if not user:
        # Для безпеки повертаємо "успіх", навіть якщо email не знайдено (захист від перебору імейлів)
        return Response({'message': 'If the account exists and is unverified, a new code has been sent.'}, status=status.HTTP_200_OK)

    if user.is_active:
        return Response({'error': 'This account is already verified.'}, status=status.HTTP_400_BAD_REQUEST)

    # 3. Генеруємо новий 6-значний код
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = timezone.now() + timedelta(minutes=15)

    # 4. Анулюємо всі попередні невикористані коди для цього імейла
    RegistrationOTP.objects.filter(
        email_hash=email_hash, used=False).update(used=True)

    # 5. Створюємо новий запис OTP[cite: 4]
    # Метод save() в RegistrationOTP автоматично зашифрує email та оновить хеш[cite: 4]
    RegistrationOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

    # 6. Надсилаємо імейл[cite: 3]
    try:
        send_mail(
            subject='New Verification Code - FinSecure',
            message=f'Your new verification code is: {code}\nIt expires in 15 minutes.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return Response({'message': 'A new verification code has been sent to your email.'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': 'Failed to send email. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
