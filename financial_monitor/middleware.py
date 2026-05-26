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

        if response.status_code in [401, 403]:
            logger.warning(
                'Security Alert: %s - %s %s from IP %s. User: %s',
                response.status_code, request.method, request.path,
                ip, user_email,
            )

        if response.status_code == 429:
            logger.warning(
                'Rate Limit Hit: %s %s from IP %s. User: %s',
                request.method, request.path, ip, user_email,
            )

        if response.status_code < 400:
            path = request.path

            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                if any(path.startswith(p) for p in SENSITIVE_PATH_PREFIXES):
                    logger.info(
                        'Audit: %s %s from IP %s. User: %s. Status: %s',
                        request.method, path, ip, user_email,
                        response.status_code,
                    )

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
    def process_request(self, request):
        if request.user.is_authenticated and not request.user.is_verified():
            return JsonResponse(
                {'error': '2FA_REQUIRED',
                    'message': 'Two-factor authentication is required.'},
                status=403
            )
