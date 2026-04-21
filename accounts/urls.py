"""
URL configuration for accounts app (authentication endpoints).
"""

from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('refresh/', views.refresh_token_view, name='refresh'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.user_profile_view, name='profile'),
    path('google/', views.google_auth_view, name='google-auth'),
    path('password-reset/', views.password_reset_request_view,
         name='password-reset-request'),
    path('password-reset/confirm/', views.password_reset_confirm_view,
         name='password-reset-confirm'),
    # 2FA / TOTP
    path('2fa/setup/', views.totp_setup_view, name='2fa-setup'),
    path('2fa/confirm/', views.totp_confirm_view, name='2fa-confirm'),
    path('2fa/disable/', views.totp_disable_view, name='2fa-disable'),
    path('2fa/status/', views.totp_status_view, name='2fa-status'),
]
