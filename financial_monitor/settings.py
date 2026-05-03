"""
Django settings for financial_monitor project.

Production-ready configuration with security hardening, CORS, and environment variables.
"""

import os
from pathlib import Path
from datetime import timedelta
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file
if os.path.exists(os.path.join(BASE_DIR, '.env')):
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'), encoding='utf-8')

# Security Settings
SECRET_KEY = env(
    'SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = env('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'axes',
    # Local apps
    'accounts',
    'transactions',
    'drf_spectacular',
    'csp',
    'django_extensions',
]

MIDDLEWARE = [
    'csp.middleware.CSPMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # CORS middleware (early in stack)
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom logging middleware for security monitoring
    'financial_monitor.middleware.SecurityLoggingMiddleware',
    # Brute-force protection — must be last
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'financial_monitor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'financial_monitor.wsgi.application'

# Database Configuration (PostgreSQL - ready for Supabase)
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgresql://user:password@localhost:5432/financial_monitor'
    )
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}, # Стандарт NIST — мінімум 8 символів
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/hour',

        'login': '5/minute',
        'forecast': '20/hour',
        'advisor': '10/hour',
        'default': '100/hour',
        'resend_verification': '3/minute',  # Повторне надсилання коду реєстрації
        'password_reset': '5/hour',
        'sms_2fa_setup': '3/minute',  # SMS 2FA code sending
        'sms_2fa_verify': '5/minute',  # SMS 2FA code verification
        'sms_2fa_disable': '3/minute',  # Disabling SMS 2FA
    },
}

# Simple JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'UPDATE_LAST_LOGIN': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'FinSecure Monitor API',
    'DESCRIPTION': 'API для моніторингу витрат та доходів з ML-прогнозуванням',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_PATCH': True,
}

# CORS Configuration (Security: allow specific origins only)
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'https://localhost:3000',  # React default port
        'https://127.0.0.1:3000',
        'https://localhost:8080',  # Alternative frontend port
        'https://127.0.0.1:8080',
    ]
)

SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    # Brute-force protection (must be first)
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',  # Default Django authentication
]

# Site ID (required for django-allauth)
SITE_ID = 1

# Email Backend Configuration
# For development, use console backend to see emails in terminal
# For production, use SMTP backend with proper credentials
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)

# Email Settings (for production, configure these in .env)
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL',
                         default='noreply@financialmonitor.com')

# Google OAuth Configuration
# Set these in your .env file:
# GOOGLE_OAUTH_CLIENT_ID=your_google_client_id_here
# GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret_here (optional, for server-side)
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')

# =============================================================================
# Twilio SMS Configuration (for SMS-based 2FA)
# =============================================================================
# To set up Twilio:
# 1. Create an account at https://www.twilio.com/
# 2. Get your Account SID and Auth Token from the dashboard
# 3. Get or create a Twilio phone number
# 4. Set these environment variables in your .env file:
#    TWILIO_ACCOUNT_SID=your_account_sid
#    TWILIO_AUTH_TOKEN=your_auth_token
#    TWILIO_PHONE_NUMBER=+1234567890
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='')

# =============================================================================
# Django-Axes: Brute-Force Protection
# =============================================================================
AXES_FAILURE_LIMIT = 5                   # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 1                    # Lock duration in hours
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']  # Lock per IP + username
AXES_RESET_ON_SUCCESS = True             # Reset counter on successful login
AXES_ENABLED = True

# =============================================================================
# Field-Level Encryption (Fernet / AES-128-CBC + HMAC-SHA256)
# =============================================================================
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='')

# =============================================================================
# AI Financial Advisor (RAG pipeline)
# =============================================================================
# Gemini API key — required for the /api/analytics/advisor/ endpoint.
# Generate at: https://aistudio.google.com/app/apikey
# Set via environment variable: GOOGLE_API_KEY=AIza...
GOOGLE_API_KEY = env('GOOGLE_API_KEY', default='')

# LLM model used by FinancialAdvisorService.
# "gemini-2.5-flash" offers the best cost/quality ratio for financial Q&A.
# Override via: ADVISOR_LLM_MODEL=gemini-2.5-pro
ADVISOR_LLM_MODEL = env('ADVISOR_LLM_MODEL', default='gemini-2.5-flash')

# =============================================================================
# Audit Logging
# =============================================================================
LOGGING['handlers']['audit_file'] = {
    'level': 'INFO',
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'audit.log',
    'formatter': 'verbose',
}
LOGGING['loggers']['audit'] = {
    'handlers': ['audit_file', 'console'],
    'level': 'INFO',
    'propagate': False,
}

# Large transaction threshold — transactions above this trigger an audit entry
LARGE_TRANSACTION_THRESHOLD = env.float(
    'LARGE_TRANSACTION_THRESHOLD', default=10000.00)

# Оновлений формат налаштувань для django-csp 4.0+
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "'unsafe-inline'",
            "https://accounts.google.com",
            "https://www.gstatic.com",
        ),
        'style-src': (
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
        ),
        'font-src': ("'self'", "https://fonts.gstatic.com", "data:"),
        'img-src': (
            "'self'",
            "data:",
            "https://*.googleusercontent.com",
        ),
        'connect-src': (
            "'self'",
            "https://localhost:8000",
            "https://accounts.google.com",
        ),
    }
}

ADVISOR_DAILY_LIMIT = 7

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'my_cache_table',
    }
}
