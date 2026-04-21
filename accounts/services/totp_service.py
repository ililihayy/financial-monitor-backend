"""
TOTP Two-Factor Authentication Service.

Provides Google Authenticator / Authy compatible TOTP setup, QR code generation,
and verification using django-otp's TOTP device model.
"""

import base64
import io
from typing import Dict, Optional

import qrcode
from django_otp.plugins.otp_totp.models import TOTPDevice


class TOTPService:
    """
    Service class for TOTP-based 2FA management.

    Wraps django-otp's TOTPDevice to provide a clean API for:
    - Enabling 2FA (creating an unconfirmed TOTP device + QR code)
    - Confirming 2FA (verifying a token against the unconfirmed device)
    - Verifying tokens on login
    - Disabling 2FA
    - Querying 2FA status
    """

    ISSUER_NAME = 'FinSecure Monitor'

    @staticmethod
    def get_user_device(user, confirmed: Optional[bool] = None) -> Optional[TOTPDevice]:
        """
        Get the user's TOTP device filtered by confirmation status.

        Args:
            user: CustomUser instance.
            confirmed: True for confirmed devices, False for unconfirmed, None for any.

        Returns:
            TOTPDevice or None.
        """
        devices = TOTPDevice.objects.filter(user=user)
        if confirmed is not None:
            devices = devices.filter(confirmed=confirmed)
        return devices.first()

    @staticmethod
    def is_2fa_enabled(user) -> bool:
        """Check whether the user has a confirmed TOTP device."""
        return TOTPDevice.objects.filter(user=user, confirmed=True).exists()

    @classmethod
    def setup_2fa(cls, user) -> Dict[str, str]:
        """
        Begin 2FA setup: create an unconfirmed TOTP device and return
        the provisioning URI + base64-encoded QR code PNG.

        If an unconfirmed device already exists, it is replaced.
        Raises ValueError if 2FA is already confirmed.
        """
        if cls.is_2fa_enabled(user):
            raise ValueError('2FA is already enabled for this account.')

        # Remove stale unconfirmed devices
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()

        device = TOTPDevice.objects.create(
            user=user,
            name='default',
            confirmed=False,
        )

        # Build otpauth:// URI
        otp_uri = device.config_url
        # Inject issuer if not present
        if 'issuer=' not in otp_uri:
            otp_uri += f'&issuer={cls.ISSUER_NAME.replace(" ", "%20")}'

        # Generate QR code as base64 PNG
        qr_img = qrcode.make(otp_uri)
        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            'otp_uri': otp_uri,
            'qr_code': f'data:image/png;base64,{qr_base64}',
        }

    @classmethod
    def confirm_2fa(cls, user, token: str) -> bool:
        """
        Confirm 2FA by verifying a TOTP token against the unconfirmed device.

        Returns True on success; False if the token is invalid.
        Raises ValueError if there is no unconfirmed device.
        """
        device = cls.get_user_device(user, confirmed=False)
        if device is None:
            raise ValueError('No pending 2FA setup found. Call setup first.')

        if device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            return True
        return False

    @classmethod
    def verify_token(cls, user, token: str) -> bool:
        """
        Verify a TOTP token for an already-confirmed device.

        Returns True if valid, False otherwise.
        Returns True automatically if 2FA is not enabled (no device).
        """
        device = cls.get_user_device(user, confirmed=True)
        if device is None:
            # 2FA not enabled — token check not required
            return True
        return device.verify_token(token)

    @classmethod
    def disable_2fa(cls, user, token: str) -> bool:
        """
        Disable 2FA after verifying a valid token.

        Returns True on success; False if the token is invalid.
        Raises ValueError if 2FA is not enabled.
        """
        device = cls.get_user_device(user, confirmed=True)
        if device is None:
            raise ValueError('2FA is not enabled for this account.')

        if not device.verify_token(token):
            return False

        device.delete()
        return True
