# FinSecure Monitor — Agent Instructions

## Project Overview

Django REST Framework backend for a secure financial expense monitoring system with ML-based expense forecasting. Diploma project demonstrating production-ready practices.

## Tech Stack

| Layer      | Technology                                                          |
| ---------- | ------------------------------------------------------------------- |
| Framework  | Django 5.2, DRF 3.16                                                |
| Database   | PostgreSQL (psycopg 3.x + psycopg2)                                 |
| Auth       | SimpleJWT 5.5 (access 15 min, refresh 7 days, rotation + blacklist) |
| 2FA        | django-otp 1.7 (TOTP — Google Authenticator / Authy compatible)     |
| OAuth      | Google ID token via `google-auth`                                   |
| ML         | scikit-learn 1.8, numpy 2.4, pandas 2.3                             |
| Schema     | drf-spectacular (OpenAPI 3, Swagger UI at `/api/docs/`)             |
| Security   | django-csp, django-cors-headers, django-environ, django-axes 8.3    |
| Encryption | cryptography (Fernet — field-level AES-128-CBC at rest)             |

## Project Structure

```
financial_monitor/     # Django project config
  settings.py          # All config (env-driven via django-environ)
  urls.py              # Root router (admin, api/auth, api/categories, api/transactions, api/analytics)
  middleware.py        # SecurityLoggingMiddleware — logs 401/403, rate-limit hits, data mutations

accounts/              # Auth app
  models.py            # CustomUser (email PK, monthly_budget), PasswordResetOTP
  serializers.py       # Registration, Login, Google, PasswordReset serializers
  views.py             # register, login (+2FA check), refresh, logout, profile, google_auth,
                       # password_reset, totp_setup, totp_confirm, totp_disable, totp_status
  urls.py
  services/
    totp_service.py    # TOTPService — setup/confirm/verify/disable TOTP 2FA
    encryption_service.py  # EncryptionService — Fernet encrypt/decrypt/rotate
    pii_detection_service.py  # PIIDetectionService — regex PII scanner
    audit_service.py   # AuditService — HMAC-signed audit log entries

transactions/          # Core business app
  models.py            # Category (soft-delete, Income/Expense), Transaction
                       # Transaction has: is_suspicious, anomaly_score, predicted_category, is_encrypted
  serializers.py       # CategorySerializer, TransactionSerializer (PII warnings + new ML fields)
  views.py             # CategoryListCreate, CategoryDetail, TransactionListCreate, TransactionDetail,
                       # dashboard_view, forecast_view, balance_view, ai_insights_view, trend_view,
                       # anomaly_detection_view, auto_categorize_view, budget_alert_view, health_score_view
  urls_categories.py
  urls_transactions.py
  urls_analytics.py
  services/
    finance_service.py # FinanceService — balance, aggregation, dashboard summary, pie chart
    ml_service.py      # MLForecastService, AnomalyDetectionService, AutoCategorizationService,
                       # BudgetAlertService, FinancialHealthService, MLRetrainingService
  management/commands/
    populate_test_data.py
```

## Key Conventions

### Auth Pattern

- All endpoints require `Authorization: Bearer <access_token>` except `register`, `login`, `refresh`, `google`, `password-reset*`.
- Token refresh rotates the refresh token and blacklists the old one.
- `USERNAME_FIELD = 'email'` on `CustomUser`; no username field exists.

### Service Layer Pattern

Business logic lives exclusively in `transactions/services/`. Views are thin — they validate input, call services, return responses. Do not put DB queries or calculations in views.

### Category Ownership

- `user=None` → system-default category (all users see it, cannot be deleted).
- `user=<user>` → user-created category (owner-only access).
- Soft-delete: if a category has linked transactions, `is_active=False` is set instead of hard delete.

### Transaction Ownership

All transaction queries **must** filter by `user=request.user` to enforce row-level isolation.

### Rate Limits (ScopedRateThrottle)

| Scope      | Limit    |
| ---------- | -------- |
| `login`    | 5/minute |
| `forecast` | 20/hour  |
| `default`  | 100/hour |

Apply with `@throttle_classes([ScopedRateThrottle])` and set `request.throttle_scope` or use the scope name.

## Environment Variables

Required env vars (in `.env`):

```env
DEBUG=True
SECRET_KEY=<strong-random-key>
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:pass@host:5432/dbname
CORS_ALLOWED_ORIGINS=https://localhost:3000
GOOGLE_OAUTH_CLIENT_ID=<google-client-id>          # optional, for Google auth
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend  # dev default

# New in Phase 1 security hardening:
FIELD_ENCRYPTION_KEY=<fernet-key>    # generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
LARGE_TRANSACTION_THRESHOLD=10000.00 # audit threshold (default 10 000)
```

## Database

PostgreSQL only. Uses `dj-database-url` to parse `DATABASE_URL`.  
Custom indexes on `Transaction`: `(user, date)` and `(user, category, date)`.

## Running the Project

```bash
# Activate venv (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Migrate
python manage.py makemigrations
python manage.py migrate

# Seed test data
python manage.py populate_test_data

# Start server
python manage.py runserver

# Interactive API docs
# https://localhost:8000/api/docs/        ← Swagger UI
# https://localhost:8000/api/redoc/       ← ReDoc
```

## Adding New Endpoints — Checklist

1. Create/update model in `transactions/models.py` or `accounts/models.py`.
2. Create/update serializer with field-level validation.
3. Add business logic to the appropriate service in `transactions/services/`.
4. Create view (thin: validate → call service → return Response).
5. Register URL in the relevant `urls_*.py` file.
6. Apply `@permission_classes([IsAuthenticated])` unless the endpoint is intentionally public.
7. Apply `@throttle_classes([ScopedRateThrottle])` for sensitive endpoints.
8. Run `python manage.py makemigrations` and `migrate` for model changes.

## ML Service Notes

`MLForecastService.get_comprehensive_analysis(user, current_balance)`:

- Requires **≥ 3 months** of expense history; returns `{"status": "insufficient_data"}` otherwise.
- Aggregates expenses monthly (last 12 months by default).
- Trains a `LinearRegression` model; returns `predicted_amount`, `confidence_score` (R²), `trend_direction`, `historical_trends`, and `mathematical_summary`.

## Security Hardening Checklist

- [x] JWT token blacklist on logout and rotation.
- [x] `SecurityLoggingMiddleware` logs 401/403, 429 (rate-limit), and sensitive mutations.
- [x] `CSPMiddleware` (Content Security Policy).
- [x] `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`.
- [x] HSTS + secure cookies enforced in production (`DEBUG=False`).
- [x] Passwords validated through Django's full built-in validator stack.
- [x] All secrets loaded from `.env` (never hardcoded).
- [x] Transaction amount `> 0` and `≤ 9,999,999,999.99` enforced in serializer.
- [x] Transaction date cannot be in the future or more than 50 years in the past.
- [x] **2FA (TOTP)**: Google Authenticator / Authy via `django-otp`. Optional per user; login gate enforces token when enabled.
- [x] **Field-Level Encryption**: Transaction descriptions encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).
- [x] **Brute-Force Protection**: `django-axes` locks IP+username after 5 failed login attempts for 1 hour.
- [x] **Audit Log with Checksums**: `AuditService` writes HMAC-SHA256 signed JSON lines to `logs/audit.log` for password changes, 2FA events, large transactions, and PII warnings.
- [x] **PII Detection**: `PIIDetectionService` scans transaction descriptions for credit cards (Luhn-validated), SSNs, IBANs, phone numbers, emails, and passport numbers before save.

## ML Services Quick Reference

| Class                       | Method                                      | Minimum Data             | Description                                       |
| --------------------------- | ------------------------------------------- | ------------------------ | ------------------------------------------------- |
| `MLForecastService`         | `get_comprehensive_analysis(user, balance)` | 3 months                 | Linear Regression spend forecast                  |
| `AnomalyDetectionService`   | `detect_anomalies(user)`                    | 20 transactions          | Isolation Forest batch scan                       |
| `AnomalyDetectionService`   | `score_single(user, txn)`                   | 20 transactions          | Score a single new transaction                    |
| `AutoCategorizationService` | `predict_category(user, description)`       | 30 labelled transactions | TF-IDF + Random Forest category prediction        |
| `AutoCategorizationService` | `auto_label(user, txn)`                     | 30 labelled transactions | Auto-set `predicted_category` if confidence ≥ 0.6 |
| `BudgetAlertService`        | `get_budget_prediction(user)`               | None                     | Velocity-based budget-hit date estimate           |
| `FinancialHealthService`    | `calculate_health_score(user)`              | 2 months                 | Composite 0-100 score with grade                  |
| `MLRetrainingService`       | `retrain_anomaly_model_async(user)`         | —                        | Daemon thread background retrain                  |
| `MLRetrainingService`       | `auto_categorize_async(user, txn)`          | —                        | Daemon thread auto-categorization                 |

ML models are **stateless / in-process**: re-trained on every request using the user's stored transactions. For high-traffic production, replace daemon threads with `django-rq` or `Celery`.

## API Quick Reference

| Method               | URL                                 | Auth     | Description                           |
| -------------------- | ----------------------------------- | -------- | ------------------------------------- |
| POST                 | `/api/auth/register/`               | Public   | Register, returns tokens              |
| POST                 | `/api/auth/login/`                  | Public   | Login, returns tokens                 |
| POST                 | `/api/auth/refresh/`                | Public   | Rotate access token                   |
| POST                 | `/api/auth/logout/`                 | Required | Blacklist refresh token               |
| GET                  | `/api/auth/profile/`                | Required | Current user profile                  |
| POST                 | `/api/auth/google/`                 | Public   | Google OAuth login/register           |
| POST                 | `/api/auth/password-reset/`         | Public   | Send OTP to email                     |
| POST                 | `/api/auth/password-reset/confirm/` | Public   | Confirm OTP + set new password        |
| GET/POST             | `/api/categories/`                  | Required | List or create categories             |
| GET/PUT/PATCH/DELETE | `/api/categories/{id}/`             | Required | Category detail (own only)            |
| GET/POST             | `/api/transactions/`                | Required | List (filterable) or create           |
| GET/PUT/PATCH/DELETE | `/api/transactions/{id}/`           | Required | Transaction detail (own only)         |
| GET                  | `/api/analytics/dashboard/`         | Required | Totals + category distribution        |
| GET                  | `/api/analytics/forecast/`          | Required | Linear Regression spend forecast      |
| GET                  | `/api/analytics/balance/`           | Required | Monthly balance                       |
| GET                  | `/api/analytics/insights/`          | Required | Rule-based spending insights          |
| GET                  | `/api/analytics/trend/`             | Required | Monthly income/expense trend          |
| GET                  | `/api/analytics/anomalies/`         | Required | Isolation Forest anomaly detection    |
| POST                 | `/api/analytics/categorize/`        | Required | Auto-categorize by description        |
| GET                  | `/api/analytics/budget-alert/`      | Required | Budget velocity + hit-date prediction |
| GET                  | `/api/analytics/health-score/`      | Required | Financial health score 0-100          |
| POST                 | `/api/auth/2fa/setup/`              | Required | Begin 2FA — returns QR code           |
| POST                 | `/api/auth/2fa/confirm/`            | Required | Confirm 2FA with first TOTP token     |
| POST                 | `/api/auth/2fa/disable/`            | Required | Disable 2FA (requires valid token)    |
| GET                  | `/api/auth/2fa/status/`             | Required | Check if 2FA is enabled               |
| GET                  | `/api/docs/`                        | Public   | Swagger UI                            |
| GET                  | `/api/redoc/`                       | Public   | ReDoc                                 |
| GET                  | `/api/schema/`                      | Public   | OpenAPI schema JSON                   |
