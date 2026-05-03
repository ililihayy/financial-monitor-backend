"""
SMS Service using Twilio for sending OTP codes.

Handles SMS-based two-factor authentication.
"""

import random
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

try:
    from twilio.rest import Client
except ImportError:
    Client = None

logger = logging.getLogger('security')


class SMSService:
    """
    Service for sending SMS messages via Twilio.
    Handles OTP code generation and SMS transmission.
    """

    _client = None

    @classmethod
    def _get_client(cls):
        """
        Initialize and cache Twilio client.

        Returns:
            Client: Twilio REST client

        Raises:
            ValueError: If Twilio is not properly configured
        """
        if cls._client is None:
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)

            if not account_sid or not auth_token:
                raise ValueError(
                    'Twilio credentials are not configured. '
                    'Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in settings.'
                )

            if Client is None:
                raise ImportError(
                    'twilio package is not installed. Please run: pip install twilio')

            cls._client = Client(account_sid, auth_token)

        return cls._client

    @classmethod
    def send_sms(cls, phone_number: str, message: str) -> bool:
        """
        Send SMS message via Twilio.

        Args:
            phone_number: Recipient phone number in E.164 format (e.g., +1234567890)
            message: Message text to send

        Returns:
            bool: True if SMS was sent successfully, False otherwise
        """
        try:
            from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)

            if not from_number:
                raise ValueError(
                    'TWILIO_PHONE_NUMBER is not configured in settings.')

            client = cls._get_client()

            message_obj = client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )

            logger.info(
                f'SMS sent successfully to {phone_number}. SID: {message_obj.sid}')
            return True

        except Exception as e:
            logger.error(f'Failed to send SMS to {phone_number}: {str(e)}')
            return False

    @classmethod
    def generate_otp_code(cls) -> str:
        """
        Generate a 6-digit OTP code.

        Returns:
            str: 6-digit OTP code
        """
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    @classmethod
    def send_2fa_code(cls, phone_number: str, code: str) -> bool:
        """
        Send 2FA verification code via SMS.

        Args:
            phone_number: User's phone number in E.164 format
            code: 6-digit OTP code

        Returns:
            bool: True if SMS was sent successfully
        """
        message = (
            f'Your Financial Monitor 2FA code is: {code}\n\n'
            f'This code will expire in 10 minutes.\n\n'
            f'If you did not request this, please ignore this message.'
        )

        return cls.send_sms(phone_number, message)

    @classmethod
    def setup_2fa_sms(cls, user, phone_number: str):
        """
        Setup SMS-based 2FA for a user.

        Creates an OTP record and sends verification code to phone.

        Args:
            user: CustomUser instance
            phone_number: Phone number in E.164 format

        Returns:
            dict: Result with status and message

        Raises:
            ValueError: If phone number is invalid or SMS sending fails
        """
        from .models import SMSVerificationOTP

        # Validate phone number format (basic check for E.164)
        if not phone_number.startswith('+') or not phone_number[1:].isdigit():
            raise ValueError(
                'Phone number must be in E.164 format (e.g., +1234567890)'
            )

        # Delete any existing OTP for this user
        SMSVerificationOTP.objects.filter(user=user).delete()

        # Generate new OTP code
        code = cls.generate_otp_code()
        expires_at = timezone.now() + timedelta(minutes=10)

        # Create OTP record
        otp = SMSVerificationOTP.objects.create(
            user=user,
            phone_number=phone_number,
            code=code,
            expires_at=expires_at
        )

        # Send SMS
        if not cls.send_2fa_code(phone_number, code):
            otp.delete()
            raise ValueError('Failed to send SMS. Please try again.')

        return {
            'message': f'Verification code sent to {phone_number}',
            'phone_number': phone_number,
            'expires_in_minutes': 10
        }

    @classmethod
    def verify_2fa_code(cls, user, code: str, max_attempts: int = 3) -> tuple[bool, str]:
        """
        Verify 2FA code submitted by user.

        Args:
            user: CustomUser instance
            code: 6-digit OTP code submitted by user
            max_attempts: Maximum allowed failed attempts (default: 3)

        Returns:
            tuple: (success: bool, message: str)
        """
        from .models import SMSVerificationOTP

        try:
            otp = SMSVerificationOTP.objects.get(user=user)
        except SMSVerificationOTP.DoesNotExist:
            return False, 'No active 2FA code. Please request a new one.'

        # Check if code has expired
        if not otp.is_valid():
            return False, 'Verification code has expired. Please request a new one.'

        # Check if max attempts exceeded
        if otp.attempts >= max_attempts:
            otp.delete()
            return False, 'Too many failed attempts. Please request a new code.'

        # Verify code
        if otp.code != code:
            otp.increment_attempts()
            remaining = max_attempts - otp.attempts
            return False, f'Invalid code. {remaining} attempts remaining.'

        # Code is valid - mark as used
        otp.mark_as_used()
        return True, 'Code verified successfully.'

    @classmethod
    def disable_2fa(cls, user) -> bool:
        """
        Disable SMS 2FA for user.

        Args:
            user: CustomUser instance

        Returns:
            bool: True if 2FA was disabled
        """
        from .models import SMSVerificationOTP

        SMSVerificationOTP.objects.filter(user=user).delete()
        return True

    @classmethod
    def is_2fa_enabled(cls, user) -> bool:
        """
        Check if SMS 2FA is enabled for user.

        Args:
            user: CustomUser instance

        Returns:
            bool: True if active 2FA OTP exists and is valid
        """
        from .models import SMSVerificationOTP

        try:
            otp = SMSVerificationOTP.objects.get(user=user)
            return otp.is_valid() and not otp.used
        except SMSVerificationOTP.DoesNotExist:
            return False
