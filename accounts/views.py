import logging
import random
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from axes.models import AccessAttempt
from disposable_email_checker.validators import validate_disposable_email

from accounts.models import CustomUser, PasswordResetOTP, RegistrationOTP, SMSVerificationOTP
from .serializers import (
    UserRegistrationSerializer, UserSerializer, LoginSerializer,
    GoogleAuthSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    RegistrationVerifySerializer, SMS2FASetupSerializer, SMS2FAVerifySerializer,
    SMS2FADisableSerializer
)
from .services import AuditService
from .services.sms_service import SMSService


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
        user = serializer.save()
        user.is_active = False
        user.save()
    except IntegrityError:
        return Response(
            {'email': ['A user with this email address is already registered.']},
            status=status.HTTP_400_BAD_REQUEST
        )

    email = request.data.get('email').lower().strip()
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = timezone.now() + timedelta(minutes=15)

    # Invalidate any existing OTP codes for this email
    RegistrationOTP.objects.filter(email=email, used=False).update(used=True)

    otp = RegistrationOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

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


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register_verify_view(request):
    serializer = RegistrationVerifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email'].lower().strip()
    code = serializer.validated_data['code']

    email_hash = CustomUser.objects._generate_email_hash(email)
    try:
        otp = RegistrationOTP.objects.filter(
            email_hash=email_hash,
        ).latest('created_at')

        if not otp.is_valid():
            return Response(
                {'error': 'Verification code has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = CustomUser.objects.get(email_hash=email_hash)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_active = True
        user.save()
        otp.mark_as_used()

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
        return Response(
            {'error': 'Invalid verification code. Please check your code and try again.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_view(request):
    email = request.data.get('email', '').lower().strip()
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    client_ip = _get_client_ip(request)
    is_locked = AccessAttempt.objects.filter(
        ip_address=client_ip,
        username=email,
        failures_since_start__gte=settings.AXES_FAILURE_LIMIT
    ).exists()

    if is_locked:
        return Response(
            {'error': 'Account locked out due to too many failed login attempts. Please try again later.'},
            status=status.HTTP_403_FORBIDDEN
        )

    email_hash = CustomUser.objects._generate_email_hash(email)
    user = CustomUser.objects.filter(email_hash=email_hash).first()

    if user and not user.is_active:
        if user.check_password(password):
            code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            expires_at = timezone.now() + timedelta(minutes=15)

            RegistrationOTP.objects.filter(
                email_hash=email_hash, used=False).update(used=True)
            RegistrationOTP.objects.create(
                email=email, code=code, expires_at=expires_at)

            try:
                send_mail(
                    subject='Verify Your Email - FinSecure',
                    message=f'Your new verification code is: {code}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )
            except Exception:
                pass

            return Response({
                'message': 'Account not verified. A new code has been sent to your email.',
                'requires_verification': True,
                'email': email
            }, status=status.HTTP_403_FORBIDDEN)
        else:
            user_login_failed.send(
                sender=CustomUser, request=request, credentials={'username': email})
            AuditService.log_login_failed(email, client_ip)
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    user = authenticate(request, email=email, password=password)

    if user is not None:
        try:
            if SMSService.is_2fa_enabled(user):
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
                    pass
        except Exception as e:
            logger = logging.getLogger('security')
            logger.error(f'Error checking 2FA status: {str(e)}')

        refresh = RefreshToken.for_user(user)
        AuditService.log_login_success(user, client_ip)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    user_login_failed.send(sender=CustomUser, request=request,
                           credentials={'username': email})
    AuditService.log_login_failed(email, client_ip)
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


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_view(request):
    """
    Get or update current user profile.
    GET /api/auth/profile/
    PATCH /api/auth/profile/
    """
    user = request.user

    if request.method == 'PATCH':
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer = UserSerializer(user)
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
        AuditService.log_account_deletion(user, _get_client_ip(request))
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
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            google_client_id
        )

        google_email = idinfo.get('email')
        google_name = idinfo.get('name', '')

        if not google_email:
            return Response(
                {'error': 'Email not found in Google token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email_hash = CustomUser.objects._generate_email_hash(google_email)

        user = CustomUser.objects.filter(email_hash=email_hash).first()
        created = False

        if not user:
            user = CustomUser.objects.create(
                email=google_email,
                nickname=idinfo.get('name', f"user_{email_hash[:8]}"),
                currency_preference='USD',
                is_active=True
            )
            created = True

        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'created': created,
        }, status=status.HTTP_200_OK)

    except ValueError:
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
    serializer = PasswordResetRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email'].lower().strip()

    email_hash = CustomUser.objects._generate_email_hash(email)

    if not CustomUser.objects.filter(email_hash=email_hash).exists():
        return Response({
            'message': 'If an account with this email exists, a password reset code has been sent.',
            'email': email,
        }, status=status.HTTP_200_OK)

    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = timezone.now() + timedelta(minutes=10)

    PasswordResetOTP.objects.filter(email=email, used=False).update(used=True)

    otp = PasswordResetOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

    try:
        send_mail(
            subject='Password Reset Code - Financial Monitor',
            message=f'Your password reset code is: {code}\n\nThis code will expire in 10 minutes.',
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(
                settings, 'DEFAULT_FROM_EMAIL') else 'noreply@financialmonitor.com',
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        otp.delete()
        return Response(
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
    serializer = PasswordResetConfirmSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email'].lower().strip()
    code = serializer.validated_data['code']
    new_password = serializer.validated_data['new_password']

    email_hash = CustomUser.objects._generate_email_hash(email)

    try:
        otp = PasswordResetOTP.objects.filter(
            code=code,
            used=False
        ).latest('created_at')

        if hasattr(otp, 'email_hash') and otp.email_hash != email_hash:
            return Response({'error': 'Invalid OTP code. Please check your code and try again.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            return Response(
                {'error': 'OTP code has expired or is invalid. Please request a new code.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = CustomUser.objects.get(email_hash=email_hash)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        user.set_password(new_password)
        user.save()

        otp.mark_as_used()

        filter_kwargs = {'used': False}
        if hasattr(PasswordResetOTP, 'email_hash'):
            filter_kwargs['email_hash'] = email_hash
        else:
            filter_kwargs['email'] = email

        PasswordResetOTP.objects.filter(
            **filter_kwargs).exclude(pk=otp.pk).update(used=True)

        return Response({
            'message': 'Password has been reset successfully.',
        }, status=status.HTTP_200_OK)

    except PasswordResetOTP.DoesNotExist:
        return Response(
            {'error': 'Invalid OTP code. Please check your code and try again.'},
            status=status.HTTP_400_BAD_REQUEST
        )


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


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
        result = SMSService.setup_2fa_sms(request.user, phone_number)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response(
            {'error': 'Failed to set up SMS 2FA. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def sms_2fa_verify_view(request):
    sms_2fa_verify_view.throttle_scope = 'sms_2fa_verify'

    email = request.data.get('email', '').lower().strip()
    code = request.data.get('code')

    if not email or not code:
        return Response({'error': 'Email and verification code are required.'}, status=status.HTTP_400_BAD_REQUEST)

    email_hash = CustomUser.objects._generate_email_hash(email)
    user = CustomUser.objects.filter(email_hash=email_hash).first()

    if not user:
        return Response({'error': 'Invalid credentials or code.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        otp = SMSVerificationOTP.objects.get(user=user)

        if not otp.is_valid():
            return Response({'error': 'The code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp.code != code:
            otp.increment_attempts()
            return Response({'error': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.mark_as_used()

        refresh = RefreshToken.for_user(user)
        AuditService.log_login_success(user, _get_client_ip(request))

        return Response({
            'success': True,
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    except SMSVerificationOTP.DoesNotExist:
        return Response({'error': '2FA session not found. Please log in again.'}, status=status.HTTP_400_BAD_REQUEST)


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


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def resend_verification_view(request):
    resend_verification_view.throttle_scope = 'resend_verification'
    email = request.data.get('email', '').lower().strip()

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    email_hash = CustomUser.objects._generate_email_hash(email)
    user = CustomUser.objects.filter(email_hash=email_hash).first()

    if not user:
        return Response({'message': 'If the account exists and is unverified, a new code has been sent.'}, status=status.HTTP_200_OK)

    if user.is_active:
        return Response({'error': 'This account is already verified.'}, status=status.HTTP_400_BAD_REQUEST)

    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = timezone.now() + timedelta(minutes=15)

    RegistrationOTP.objects.filter(
        email_hash=email_hash, used=False).update(used=True)

    RegistrationOTP.objects.create(
        email=email,
        code=code,
        expires_at=expires_at
    )

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
