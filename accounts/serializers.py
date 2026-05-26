"""
Serializers for the accounts app with strict input validation.

Includes user registration and authentication serializers.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.conf import settings
import hashlib
from .models import CustomUser


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with strict validation.

    Validates email format, password strength, and ensures all required fields are present.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text='Password must meet Django password validation requirements.'
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Confirm password must match the password field.'
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'nickname', 'password',
                  'password_confirm', 'currency_preference', 'phone_number')
        extra_kwargs = {
            'email': {'required': True},
            'nickname': {'required': False},
            'currency_preference': {'required': False},
            'phone_number': {'required': True},
        }

    def validate_email(self, value):
        """
        Validate email format and uniqueness.

        Args:
            value: Email address to validate

        Returns:
            str: Validated email address

        Raises:
            serializers.ValidationError: If email is invalid or already exists
        """
        if not value:
            raise serializers.ValidationError("Email is required.")

        # Normalize email for comparison
        clean_email = value.lower().strip()

        # Generate email_hash using the same method as the model
        salt = getattr(settings, 'SECRET_KEY', 'default-salt')
        email_hash = hashlib.sha256((clean_email + salt).encode()).hexdigest()

        # Check if email_hash already exists (meaning email is taken)
        if CustomUser.objects.filter(email_hash=email_hash).exists():
            raise serializers.ValidationError(
                "A user with this email address is already registered.")

        return clean_email

    def validate(self, attrs):
        """
        Validate that password and password_confirm match.

        Args:
            attrs: Dictionary of serializer fields

        Returns:
            dict: Validated attributes

        Raises:
            serializers.ValidationError: If passwords don't match
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })
        return attrs

    def create(self, validated_data):
        """
        Create and return a new user instance.

        Args:
            validated_data: Validated serializer data

        Returns:
            CustomUser: The created user instance
        """
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(
            password=password, **validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information (read-only for sensitive data).
    """
    email = serializers.ReadOnlyField(source='decrypted_email')
    phone_number = serializers.ReadOnlyField(source='decrypted_phone_number')

    class Meta:
        model = CustomUser
        fields = (
            'id',
            'email',
            'phone_number',
            'nickname',
            'currency_preference',
            'date_joined'
        )
        read_only_fields = ('id', 'email', 'phone_number', 'nickname', 'date_joined')

    def update(self, instance, validated_data):
        instance.currency_preference = validated_data.get(
            'currency_preference', 
            instance.currency_preference
        )
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email and password.

    Validates credentials and returns user instance if valid.
    """

    email = serializers.EmailField(
        required=True,
        help_text='User email address.'
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='User password.'
    )

    def validate(self, attrs):
        """
        Validate user credentials.

        Args:
            attrs: Dictionary containing email and password

        Returns:
            dict: Validated attributes with user instance

        Raises:
            serializers.ValidationError: If credentials are invalid
        """
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            request = self.context.get('request')

            user = authenticate(
                request=request, email=email, password=password)

            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.'
                )
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.'
                )

            attrs['user'] = user
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".'
            )

        return attrs


class GoogleAuthSerializer(serializers.Serializer):
    """
    Serializer for Google authentication with ID token.

    Accepts a Google ID token from the frontend and validates it.
    """

    credential = serializers.CharField(
        required=True,
        help_text='Google ID token (credential) from Google One Tap or Google Login.'
    )

    def validate_credential(self, value):
        """
        Validate Google ID token.

        Args:
            value: Google ID token string

        Returns:
            str: Validated token string

        Raises:
            serializers.ValidationError: If token is invalid or empty
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Google credential is required.")
        return value.strip()


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.

    Accepts email and generates a 6-digit OTP code.
    """

    email = serializers.EmailField(
        required=True,
        help_text='Email address of the user requesting password reset.'
    )

    def validate_email(self, value):
        """
        Validate email format and existence.

        Args:
            value: Email address to validate

        Returns:
            str: Validated email address

        Raises:
            serializers.ValidationError: If email is invalid
        """
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.

    Accepts email, OTP code, and new password.
    """

    email = serializers.EmailField(
        required=True,
        help_text='Email address of the user.'
    )
    code = serializers.CharField(
        required=True,
        max_length=6,
        min_length=6,
        help_text='6-digit OTP code sent via email.'
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text='New password that meets Django password validation requirements.'
    )

    def validate_email(self, value):
        """Validate email format."""
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value.lower().strip()

    def validate_code(self, value):
        """
        Validate OTP code format (must be 6 digits).

        Args:
            value: OTP code to validate

        Returns:
            str: Validated code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        if not value or not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "OTP code must be exactly 6 digits.")
        return value


class RegistrationVerifySerializer(serializers.Serializer):
    """
    Serializer for registration email verification.

    Accepts email and OTP code to verify and activate the user account.
    """

    email = serializers.EmailField(
        required=True,
        help_text='Email address of the user.'
    )
    code = serializers.CharField(
        required=True,
        max_length=6,
        min_length=6,
        help_text='6-digit OTP code sent via email.'
    )

    def validate_email(self, value):
        """Validate email format."""
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value.lower().strip()

    def validate_code(self, value):
        """
        Validate OTP code format (must be 6 digits).

        Args:
            value: OTP code to validate

        Returns:
            str: Validated code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        if not value or not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "OTP code must be exactly 6 digits.")
        return value


class SMS2FASetupSerializer(serializers.Serializer):
    """
    Serializer for initiating SMS 2FA setup.

    Accepts phone number and sends verification code via SMS.
    """

    phone_number = serializers.CharField(
        required=True,
        max_length=20,
        help_text='Phone number in E.164 format (e.g., +1234567890)'
    )

    def validate_phone_number(self, value):
        """
        Validate phone number format (E.164).

        Args:
            value: Phone number to validate

        Returns:
            str: Validated phone number

        Raises:
            serializers.ValidationError: If phone number format is invalid
        """
        if not value:
            raise serializers.ValidationError("Phone number is required.")

        # Check if it starts with + and contains only digits
        if not value.startswith('+') or not value[1:].isdigit():
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g., +1234567890)"
            )

        return value


class SMS2FAVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying SMS 2FA code.

    Accepts OTP code and verifies it matches the sent code.
    """

    code = serializers.CharField(
        required=True,
        max_length=6,
        min_length=6,
        help_text='6-digit OTP code sent via SMS'
    )

    def validate_code(self, value):
        """
        Validate OTP code format (must be 6 digits).

        Args:
            value: OTP code to validate

        Returns:
            str: Validated code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        if not value or not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "Code must be exactly 6 digits."
            )
        return value


class SMS2FADisableSerializer(serializers.Serializer):
    """
    Serializer for disabling SMS 2FA.

    Requires verification with current OTP code for security.
    """

    code = serializers.CharField(
        required=True,
        max_length=6,
        min_length=6,
        help_text='6-digit OTP code for verification'
    )

    def validate_code(self, value):
        """
        Validate OTP code format (must be 6 digits).

        Args:
            value: OTP code to validate

        Returns:
            str: Validated code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        if not value or not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "Code must be exactly 6 digits."
            )
        return value
