# API Reference

Base URL: `http://localhost:8000`  
All authenticated endpoints require: `Authorization: Bearer <access_token>`  
All request/response bodies use `Content-Type: application/json`.

Interactive documentation is available at `/api/docs/` (Swagger UI) and `/api/redoc/` (ReDoc).

---

## Authentication — `/api/auth/`

### POST `/api/auth/register/`

Register a new user account.

**Auth required:** No  
**Rate limit:** Default (100/hr)

**Request body:**

| Field                 | Type   | Required | Description                          |
| --------------------- | ------ | -------- | ------------------------------------ |
| `email`               | string | Yes      | Unique email address                 |
| `password`            | string | Yes      | Must pass Django password validators |
| `password_confirm`    | string | Yes      | Must match `password`                |
| `nickname`            | string | No       | Unique display name (max 50 chars)   |
| `currency_preference` | string | No       | `USD` (default), `EUR`, `GBP`, `UAH` |

**Success response — 201 Created:**

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "john",
    "currency_preference": "USD",
    "date_joined": "2026-04-18T10:00:00Z"
  },
  "tokens": {
    "refresh": "<refresh_token>",
    "access": "<access_token>"
  }
}
```

**Error response — 400 Bad Request:**

```json
{
  "email": ["A user with this email already exists."],
  "password_confirm": ["Password fields didn't match."]
}
```

---

### POST `/api/auth/login/`

Authenticate with email and password.

**Auth required:** No  
**Rate limit:** 5/minute

**Request body:**

| Field        | Type   | Required         |
| ------------ | ------ | ---------------- | ---------------------------------------- |
| `email`      | string | Yes              |
| `password`   | string | Yes              |
| `totp_token` | string | When 2FA enabled | 6-digit TOTP code from authenticator app |

**Success response — 200 OK:**

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "john",
    "currency_preference": "USD",
    "date_joined": "2026-04-18T10:00:00Z"
  },
  "tokens": {
    "refresh": "<refresh_token>",
    "access": "<access_token>"
  }
}
```

**Error response — 400 Bad Request:**

```json
{
  "non_field_errors": ["Unable to log in with provided credentials."]
}
```

**Error response — 403 Forbidden (2FA required or invalid):**

```json
{
  "error": "2FA token is required.",
  "2fa_required": true
}
```

**Error response — 403 Forbidden (account locked by django-axes after 5 failures):**

```json
{
  "detail": "Request was throttled."
}
```

---

### POST `/api/auth/refresh/`

Obtain a new access token using a valid refresh token.

**Auth required:** No

**Request body:**

```json
{ "refresh": "<refresh_token>" }
```

**Success response — 200 OK:**

```json
{ "access": "<new_access_token>" }
```

**Error response — 401 Unauthorized:**

```json
{ "error": "Invalid refresh token." }
```

---

### POST `/api/auth/logout/`

Blacklist the refresh token, invalidating the session.

**Auth required:** Yes

**Request body:**

```json
{ "refresh": "<refresh_token>" }
```

**Success response — 200 OK:**

```json
{ "message": "Successfully logged out" }
```

---

### GET `/api/auth/profile/`

Get the current authenticated user's profile.

**Auth required:** Yes

**Success response — 200 OK:**

```json
{
  "id": 1,
  "email": "user@example.com",
  "nickname": "john",
  "currency_preference": "USD",
  "date_joined": "2026-04-18T10:00:00Z"
}
```

---

### POST `/api/auth/google/`

Authenticate or register via Google One Tap / Google Sign-In.

**Auth required:** No  
**Rate limit:** Default (100/hr)

**Request body:**

```json
{ "credential": "<google_id_token>" }
```

**Success response — 200 OK:**

```json
{
  "user": { "id": 1, "email": "user@gmail.com", ... },
  "tokens": { "refresh": "...", "access": "..." },
  "created": false
}
```

`"created": true` when the account was just registered.

**Error responses:**

| Code | Reason                                  |
| ---- | --------------------------------------- |
| 400  | Missing or empty credential             |
| 401  | Invalid / expired Google token          |
| 500  | `GOOGLE_OAUTH_CLIENT_ID` not configured |

---

### POST `/api/auth/password-reset/`

Send a 6-digit OTP code to the user's email (valid for 10 minutes).

**Auth required:** No  
**Rate limit:** Default (100/hr)

**Request body:**

```json
{ "email": "user@example.com" }
```

**Success response — 200 OK:**

```json
{
  "message": "Password reset code has been sent to your email.",
  "email": "user@example.com"
}
```

> Returns 200 even if the email does not exist (prevents user enumeration).

---

### POST `/api/auth/password-reset/confirm/`

Confirm OTP code and set a new password.

**Auth required:** No

**Request body:**

| Field                  | Type   | Required |
| ---------------------- | ------ | -------- | ----------- |
| `email`                | string | Yes      |
| `code`                 | string | Yes      | 6-digit OTP |
| `new_password`         | string | Yes      |
| `new_password_confirm` | string | Yes      |

**Success response — 200 OK:**

```json
{ "message": "Password has been reset successfully." }
```

**Error responses — 400 Bad Request:**

```json
{ "code": ["Invalid or expired OTP code."] }
```

---

## Categories — `/api/categories/`

### GET `/api/categories/`

List all active categories available to the current user: system-default categories (shared) plus the user's own categories.

**Auth required:** Yes

**Success response — 200 OK:**

```json
[
  {
    "id": 1,
    "name": "Food",
    "user": null,
    "type": "Expense",
    "icon_identifier": "food",
    "icon": "food",
    "is_system": true,
    "is_active": true,
    "created_at": "2026-01-01T00:00:00Z"
  },
  {
    "id": 15,
    "name": "Freelance",
    "user": 1,
    "type": "Income",
    "icon_identifier": "laptop",
    "icon": "laptop",
    "is_system": false,
    "is_active": true,
    "created_at": "2026-04-01T09:00:00Z"
  }
]
```

---

### POST `/api/categories/`

Create a new user-owned category.

**Auth required:** Yes

**Request body:**

| Field             | Type   | Required | Description                        |
| ----------------- | ------ | -------- | ---------------------------------- |
| `name`            | string | Yes      | Max 100 chars                      |
| `type`            | string | Yes      | `"Income"` or `"Expense"`          |
| `icon_identifier` | string | No       | Icon string (default: `"default"`) |

**Success response — 201 Created:** Returns the created category object.

**Error — 400:** Duplicate name+type combination for this user.

---

### GET `/api/categories/{id}/`

Retrieve a specific user-owned category.

**Auth required:** Yes  
**Note:** Only the owner can access their own categories. System categories cannot be accessed through this endpoint.

---

### PUT/PATCH `/api/categories/{id}/`

Update a user-owned category.

**Auth required:** Yes  
**Note:** Cannot update system categories.

---

### DELETE `/api/categories/{id}/`

Delete a user-owned category.

**Auth required:** Yes  
**Behavior:** If the category has linked transactions, it is soft-deleted (`is_active=False`) rather than removed from the database. System categories cannot be deleted (`403 Forbidden`).

---

## Transactions — `/api/transactions/`

### GET `/api/transactions/`

List transactions for the authenticated user, with optional filters.

**Auth required:** Yes

**Query parameters:**

| Param       | Type         | Description                                 |
| ----------- | ------------ | ------------------------------------------- |
| `date_from` | `YYYY-MM-DD` | Include transactions on or after this date  |
| `date_to`   | `YYYY-MM-DD` | Include transactions on or before this date |
| `category`  | integer      | Filter by category ID                       |
| `type`      | string       | `"Income"` or `"Expense"`                   |

**Success response — 200 OK:**

```json
[
  {
    "id": 42,
    "user": 1,
    "category": 3,
    "category_name": "Food",
    "category_type": "Expense",
    "amount": "150.50",
    "date": "2026-04-15",
    "description": "Weekly grocery shopping",
    "created_at": "2026-04-15T14:00:00Z"
  }
]
```

---

### POST `/api/transactions/`

Create a new transaction.

**Auth required:** Yes

**Request body:**

| Field         | Type         | Required | Constraints                                       |
| ------------- | ------------ | -------- | ------------------------------------------------- |
| `category`    | integer      | Yes      | Must be a category accessible to the user         |
| `amount`      | decimal      | Yes      | `> 0`, max `9999999999.99`                        |
| `date`        | `YYYY-MM-DD` | Yes      | Cannot be in the future; cannot be > 50 years ago |
| `description` | string       | No       | Optional free text                                |

**Success response — 201 Created:** Returns the created transaction object.

---

### GET `/api/transactions/{id}/`

Retrieve a single transaction.

**Auth required:** Yes  
**Note:** Returns 404 if the transaction belongs to a different user.

---

### PUT/PATCH `/api/transactions/{id}/`

Update all or some fields of a transaction.

**Auth required:** Yes

---

### DELETE `/api/transactions/{id}/`

Delete a transaction.

**Auth required:** Yes  
**Note:** Hard delete. Category remains unaffected (uses `PROTECT` on the FK).

---

## Analytics — `/api/analytics/`

### GET `/api/analytics/dashboard/`

Dashboard summary for the specified month/year.

**Auth required:** Yes

**Query parameters:**

| Param   | Type    | Default       | Description  |
| ------- | ------- | ------------- | ------------ |
| `year`  | integer | current year  | e.g., `2026` |
| `month` | integer | current month | `1`–`12`     |

**Success response — 200 OK:**

```json
{
  "total_income": "5000.00",
  "total_spent": "3200.00",
  "current_balance": "1800.00",
  "income_percent_change": 10.5,
  "spent_percent_change": -5.2,
  "balance_percent_change": 15.0,
  "year": 2026,
  "month": 4,
  "category_distribution": [
    { "name": "Food", "value": 800.0 },
    { "name": "Transport", "value": 400.0 }
  ]
}
```

Percent change fields compare the requested month to the previous month. `0.0` is returned when there is no prior month data.

---

### GET `/api/analytics/forecast/`

ML-based expense forecast using Linear Regression on the last 12 months of data.

**Auth required:** Yes  
**Rate limit:** 20/hour

**Success response — 200 OK (sufficient data):**

```json
{
  "status": "success",
  "forecast": {
    "predicted_amount": 3450.75,
    "confidence_score": 0.8712,
    "trend_direction": "increasing",
    "next_month": "May 2026"
  },
  "historical_trends": [
    { "month": "Apr 2025", "amount": 2800.0 },
    { "month": "May 2025", "amount": 2950.0 }
  ],
  "mathematical_summary": {
    "r_squared": 0.8712,
    "slope": 52.3,
    "intercept": 2600.0
  }
}
```

**Response when data is insufficient (< 3 months):**

```json
{
  "status": "insufficient_data",
  "message": "Потрібно мінімум 3 місяці історії"
}
```

`confidence_score` / `r_squared`: R² coefficient (0–1); higher is better.  
`trend_direction`: `"increasing"` or `"decreasing"`.

---

### GET `/api/analytics/balance/`

Monthly balance (Income − Expenses) for a given month.

**Auth required:** Yes

**Query parameters:** `year`, `month` (same defaults as `/dashboard/`).

**Success response — 200 OK:**

```json
{
  "balance": "1800.00",
  "year": 2026,
  "month": 4
}
```

---

### GET `/api/analytics/trend/`

Month-by-month income, expenses, and balance over a rolling window.

**Auth required:** Yes

**Query parameters:**

| Param         | Type    | Default | Range                        |
| ------------- | ------- | ------- | ---------------------------- |
| `months_back` | integer | 12      | 6–24 (clamped automatically) |

**Success response — 200 OK:**

```json
[
  {
    "month": "2025-05",
    "income": 5000.0,
    "expenses": 3200.0,
    "balance": 1800.0
  },
  {
    "month": "2025-06",
    "income": 4800.0,
    "expenses": 3500.0,
    "balance": 1300.0
  }
]
```

Only months that have at least one transaction are included.

---

### GET `/api/analytics/insights/`

Rule-based spending insights for a given month.

**Auth required:** Yes

**Query parameters:** `year`, `month` (same defaults as `/dashboard/`).

**Success response — 200 OK:**

```json
{
  "insights": [
    "Food is your biggest expense this month.",
    "You spent 12.3% more this month compared to last month. Consider reviewing your expenses.",
    "Your balance is positive this month. Great job!"
  ],
  "year": 2026,
  "month": 4
}
```

Insights are generated based on: biggest expense category, month-over-month change (> ±10%), balance status, dominant category (> 50% of spending), and income-to-expense ratio.

---

## 2FA / TOTP — `/api/auth/2fa/`

### POST `/api/auth/2fa/setup/`

Begin 2FA setup. Creates an unconfirmed TOTP device (overwrites any previous unconfirmed device).

**Auth required:** Yes

**Success response — 200 OK:**

```json
{
  "otp_uri": "otpauth://totp/FinSecure%20Monitor:user%40example.com?secret=ABC123&issuer=FinSecure%20Monitor",
  "qr_code": "data:image/png;base64,<base64_png>"
}
```

Display `qr_code` as an `<img src="...">`. The user scans it with Google Authenticator or Authy.

**Error — 400:** 2FA is already confirmed for this account.

---

### POST `/api/auth/2fa/confirm/`

Confirm 2FA by verifying the first TOTP token from the authenticator app.

**Auth required:** Yes

**Request body:**

```json
{ "token": "123456" }
```

**Success response — 200 OK:**

```json
{ "message": "2FA has been enabled successfully." }
```

**Error — 400:** Invalid token or no pending setup.

---

### POST `/api/auth/2fa/disable/`

Disable 2FA for the current account. Requires a valid TOTP token.

**Auth required:** Yes

**Request body:**

```json
{ "token": "123456" }
```

**Success response — 200 OK:**

```json
{ "message": "2FA has been disabled." }
```

**Error — 400:** Invalid token or 2FA not enabled.

---

### GET `/api/auth/2fa/status/`

Check 2FA status for the current user.

**Auth required:** Yes

**Success response — 200 OK:**

```json
{ "is_2fa_enabled": true }
```

---

## Advanced Analytics — `/api/analytics/`

### GET `/api/analytics/anomalies/`

Run Isolation Forest anomaly detection over all user transactions. Automatically updates `is_suspicious` and `anomaly_score` on each transaction.

**Auth required:** Yes

**Success response — 200 OK:**

```json
{
  "status": "success",
  "total_analysed": 150,
  "anomalies_found": 3,
  "flagged_transactions": [
    {
      "transaction_id": 87,
      "amount": 3400.0,
      "date": "2026-04-02",
      "category": "Shopping",
      "anomaly_score": -0.1823
    }
  ]
}
```

**When insufficient data (< 20 transactions):**

```json
{
  "status": "insufficient_data",
  "message": "Need at least 20 transactions for anomaly detection.",
  "flagged": []
}
```

`anomaly_score`: Decision function output from Isolation Forest. Values below 0 indicate anomalies; more negative = more anomalous.

---

### POST `/api/analytics/categorize/`

Predict the most likely category for a transaction description using TF-IDF + Random Forest.

**Auth required:** Yes

**Request body:**

```json
{ "description": "Uber trip to airport" }
```

**Success response — 200 OK:**

```json
{
  "predicted_category_id": 4,
  "predicted_category_name": "Transport",
  "predicted_category_type": "Expense",
  "confidence": 0.82
}
```

**When insufficient training data (< 30 labelled transactions):**

```json
{
  "status": "insufficient_data",
  "message": "Not enough labelled transactions to train the model."
}
```

`confidence`: RandomForest prediction probability (0–1). Auto-categorization on transaction creation applies automatically when confidence ≥ 0.6.

---

### GET `/api/analytics/budget-alert/`

Predict when the user will exhaust their monthly budget based on current spending velocity.

**Auth required:** Yes  
**Setup:** Set `monthly_budget` on the user profile to enable budget-specific predictions.

**Success response — 200 OK:**

```json
{
  "total_spent_this_month": 6200.0,
  "daily_velocity": 283.5,
  "projected_month_end": 8788.5,
  "days_elapsed": 18,
  "days_remaining": 12,
  "budget": 8000.0,
  "budget_percent_used": 77.5,
  "budget_hit_date": "2026-04-26",
  "risk_level": "high"
}
```

`risk_level` values: `"low"` (< 60 %), `"medium"` (60–79 %), `"high"` (80–99 %), `"critical"` (≥ 100 %).  
`budget_hit_date`: ISO date when budget will be exhausted at current velocity. `null` if budget not set or will not be hit this month.

---

### GET `/api/analytics/health-score/`

Calculate a composite financial health score (0–100) based on the last 6 months of data.

**Auth required:** Yes

**Success response — 200 OK:**

```json
{
  "status": "success",
  "health_score": 72,
  "grade": "B",
  "breakdown": {
    "savings_rate": { "score": 22, "max": 30, "savings_rate_pct": 22.0 },
    "expense_volatility": { "score": 19, "max": 25, "cv": 0.1823 },
    "budget_adherence": { "score": 20, "max": 25, "budget_set": true },
    "consistency": { "score": 17, "max": 20, "active_months": 5 }
  },
  "period_months": 6
}
```

**Score breakdown:**

| Sub-score          | Max pts | Formula                                                        |
| ------------------ | ------- | -------------------------------------------------------------- |
| Savings Rate       | 30      | `(income - expenses) / income × 100` pts, capped at 30         |
| Expense Volatility | 25      | Based on monthly CV (coefficient of variation); lower = better |
| Budget Adherence   | 25      | Fraction of months ≤ budget × 25                               |
| Consistency        | 20      | Active months / 6 × 20                                         |

**Grades:** A (≥ 80), B (60–79), C (40–59), D (20–39), F (< 20).

---

## Error Responses

| HTTP Code | Meaning                                                                 |
| --------- | ----------------------------------------------------------------------- |
| 400       | Validation error — check the response body for field-level details      |
| 401       | Missing or invalid JWT access token                                     |
| 403       | Authenticated but not authorised, 2FA failed, or account locked by axes |
| 404       | Resource not found or belongs to a different user                       |
| 429       | Rate limit exceeded                                                     |
| 500       | Internal server error                                                   |

Standard DRF error body:

```json
{
  "field_name": ["Error message."],
  "non_field_errors": ["Non-field error message."]
}
```
