"""
Field-Level Encryption Service using Fernet (AES-128-CBC + HMAC-SHA256).

Encrypts sensitive fields (e.g. transaction descriptions) at rest so that
even direct database access does not reveal the plaintext.
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger('security')


class EncryptionService:
    """
    Symmetric encryption service backed by Fernet.

    The encryption key is derived from the ``FIELD_ENCRYPTION_KEY`` setting.
    If no dedicated key is configured, the first 32 bytes of ``SECRET_KEY``
    are used (URL-safe base64 encoded to 44 chars) as a fallback.
    """

    _fernet = None

    @classmethod
    def _get_fernet(cls) -> Fernet:
        """Lazy-initialise and cache the Fernet instance."""
        if cls._fernet is None:
            key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
            if not key:
                # Derive a deterministic 32-byte key from SECRET_KEY
                raw = settings.SECRET_KEY.encode('utf-8')[:32].ljust(32, b'\0')
                key = base64.urlsafe_b64encode(raw).decode('utf-8')
            cls._fernet = Fernet(key.encode(
                'utf-8') if isinstance(key, str) else key)
        return cls._fernet

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypt a plaintext string and return the cipher-text as a UTF-8 string.

        Args:
            plaintext: The value to encrypt.

        Returns:
            Fernet token (URL-safe base64 encoded cipher-text).
        """
        if not plaintext:
            return plaintext
        fernet = cls._get_fernet()
        return fernet.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Decrypt a Fernet token back to plaintext.

        Args:
            ciphertext: The Fernet-encrypted value.

        Returns:
            Original plaintext string.

        If decryption fails (wrong key, corrupted data) the raw ciphertext
        is returned unchanged and a warning is logged.
        """
        if not ciphertext:
            return ciphertext
        fernet = cls._get_fernet()
        try:
            return fernet.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
        except (InvalidToken, Exception) as exc:
            logger.warning('Field decryption failed: %s', exc)
            return ciphertext

    @classmethod
    def rotate_key(cls, ciphertext: str, new_key: str) -> str:
        """
        Re-encrypt *ciphertext* under a new key.

        Useful during key rotation: decrypt with the current key, encrypt with *new_key*.
        """
        plaintext = cls.decrypt(ciphertext)
        new_fernet = Fernet(new_key.encode('utf-8')
                            if isinstance(new_key, str) else new_key)
        return new_fernet.encrypt(plaintext.encode('utf-8')).decode('utf-8')
