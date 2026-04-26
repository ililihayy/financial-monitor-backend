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
from datetime import timedelta
import random
from google.auth.transport import requests
from google.oauth2 import id_token
from .serializers import (
    UserRegistrationSerializer, UserSerializer, LoginSerializer,
    GoogleAuthSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
)
from .models import CustomUser, PasswordResetOTP
from .services import TOTPService, AuditService


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register_view(request):
    """
    Register a new user.

    POST /api/auth/register/
    Body: {
        "email": "user@example.com",
        "password": "securepassword123",
        "password_confirm": "securepassword123",
        "currency_preference": "USD"  # optional
    }

    Returns: {
        "user": {...},
        "tokens": {
            "refresh": "...",
            "access": "..."
        }
    }
    """
    serializer = UserRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_view(request):
    """
    Login user and return JWT tokens.

    POST /api/auth/login/
    Body: {
        "email": "user@example.com",
        "password": "securepassword123"
    }

    Returns: {
        "user": {...},
        "tokens": {
            "refresh": "...",
            "access": "..."
        }
    }
    """
    serializer = LoginSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.validated_data['user']

        # 2FA check: if enabled, require totp_token in payload
        if TOTPService.is_2fa_enabled(user):
            totp_token = request.data.get('totp_token')
            if not totp_token:
                return Response(
                    {'error': '2FA token is required.', '2fa_required': True},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not TOTPService.verify_token(user, totp_token):
                return Response(
                    {'error': 'Invalid 2FA token.', '2fa_required': True},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        AuditService.log_login_success(user, _get_client_ip(request))

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    # Audit failed login
    email = request.data.get('email', 'unknown')
    AuditService.log_login_failed(email, _get_client_ip(request))
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


# ========== 2FA / TOTP Views ==========

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def totp_setup_view(request):
    """
    Begin 2FA setup: returns a QR code and OTP URI for Google Authenticator.

    POST /api/auth/2fa/setup/
    """
    try:
        result = TOTPService.setup_2fa(request.user)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def totp_confirm_view(request):
    """
    Confirm 2FA setup by verifying a TOTP token from the authenticator app.

    POST /api/auth/2fa/confirm/
    Body: {"token": "123456"}
    """
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        success = TOTPService.confirm_2fa(request.user, str(token))
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if success:
        AuditService.log_2fa_enabled(request.user, _get_client_ip(request))
        return Response({'message': '2FA has been enabled successfully.'}, status=status.HTTP_200_OK)
    return Response({'error': 'Invalid token. Please try again.'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def totp_disable_view(request):
    """
    Disable 2FA (requires a valid TOTP token for security).

    POST /api/auth/2fa/disable/
    Body: {"token": "123456"}
    """
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        success = TOTPService.disable_2fa(request.user, str(token))
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if success:
        AuditService.log_2fa_disabled(request.user, _get_client_ip(request))
        return Response({'message': '2FA has been disabled.'}, status=status.HTTP_200_OK)
    return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def totp_status_view(request):
    """
    Check whether 2FA is enabled for the current user.

    GET /api/auth/2fa/status/
    """
    enabled = TOTPService.is_2fa_enabled(request.user)
    return Response({'is_2fa_enabled': enabled}, status=status.HTTP_200_OK)
