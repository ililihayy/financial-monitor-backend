"""
Audit Logging Service with tamper-detection checksums.

Logs sensitive actions (password changes, 2FA toggle, category deletions,
large transactions, etc.) to a dedicated audit log with HMAC integrity.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('audit')


class AuditService:
    """
    Structured audit logger.

    Every audit entry is a JSON line containing:
    - timestamp, action, user, ip, detail, checksum

    The checksum is an HMAC-SHA256 over the rest of the payload,
    making retrospective tampering detectable.
    """

    @staticmethod
    def _get_hmac_key() -> bytes:
        return settings.SECRET_KEY[:32].encode('utf-8')

    @classmethod
    def _compute_checksum(cls, payload: str) -> str:
        """HMAC-SHA256 hex digest of *payload*."""
        return hmac.new(
            cls._get_hmac_key(),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def log(
        cls,
        action: str,
        user: Optional[Any] = None,
        ip: Optional[str] = None,
        detail: Optional[Dict] = None,
    ) -> Dict:
        """
        Write an audit log entry.

        Args:
            action:  Short action identifier, e.g. ``password_change``.
            user:    User instance or email string (``None`` for anonymous).
            ip:      Client IP address.
            detail:  Arbitrary dict with action-specific context.

        Returns:
            The full audit entry dict (for testing / further processing).
        """
        entry = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'user': str(getattr(user, 'email', user) or 'anonymous'),
            'ip': ip or 'unknown',
            'detail': detail or {},
        }

        # Compute checksum over the serialised payload (excluding checksum itself)
        payload = json.dumps(entry, sort_keys=True, default=str)
        entry['checksum'] = cls._compute_checksum(payload)

        logger.info(json.dumps(entry, default=str))
        return entry

    @classmethod
    def verify_entry(cls, entry: Dict) -> bool:
        """Verify that an audit entry has not been tampered with."""
        checksum = entry.pop('checksum', None)
        if not checksum:
            return False
        payload = json.dumps(entry, sort_keys=True, default=str)
        expected = cls._compute_checksum(payload)
        entry['checksum'] = checksum  # restore for caller
        return hmac.compare_digest(checksum, expected)

    # ---- Convenience helpers for common actions ----

    @classmethod
    def log_password_change(cls, user, ip: str):
        cls.log('password_change', user=user, ip=ip)

    @classmethod
    def log_2fa_enabled(cls, user, ip: str):
        cls.log('2fa_enabled', user=user, ip=ip)

    @classmethod
    def log_2fa_disabled(cls, user, ip: str):
        cls.log('2fa_disabled', user=user, ip=ip)

    @classmethod
    def log_login_success(cls, user, ip: str):
        cls.log('login_success', user=user, ip=ip)

    @classmethod
    def log_login_failed(cls, email: str, ip: str):
        cls.log('login_failed', user=email, ip=ip, detail={'email': email})

    @classmethod
    def log_category_deleted(cls, user, ip: str, category_name: str, soft: bool):
        cls.log('category_deleted', user=user, ip=ip, detail={
            'category': category_name,
            'soft_delete': soft,
        })

    @classmethod
    def log_large_transaction(cls, user, ip: str, amount, threshold):
        cls.log('large_transaction', user=user, ip=ip, detail={
            'amount': str(amount),
            'threshold': str(threshold),
        })

    @classmethod
    def log_pii_warning(cls, user, ip: str, pii_types: list):
        cls.log('pii_warning', user=user, ip=ip, detail={
            'detected_types': pii_types,
        })
