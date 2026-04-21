# Architecture

## Overview

FinSecure Monitor follows a layered, service-oriented architecture built on Django REST Framework. The design separates HTTP concerns (views/serializers) from business logic (services) and data persistence (models), making each layer independently testable.

```
┌─────────────────────────────────────────────┐
│              HTTP Clients                   │
│     React frontend / mobile / curl          │
└─────────────────┬───────────────────────────┘
                  │ HTTPS / JWT Bearer token
┌─────────────────▼───────────────────────────┐
│              Middleware Stack               │
│  CSPMiddleware → CorsMiddleware →           │
│  SecurityMiddleware → CsrfViewMiddleware →  │
│  AuthenticationMiddleware →                 │
│  SecurityLoggingMiddleware                  │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│                 DRF Router                  │
│  /api/auth/   /api/categories/              │
│  /api/transactions/   /api/analytics/       │
│  /api/docs/   /api/schema/                  │
└──────┬──────────────────────┬───────────────┘
       │                      │
┌──────▼───────┐     ┌────────▼────────────────┐
│  accounts    │     │       transactions       │
│  app         │     │       app                │
│              │     │                          │
│  Views       │     │  Views (thin)            │
│  Serializers │     │  Serializers             │
│  Models      │     │  Models                  │
│              │     │  Services ◄── ML + Finance│
└──────────────┘     └──────────────────────────┘
       │                      │
┌──────▼──────────────────────▼───────────────┐
│              PostgreSQL                     │
│  (Supabase-ready, dj-database-url)          │
└─────────────────────────────────────────────┘
```

---

## Apps

### `accounts` — Authentication

Responsible for all user identity concerns:

- **`CustomUser`** model — replaces Django's default `User`; uses `email` as `USERNAME_FIELD`. Supports currency preference (`USD`, `EUR`, `GBP`, `UAH`) and an optional unique `nickname`.
- **`PasswordResetOTP`** model — stores 6-digit codes with a `expires_at` timestamp (10 minutes TTL).
- **Views** — thin function-based views using `@api_view`, delegating to serializers for all validation.
- **Google OAuth** — verifies Google ID tokens server-side via `google-auth`, then `get_or_create` the user.

### `transactions` — Core Domain

Responsible for categories, transactions, and all analytics:

- **`Category`** model — two ownership modes:
  - `user=None`: system-default (visible to all, protected from deletion)
  - `user=<foreign key>`: user-created (owner-only, soft-deleted when has transactions)
- **`Transaction`** model — links a `user` to a `category` with `amount`, `date`, and optional `description`. Composite indexes on `(user, date)` and `(user, category, date)` for fast analytics queries.
- **Views** — class-based (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`) for CRUD; function-based for analytics endpoints.
- **Service layer** — all computation lives in `services/`.

---

## Service Layer

### `FinanceService`

```
finance_service.py
├── calculate_monthly_balance(user, year, month) → Decimal
├── aggregate_expenses_by_category(user, year, month, category_type) → List[Dict]
├── get_dashboard_totals(user, year, month) → Dict
├── get_pie_chart_data(user, year, month) → Dict
├── get_dashboard_summary(user, month, year) → Dict  ← includes percent change vs prev month
└── get_category_distribution(user, month, year) → List[Dict]
```

`get_dashboard_summary` computes percent changes by comparing the requested month against the previous month. Division-by-zero is guarded: returns `100.0` when the previous period is zero with a positive current value, `0.0` when both are zero.

### `MLForecastService`

```
ml_service.py
└── get_comprehensive_analysis(user, current_balance) → Dict
      │
      ├── Queries Transaction (Expense only, last 12 months)
      │   aggregated by TruncMonth
      │
      ├── Requires ≥ 3 data points → else {"status": "insufficient_data"}
      │
      ├── Trains LinearRegression (X = month index, y = monthly total)
      │
      ├── Predicts next month's spending (next_index = len(months))
      │
      └── Returns forecast + historical_trends + mathematical_summary
```

The R² coefficient (`confidence_score`) gives a 0–1 measure of how well the linear model fits historical data. `slope > 0` → `"increasing"` trend.

---

## Authentication Flow

```
Client                           Server
  │                                │
  │  POST /api/auth/login/         │
  │  { email, password }          │
  │──────────────────────────────► │
  │                         Authenticate user
  │                         Generate access (15 min)
  │                                + refresh (7 days)
  │ ◄────────────────────────────── │
  │  { user, tokens: {access, refresh} }
  │                                │
  │  GET /api/transactions/        │
  │  Authorization: Bearer <access>│
  │──────────────────────────────► │
  │                         JWTAuthentication validates token
  │ ◄────────────────────────────── │
  │  [transaction list]            │
  │                                │
  │  POST /api/auth/refresh/       │
  │  { refresh }                  │
  │──────────────────────────────► │
  │                         Old refresh token blacklisted
  │                         New refresh + access issued
  │ ◄────────────────────────────── │
  │  { access }                    │
  │                                │
  │  POST /api/auth/logout/        │
  │  { refresh }                  │
  │──────────────────────────────► │
  │                         Refresh token blacklisted
  │ ◄────────────────────────────── │
  │  { message: "Successfully..." }│
```

JWT configuration:

| Setting                  | Value      |
| ------------------------ | ---------- |
| Algorithm                | HS256      |
| Access token lifetime    | 15 minutes |
| Refresh token lifetime   | 7 days     |
| Rotate refresh tokens    | Yes        |
| Blacklist after rotation | Yes        |

---

## Security Architecture

### Defence-in-Depth Layers

1. **Network** — CORS whitelist (`CORS_ALLOWED_ORIGINS`); HSTS enforced in production.
2. **Application** — CSP headers via `django-csp`; XSS filter; `X-Frame-Options: DENY`; content-type sniffing prevention.
3. **Authentication** — JWT with short-lived access tokens; refresh token rotation + blacklist prevents reuse after logout or rotation.
4. **Authorisation** — Every resource query scoped to `user=request.user`. System categories protected from mutation.
5. **Input Validation** — All input passes through DRF serializers with explicit field validators before touching the database.
6. **Rate Limiting** — `ScopedRateThrottle` applied to login (brute-force protection) and ML forecast (expensive computation).
7. **Logging** — `SecurityLoggingMiddleware` writes 401/403 events (method, path, IP, user) to `logs/security.log`.
8. **Secrets** — All credentials loaded from `.env` via `django-environ`; never hardcoded.

### Production Hardening (`DEBUG=False`)

```python
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

---

## Data Model

```
CustomUser
  id (BigAuto PK)
  email (unique)
  nickname (unique, nullable)
  currency_preference  (USD | EUR | GBP | UAH)
  date_joined
  is_staff / is_active / is_superuser

PasswordResetOTP
  email
  code (6 chars)
  created_at
  expires_at
  is_used

Category
  id
  name
  user → CustomUser | NULL (system)
  type  (Income | Expense)
  icon_identifier
  is_active
  created_at
  UNIQUE(name, user, type)

Transaction
  id
  user → CustomUser  (CASCADE)
  category → Category  (PROTECT)
  amount  (Decimal 12,2 > 0)
  date
  description (optional)
  created_at
  INDEX(user, date)
  INDEX(user, category, date)
```

`Category.delete()` is overridden: if linked transactions exist, sets `is_active=False` (soft-delete); otherwise performs a hard delete.

---

## Configuration & Environment

All runtime configuration is loaded from `.env` using `django-environ`:

| Variable                 | Required | Description                      |
| ------------------------ | -------- | -------------------------------- |
| `SECRET_KEY`             | Yes      | Django secret key                |
| `DEBUG`                  | Yes      | `True` (dev) / `False` (prod)    |
| `ALLOWED_HOSTS`          | Yes      | Comma-separated hostnames        |
| `DATABASE_URL`           | Yes      | PostgreSQL connection string     |
| `CORS_ALLOWED_ORIGINS`   | No       | Comma-separated frontend origins |
| `GOOGLE_OAUTH_CLIENT_ID` | No       | For Google OAuth login           |
| `EMAIL_BACKEND`          | No       | Default: console (dev)           |
| `SECURE_SSL_REDIRECT`    | No       | Default `True` in production     |

---

## External Integrations

| Integration            | Purpose              | Library                                |
| ---------------------- | -------------------- | -------------------------------------- |
| PostgreSQL / Supabase  | Primary datastore    | psycopg 3.x, psycopg2, dj-database-url |
| Google OAuth 2.0       | Social login         | google-auth 2.47                       |
| Email (SMTP / console) | Password reset OTP   | Django's email backend                 |
| OpenAPI / Swagger      | Interactive API docs | drf-spectacular 0.29                   |

---

## Performance Considerations

- **Database indexes** on `Transaction(user, date)` and `Transaction(user, category, date)` ensure analytics aggregation queries stay fast even with large transaction volumes.
- **Service layer aggregation** uses Django ORM `Sum` and `TruncMonth` (pushed to the database) rather than pulling raw rows into Python.
- **ML computation** runs in-process on each request (no background workers). The `forecast` endpoint is rate-limited to 20/hr to prevent abuse of the CPU-bound scikit-learn training step.
- **Token rotation** keeps access tokens short-lived (15 min), reducing the window for token compromise without requiring frequent full re-authentication.
