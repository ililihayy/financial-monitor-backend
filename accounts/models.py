"""
Custom User model for the Financial Monitor application.

Uses email as the primary identifier with currency preference and registration timestamp.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from .services import EncryptionService
import hashlib
from django.conf import settings


class CustomUserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier.
    Uses a blind index (email_hash) for searching encrypted emails.
    """

    def _generate_email_hash(self, email):
        """
        Generate a deterministic HMAC-like hash for searching.
        Uses SECRET_KEY as a salt to prevent rainbow table attacks.
        """
        if not email:
            return None
        # Normalize and hash the email with the system's secret key
        salt = getattr(settings, 'SECRET_KEY', 'default-salt')
        return hashlib.sha256((email.lower() + salt).encode()).hexdigest()

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        The email will be encrypted and hashed in the model's save method.
        """
        if not email:
            raise ValueError('The Email field must be set')

        email = self.normalize_email(email)
        # Note: Encryption/Hashing is handled by the CustomUser.save() method
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        """
        Overridden to support searching by the encrypted email's blind index.
        """
        return self.get(email_hash=self._generate_email_hash(email))


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with encrypted email storage and a blind index for searching.
    """

    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('UAH', 'Ukrainian Hryvnia'),
    ]

    # Email is stored as ciphertext, so we use TextField and remove unique=True
    email = models.TextField(
        verbose_name='Encrypted Email Address',
        help_text='Stored in encrypted format (AES-128).'
    )
    # Blind index for searching and enforcing uniqueness
    email_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='Email Hash'
    )
    nickname = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Nickname'
    )
    currency_preference = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD'
    )
    date_joined = models.DateTimeField(default=timezone.now)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    monthly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Phone Number'
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def save(self, *args, **kwargs):
        """
        Encrypt email and generate blind index hash before saving.
        """
        if self.email and not self.email.startswith('gAAAA'):
            clean_email = self.email.lower().strip()
            # Generate deterministic hash for searching
            salt = getattr(settings, 'SECRET_KEY', 'default-salt')
            self.email_hash = hashlib.sha256(
                (clean_email + salt).encode()).hexdigest()
            # Encrypt the actual email value
            self.email = EncryptionService.encrypt(clean_email)

        super().save(*args, **kwargs)

    @property
    def decrypted_email(self):
        """
        Helper property to get the plaintext email.
        """
        return EncryptionService.decrypt(self.email)

    def __str__(self):
        """Return decrypted email for readability in admin/logs."""
        return self.decrypted_email


class PasswordResetOTP(models.Model):
    """
    Model for storing password reset OTP codes.
    Uses encrypted email storage and a blind index for searching.
    """

    # Email is stored as ciphertext
    email = models.TextField(
        verbose_name='Encrypted Email Address',
        help_text='Encrypted email address of the user requesting password reset.'
    )
    # Blind index for searching (SHA-256)
    email_hash = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name='Email Hash'
    )
    code = models.CharField(
        max_length=6,
        verbose_name='OTP Code',
        help_text='6-digit OTP code for password reset.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    expires_at = models.DateTimeField(
        verbose_name='Expires At'
    )
    used = models.BooleanField(
        default=False,
        verbose_name='Used'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Used At'
    )

    class Meta:
        verbose_name = 'Password Reset OTP'
        verbose_name_plural = 'Password Reset OTPs'
        ordering = ['-created_at']
        indexes = [
            # Search by hash + code instead of raw email
            models.Index(fields=['email_hash', 'code']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        """
        Encrypt email and generate blind index hash before saving.
        """
        if self.email and not self.email.startswith('gAAAA'):
            clean_email = self.email.lower().strip()
            # Generate deterministic hash for searching
            salt = getattr(settings, 'SECRET_KEY', 'default-salt')
            self.email_hash = hashlib.sha256(
                (clean_email + salt).encode()).hexdigest()
            # Encrypt the actual email value
            self.email = EncryptionService.encrypt(clean_email)

        super().save(*args, **kwargs)

    @property
    def decrypted_email(self):
        """
        Helper property to get the plaintext email.
        """
        return EncryptionService.decrypt(self.email)

    def __str__(self):
        """String representation of the OTP using the decrypted email."""
        return f"OTP for {self.decrypted_email} - {self.code}"

    def is_valid(self):
        """Check if the OTP code is still valid (not used and not expired)."""
        return not self.used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark this OTP code as used."""
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])


class RegistrationOTP(models.Model):
    """
    Model for storing registration verification OTP codes.
    Uses encrypted email storage and a blind index for searching.
    """

    # Email is stored as ciphertext
    email = models.TextField(
        verbose_name='Encrypted Email Address',
        help_text='Encrypted email address of the user registering.'
    )
    # Blind index for searching (SHA-256)
    email_hash = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name='Email Hash'
    )
    code = models.CharField(
        max_length=6,
        verbose_name='OTP Code',
        help_text='6-digit OTP code for registration verification.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    expires_at = models.DateTimeField(
        verbose_name='Expires At'
    )
    used = models.BooleanField(
        default=False,
        verbose_name='Used'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Used At'
    )

    class Meta:
        verbose_name = 'Registration OTP'
        verbose_name_plural = 'Registration OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email_hash', 'code']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        """
        Encrypt email and generate blind index hash before saving.
        """
        if self.email and not self.email.startswith('gAAAA'):
            clean_email = self.email.lower().strip()
            # Generate deterministic hash for searching
            salt = getattr(settings, 'SECRET_KEY', 'default-salt')
            self.email_hash = hashlib.sha256(
                (clean_email + salt).encode()).hexdigest()
            # Encrypt the actual email value
            self.email = EncryptionService.encrypt(clean_email)

        super().save(*args, **kwargs)

    @property
    def decrypted_email(self):
        """
        Helper property to get the plaintext email.
        """
        return EncryptionService.decrypt(self.email)

    def __str__(self):
        """String representation of the OTP using the decrypted email."""
        return f"Registration OTP for {self.decrypted_email} - {self.code}"

    def is_valid(self):
        """Check if the OTP code is still valid (not used and not expired)."""
        return not self.used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark this OTP code as used."""
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])


class SMSVerificationOTP(models.Model):
    """
    Model for storing SMS-based 2FA OTP codes.
    Used for two-factor authentication via SMS to the user's phone number.
    """

    # Link to user
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sms_2fa_otp',
        verbose_name='User'
    )
    # Phone number (in E.164 format: +1234567890)
    phone_number = models.CharField(
        max_length=20,
        verbose_name='Phone Number',
        help_text='Phone number in E.164 format'
    )
    code = models.CharField(
        max_length=6,
        verbose_name='OTP Code',
        help_text='6-digit OTP code for 2FA verification.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    expires_at = models.DateTimeField(
        verbose_name='Expires At'
    )
    used = models.BooleanField(
        default=False,
        verbose_name='Used'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Used At'
    )
    attempts = models.IntegerField(
        default=0,
        verbose_name='Failed Attempts',
        help_text='Track failed verification attempts'
    )

    class Meta:
        verbose_name = 'SMS Verification OTP'
        verbose_name_plural = 'SMS Verification OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"SMS 2FA OTP for {self.user.decrypted_email} - {self.code}"

    def is_valid(self):
        """Check if the OTP code is still valid (not used and not expired)."""
        return not self.used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark this OTP code as used."""
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])

    def increment_attempts(self):
        """Increment failed verification attempts."""
        self.attempts += 1
        self.save(update_fields=['attempts'])
