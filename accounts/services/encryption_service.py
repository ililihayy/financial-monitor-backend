import base64
import logging
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

logger = logging.getLogger('security')


class EncryptionService:
    """
    Symmetric encryption service backed by AES-GCM (AEAD).

    The encryption key is derived from the ``FIELD_ENCRYPTION_KEY`` setting.
    Supports 256-bit keys. If an old 44-character base64 Fernet key is provided,
    it will be automatically decoded to raw bytes.
    """

    _aesgcm = None

    @classmethod
    def _get_aesgcm(cls) -> AESGCM:
        """Lazy-initialise and cache the AESGCM instance."""
        if cls._aesgcm is None:
            key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
            
            if not key:
                # Створюємо детермінований 32-байтний ключ із SECRET_KEY
                raw_key = settings.SECRET_KEY.encode('utf-8')[:32].ljust(32, b'\0')
            else:
                if isinstance(key, str):
                    try:
                        # Якщо це старий ключ від Fernet (base64 рядок), декодуємо його в байты
                        raw_key = base64.urlsafe_b64decode(key.encode('utf-8'))
                    except Exception:
                        raw_key = key.encode('utf-8')[:32].ljust(32, b'\0')
                else:
                    raw_key = key

            # Переконуємося, що довжина ключа рівна 32 байтам для AES-256
            if len(raw_key) != 32:
                raw_key = raw_key[:32].ljust(32, b'\0')

            cls._aesgcm = AESGCM(raw_key)
        return cls._aesgcm

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-GCM and return base64 string containing nonce + ciphertext.
        """
        if not plaintext:
            return plaintext
        
        aesgcm = cls._get_aesgcm()
        # Стандартний розмір nonce для GCM — 12 байт
        nonce = os.urandom(12)
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Склеюємо nonce та ciphertext разом, після чого кодуємо в base64
        return base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8')

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Decrypt an AES-GCM token back to plaintext.
        """
        if not ciphertext:
            return ciphertext
        
        aesgcm = cls._get_aesgcm()
        try:
            raw_data = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            if len(raw_data) < 12:
                raise ValueError("Ciphertext is too short to contain a valid nonce.")
            
            # Витягуємо перші 12 байт nonce, решта — сам шифротекст із тегом автентифікації
            nonce = raw_data[:12]
            actual_ciphertext = raw_data[12:]
            
            return aesgcm.decrypt(nonce, actual_ciphertext, None).decode('utf-8')
        except (InvalidTag, Exception) as exc:
            logger.warning('Field decryption failed: %s', exc)
            return ciphertext

    @classmethod
    def rotate_key(cls, ciphertext: str, new_key: str) -> str:
        """
        Re-encrypt *ciphertext* under a new key using AES-GCM.
        """
        plaintext = cls.decrypt(ciphertext)
        
        if isinstance(new_key, str):
            try:
                raw_new_key = base64.urlsafe_b64decode(new_key.encode('utf-8'))
            except Exception:
                raw_new_key = new_key.encode('utf-8')[:32].ljust(32, b'\0')
        else:
            raw_new_key = new_key
            
        new_aesgcm = AESGCM(raw_new_key[:32].ljust(32, b'\0'))
        nonce = os.urandom(12)
        ciphertext = new_aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        return base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8')