"""
Custom middleware for security logging and monitoring.

Logs suspicious activities (401/403 errors) for security analysis.
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('security')


class SecurityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log suspicious activities (401/403 errors).
    
    This helps in detecting potential security threats and unauthorized access attempts.
    """

    def process_response(self, request, response):
        """
        Process the response and log suspicious activities.
        
        Args:
            request: HttpRequest object
            response: HttpResponse object
            
        Returns:
            HttpResponse object
        """
        # Log 401 (Unauthorized) and 403 (Forbidden) errors
        if response.status_code in [401, 403]:
            logger.warning(
                f'Security Alert: {response.status_code} - {request.method} {request.path} '
                f'from IP {self.get_client_ip(request)}. '
                f'User: {getattr(request.user, "email", "Anonymous")}'
            )
        
        return response

    @staticmethod
    def get_client_ip(request):
        """
        Extract client IP address from request.
        
        Args:
            request: HttpRequest object
            
        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
