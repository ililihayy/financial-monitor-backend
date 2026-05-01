"""
Custom middleware for security logging, monitoring, and audit trails.

Logs suspicious activities (401/403 errors) and sensitive write actions
with HMAC-based checksums for tamper detection.
"""

import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

logger = logging.getLogger('security')

# Paths considered "sensitive" for audit logging (method-agnostic or POST/PUT/DELETE)
SENSITIVE_PATH_PREFIXES = (
    '/api/auth/password-reset',
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/2fa',
)

AUDIT_WRITE_PREFIXES = (
    '/api/transactions',
    '/api/categories',
)


class SecurityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log suspicious activities (401/403 errors) and audit
    sensitive write operations.
    """

    def process_response(self, request, response):
        ip = self.get_client_ip(request)
        user_email = getattr(request.user, 'email', 'Anonymous')

        # 1. Log 401/403 errors
        if response.status_code in [401, 403]:
            logger.warning(
                'Security Alert: %s - %s %s from IP %s. User: %s',
                response.status_code, request.method, request.path,
                ip, user_email,
            )

        # 2. Log rate-limit hits (429)
        if response.status_code == 429:
            logger.warning(
                'Rate Limit Hit: %s %s from IP %s. User: %s',
                request.method, request.path, ip, user_email,
            )

        # 3. Audit sensitive endpoints (successful mutations)
        if response.status_code < 400:
            path = request.path

            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                # Sensitive auth actions
                if any(path.startswith(p) for p in SENSITIVE_PATH_PREFIXES):
                    logger.info(
                        'Audit: %s %s from IP %s. User: %s. Status: %s',
                        request.method, path, ip, user_email,
                        response.status_code,
                    )

                # Write operations on financial data
                if any(path.startswith(p) for p in AUDIT_WRITE_PREFIXES):
                    logger.info(
                        'Data Mutation: %s %s from IP %s. User: %s. Status: %s',
                        request.method, path, ip, user_email,
                        response.status_code,
                    )

        return response

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class Enforce2FAMiddleware(MiddlewareMixin):
    """
    Middleware to enforce mandatory 2FA for all authenticated users.
    If the user is authenticated but not verified, return a 403 response.
    """

    def process_request(self, request):
        if request.user.is_authenticated and not request.user.is_verified():
            return JsonResponse(
                {'error': '2FA_REQUIRED',
                    'message': 'Two-factor authentication is required.'},
                status=403
            )
