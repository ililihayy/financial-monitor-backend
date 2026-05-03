"""
URL configuration for accounts app (authentication endpoints).
"""

from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('register/verify/', views.register_verify_view, name='register-verify'),
    path('resend-verification/', views.resend_verification_view,
         name='resend-verification'),
    path('login/', views.login_view, name='login'),
    path('refresh/', views.refresh_token_view, name='refresh'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.user_profile_view, name='profile'),
    path('delete-account/', views.delete_account_view, name='delete-account'),
    path('google/', views.google_auth_view, name='google-auth'),
    path('password-reset/', views.password_reset_request_view,
         name='password-reset-request'),
    path('password-reset/confirm/', views.password_reset_confirm_view,
         name='password-reset-confirm'),
    # SMS-based 2FA
    path('sms-2fa/setup/', views.sms_2fa_setup_view, name='sms-2fa-setup'),
    path('sms-2fa/verify/', views.sms_2fa_verify_view, name='sms-2fa-verify'),
    path('sms-2fa/disable/', views.sms_2fa_disable_view, name='sms-2fa-disable'),
    path('sms-2fa/status/', views.sms_2fa_status_view, name='sms-2fa-status'),
]
