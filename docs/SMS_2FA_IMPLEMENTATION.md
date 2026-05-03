# SMS-Based 2FA Implementation Summary

## Overview

Replaced the old TOTP-based (authenticator app) two-factor authentication with a modern SMS-based 2FA using Twilio.

## Changes Made

### 1. Database Models

- **Created**: `SMSVerificationOTP` model in [accounts/models.py](accounts/models.py#L330)
  - Links to CustomUser (OneToOneField)
  - Stores phone number, OTP code, expiration time
  - Tracks failed attempts for security
  - Methods: `is_valid()`, `mark_as_used()`, `increment_attempts()`

### 2. SMS Service Layer

- **Created**: [accounts/services/sms_service.py](accounts/services/sms_service.py)
  - `SMSService` class with static methods for SMS operations
  - Methods:
    - `send_sms()` - Send SMS via Twilio
    - `send_2fa_code()` - Send 2FA code to phone
    - `generate_otp_code()` - Generate 6-digit OTP
    - `setup_2fa_sms()` - Initiate SMS 2FA setup
    - `verify_2fa_code()` - Verify submitted OTP code
    - `disable_2fa()` - Disable 2FA for user
    - `is_2fa_enabled()` - Check if 2FA is active

### 3. API Serializers

- **Added 3 new serializers** to [accounts/serializers.py](accounts/serializers.py#L342):
  - `SMS2FASetupSerializer` - Validates phone number in E.164 format
  - `SMS2FAVerifySerializer` - Validates OTP code (6 digits)
  - `SMS2FADisableSerializer` - Validates OTP for secure disable

### 4. API Endpoints

- **Removed TOTP endpoints**:
  - `/api/auth/2fa/setup/`
  - `/api/auth/2fa/confirm/`
  - `/api/auth/2fa/disable/`
  - `/api/auth/2fa/status/`

- **Added SMS 2FA endpoints**:
  - `POST /api/auth/sms-2fa/setup/` - Start 2FA setup, send code to phone
  - `POST /api/auth/sms-2fa/verify/` - Verify code and enable 2FA
  - `POST /api/auth/sms-2fa/disable/` - Disable 2FA (requires OTP verification)
  - `GET /api/auth/sms-2fa/status/` - Check 2FA status and phone number

### 5. Login Flow

- **Updated** [accounts/views.py](accounts/views.py#L213) `login_view`:
  - Detects if SMS 2FA is enabled for user
  - If enabled, sends new OTP to phone and returns `2fa_required: true`
  - Frontend must then call `/api/auth/sms-2fa/verify/` with the OTP code
  - Only returns JWT tokens after successful verification

### 6. Configuration

- **Updated** [financial_monitor/settings.py](financial_monitor/settings.py#L444):
  - Added Twilio configuration variables:
    - `TWILIO_ACCOUNT_SID`
    - `TWILIO_AUTH_TOKEN`
    - `TWILIO_PHONE_NUMBER`
  - Added throttle rates for SMS 2FA endpoints:
    - `sms_2fa_setup`: 3/minute
    - `sms_2fa_verify`: 5/minute
    - `sms_2fa_disable`: 3/minute

### 7. Dependencies

- **Updated** [requirements.txt](requirements.txt):
  - Added `twilio==9.2.0`

### 8. URL Routing

- **Updated** [accounts/urls.py](accounts/urls.py):
  - Replaced TOTP routes with SMS 2FA routes

## Environment Setup

Add these variables to your `.env` file:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

## Frontend Integration Flow

### Setup 2FA

```javascript
// 1. Send phone number to setup endpoint
POST /api/auth/sms-2fa/setup/
{
  "phone_number": "+1234567890"
}

// Response:
{
  "message": "Verification code sent to your phone",
  "phone_number": "+1234567890",
  "expires_in_minutes": 10
}

// 2. User receives SMS with 6-digit code, sends it to verify endpoint
POST /api/auth/sms-2fa/verify/
{
  "code": "123456"
}

// Response:
{
  "message": "SMS 2FA has been enabled successfully",
  "phone_number": "+1234567890"
}
```

### Login with 2FA

```javascript
// 1. Login with email/password
POST /api/auth/login/
{
  "email": "user@example.com",
  "password": "password123"
}

// If 2FA is enabled, response:
{
  "2fa_required": true,
  "message": "2FA code sent to +1234567890",
  "phone_number": "+1234567890"
}

// 2. User receives SMS with code, sends to verify endpoint
POST /api/auth/sms-2fa/verify/
{
  "code": "123456"
}

// Response:
{
  "message": "Code verified successfully."
}

// 3. Login again with code to get tokens
POST /api/auth/login/
{
  "email": "user@example.com",
  "password": "password123"
}

// Response:
{
  "user": {...},
  "tokens": {
    "refresh": "...",
    "access": "..."
  }
}
```

### Disable 2FA

```javascript
// 1. Request to disable (returns current OTP status)
POST /api/auth/sms-2fa/disable/
{
  "code": "123456"  // Current 2FA code from phone
}

// 2. Check status
GET /api/auth/sms-2fa/status/

// Response:
{
  "is_2fa_enabled": false
}
```

## Security Features

✅ **OTP Expiration**: 10 minutes  
✅ **Failed Attempt Tracking**: Max 3 attempts before code expires  
✅ **Rate Limiting**: Prevents brute force attacks  
✅ **Phone Number Validation**: E.164 format required  
✅ **One-Time Use**: Each code can only be used once  
✅ **Secure Disabling**: Requires current OTP verification

## Database Migration

Run migrations to create the `SMSVerificationOTP` table:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Notes

- The old TOTP service (`TOTPService`) is still in the codebase but no longer used
- The `phone_number` field already existed in `CustomUser` model
- All email-based OTP (registration, password reset) remains unchanged
- SMS 2FA is completely optional - users can use the app without enabling it
