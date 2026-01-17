"""
Admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, PasswordResetOTP


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Admin interface for CustomUser model."""
    
    list_display = ('email', 'currency_preference', 'date_joined', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'currency_preference', 'date_joined')
    search_fields = ('email',)
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Preferences', {'fields': ('currency_preference',)}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'currency_preference', 'is_staff', 'is_active'),
        }),
    )


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    """Admin interface for PasswordResetOTP model."""
    
    list_display = ('email', 'code', 'created_at', 'expires_at', 'used', 'used_at')
    list_filter = ('used', 'created_at', 'expires_at')
    search_fields = ('email', 'code')
    readonly_fields = ('created_at', 'expires_at', 'used_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'code')}),
        ('Status', {'fields': ('used', 'created_at', 'expires_at', 'used_at')}),
    )
