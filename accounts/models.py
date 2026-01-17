"""
Custom User model for the Financial Monitor application.

Uses email as the primary identifier with currency preference and registration timestamp.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier.
    
    Handles user creation with email as the primary field instead of username.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        
        Args:
            email: User's email address (required)
            password: User's password (optional for initial creation)
            **extra_fields: Additional fields (currency_preference, etc.)
            
        Returns:
            CustomUser: The created user instance
        """
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        
        Args:
            email: User's email address (required)
            password: User's password (required)
            **extra_fields: Additional fields
            
        Returns:
            CustomUser: The created superuser instance
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with email as the primary identifier.
    
    Fields:
        email: Primary identifier (unique)
        currency_preference: User's preferred currency (default: 'USD')
        date_joined: Timestamp of registration
        is_staff: Boolean for admin access
        is_active: Boolean for account status
    """
    
    # Currency choices (can be expanded)
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('UAH', 'Ukrainian Hryvnia'),
    ]

    email = models.EmailField(
        unique=True,
        max_length=255,
        verbose_name='Email Address',
        help_text='Required. Email address is used as the primary identifier.'
    )
    currency_preference = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        verbose_name='Currency Preference',
        help_text='Preferred currency for displaying financial data.'
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name='Date Joined',
        help_text='Timestamp when the user registered.'
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Staff Status',
        help_text='Designates whether the user can log into the admin site.'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Designates whether this user should be treated as active.'
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        """String representation of the user."""
        return self.email
