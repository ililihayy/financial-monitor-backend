# Secure Financial Expense Monitoring System with Machine Learning

A production-ready Django REST Framework (DRF) backend for a financial expense monitoring system with advanced machine learning, AI-powered financial advisory, and field-level encryption.

## Features

- **Multi-Factor Authentication**: JWT-based auth with SMS 2FA (Twilio) and TOTP/OTP support
- **Field-Level Encryption**: Fernet-based encryption for sensitive data (email, amounts, descriptions, categories)
- **Financial Tracking**: Income and expense tracking with encrypted categories and transactions
- **Advanced ML Services**:
  - Expense forecasting with Linear Regression
  - Auto-categorization using TF-IDF + Random Forest
  - Budget alerts and financial health scoring
- **AI Financial Advisor**: RAG pipeline with Google Gemini 2.5 Flash API for intelligent financial insights
- **Conversation Persistence**: Multi-turn conversations with the AI advisor with history management
- **Analytics Dashboard**: Balance calculations, expense aggregations, pie charts, trends, and insights
- **Security Hardened**: Input validation, CORS, rate limiting, security logging, PII detection, audit trails
- **Service Layer Pattern**: Clean architecture with business logic separated into services
- **PostgreSQL Ready**: Configured for Supabase/PostgreSQL
- **Daily Motivational Quotes**: Financial wisdom quotes for user motivation

## Tech Stack

- **Framework**: Django 5.x, Django REST Framework (DRF)
- **Database**: PostgreSQL (ready for Supabase)
- **Authentication**: JWT (SimpleJWT), SimpleJWT for token management
- **2FA/MFA**: Twilio (SMS), PyOTP (TOTP/OTP)
- **Encryption**: cryptography (Fernet) for field-level encryption
- **AI/LLM**: Google Generative AI (Gemini 2.5 Flash)
- **ML/Data Science**: Scikit-learn, Pandas, NumPy
- **Security**: django-cors-headers, django-environ, django-axes (brute-force protection), rate limiting, audit logging
- **API Security**: Rate limiting, throttling, permission classes

## Project Structure

```
financial-monitor-backend/
├── financial_monitor/          # Main project directory
│   ├── settings.py             # Django settings with security config
│   ├── urls.py                 # Main URL routing
│   ├── middleware.py           # Security logging middleware
│   ├── wsgi.py                 # WSGI configuration
│   └── asgi.py                 # ASGI configuration
├── accounts/                   # Authentication app
│   ├── models.py               # CustomUser model (encrypted email)
│   ├── serializers.py          # User registration/login serializers
│   ├── views.py                # Auth endpoints (register, login, 2FA, password reset, OAuth)
│   ├── urls.py                 # Auth URL routing
│   ├── signals.py              # Signal handlers
│   └── services/               # Security services
│       ├── encryption_service.py    # Fernet-based field encryption
│       ├── audit_service.py         # Security audit logging
│       ├── sms_service.py           # Twilio SMS 2FA
│       ├── totp_service.py          # TOTP/OTP generation
│       └── pii_detection_service.py # PII detection
├── transactions/               # Transactions app
│   ├── models.py               # Category, Transaction, Conversation models (with encryption)
│   ├── serializers.py          # Transaction and conversation serializers
│   ├── views.py                # API endpoints for categories, transactions, analytics, AI advisor
│   ├── urls_categories.py      # Category URL routing
│   ├── urls_transactions.py    # Transaction URL routing
│   ├── urls_analytics.py       # Analytics URL routing
│   └── services/               # Business logic services
│       ├── finance_service.py       # Financial calculations (balance, aggregations, summaries)
│       ├── ml_service.py            # ML models (forecasting, anomaly detection, auto-categorization)
│       ├── advisor_service.py       # AI advisor RAG pipeline orchestrator
│       ├── advisor_prompts.py       # RAG prompt building utilities
│       ├── advisor_constants.py     # Advisor configuration constants
│       ├── anonymization_service.py # Transaction anonymization for RAG
│       └── quotes_service.py        # Daily financial wisdom quotes
├── tests/                      # Test suite
│   ├── accounts/               # Account service tests
│   └── transactions/           # Transaction and ML service tests
├── docs/                       # Documentation
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
└── README.md                   # This file
```

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- PostgreSQL (or Supabase account)
- Virtual environment (recommended)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd financial-monitor-backend
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the project root directory:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (PostgreSQL/Supabase)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://localhost:3000,https://127.0.0.1:3000

# Encryption Key (for Fernet field-level encryption)
ENCRYPTION_KEY=your-generated-fernet-key-here

# Twilio SMS 2FA Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Google Generative AI (Gemini API)
GEMINI_API_KEY=your-google-gemini-api-key

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password
```

**To generate an encryption key:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 5. Supabase Setup (Recommended)

1. Create a Supabase account at [supabase.com](https://supabase.com)
2. Create a new project
3. Go to **Settings** → **Database**
4. Copy the **Connection String** (URI format)
5. Replace `[YOUR-PASSWORD]` with your database password
6. Update `DATABASE_URL` in `.env`

**Example Supabase DATABASE_URL:**

```
DATABASE_URL=postgresql://postgres.xxxxxxxxxxxxx:yourpassword@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

### 6. Run Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 8. Create Cache Table (for rate limiting)

```bash
python manage.py createcachetable
```

### 9. Run Development Server

```bash
# Standard development server
python manage.py runserver

# With HTTPS (if certificates are available)
python manage.py runserver_plus --cert-file localhost+2.pem --key-file localhost+2-key.pem
```

The API will be available at `http://localhost:8000/`

## API Endpoints

### Authentication (`/api/auth/`)

- `POST /api/auth/register/` - Register a new user
- `POST /api/auth/login/` - Login and get JWT tokens
- `POST /api/auth/refresh/` - Refresh access token
- `POST /api/auth/logout/` - Logout (blacklist refresh token)
- `GET /api/auth/profile/` - Get current user profile
- `POST /api/auth/password-reset/` - Request password reset
- `POST /api/auth/sms-2fa-setup/` - Setup SMS 2FA
- `POST /api/auth/sms-2fa-verify/` - Verify SMS 2FA code
- `POST /api/auth/totp-setup/` - Setup TOTP (authenticator app)
- `POST /api/auth/totp-verify/` - Verify TOTP code

### Categories (`/api/categories/`)

- `GET /api/categories/` - List all categories (system + user-created)
- `POST /api/categories/` - Create a new category
- `GET /api/categories/{id}/` - Get category details
- `PUT /api/categories/{id}/` - Update category
- `DELETE /api/categories/{id}/` - Delete category (soft delete)

### Transactions (`/api/transactions/`)

- `GET /api/transactions/` - List transactions (with filtering)
  - Query params: `date_from`, `date_to`, `category`, `type`
- `POST /api/transactions/` - Create a new transaction
- `GET /api/transactions/{id}/` - Get transaction details
- `PUT /api/transactions/{id}/` - Update transaction
- `PATCH /api/transactions/{id}/` - Partial update transaction
- `DELETE /api/transactions/{id}/` - Delete transaction

### Analytics & Dashboard (`/api/analytics/`)

- `GET /api/analytics/dashboard/` - Dashboard data (income, expenses, distribution)
  - Query params: `year`, `month`
- `GET /api/analytics/forecast/` - ML-based expense forecast
  - Query params: `months_back` (default: 12)
- `GET /api/analytics/balance/` - Monthly balance trend
  - Query params: `months_back` (default: 12)
- `GET /api/analytics/trends/` - Expense trends over time
- `GET /api/analytics/insights/` - AI-generated spending insights

### Machine Learning Analytics (`/api/analytics/`)

- `POST /api/analytics/auto-categorize/` - Auto-categorize transactions by description
- `POST /api/analytics/budget-alerts/` - Generate budget alerts
- `GET /api/analytics/health-score/` - Financial health scoring

### AI Financial Advisor (`/api/advisor/`)

- `POST /api/advisor/ask/` - Ask the AI advisor a financial question
  - Daily limit: 7 queries per user
  - Query params: `query`, `conversation_id` (optional), `lookback_days` (default: 60)
- `GET /api/advisor/conversations/` - List advisor conversations
- `GET /api/advisor/conversations/{id}/` - Get conversation details with message history
- `DELETE /api/advisor/conversations/{id}/` - Delete a conversation

### Utility (`/api/quotes/`)

- `GET /api/quotes/daily/` - Get daily motivational financial quote
- `GET /api/quotes/random/` - Get random financial quote

## API Usage Examples

### 1. Register a User

```bash
curl -X POST https://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "password_confirm": "securepassword123",
    "currency_preference": "USD"
  }'
```

### 2. Login

```bash
curl -X POST https://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

Response:

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "currency_preference": "USD",
    "date_joined": "2024-01-15T10:30:00Z"
  },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

### 3. Create a Transaction (Authenticated)

```bash
curl -X POST https://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "category": 1,
    "amount": "150.50",
    "date": "2024-03-15",
    "description": "Grocery shopping"
  }'
```

### 4. Get Dashboard Data

```bash
curl -X GET "https://localhost:8000/api/analytics/dashboard/?year=2024&month=3" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Get ML Forecast

```bash
curl -X GET "https://localhost:8000/api/analytics/forecast/?months_back=12" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:

```json
{
  "predicted_amount": "1250.50",
  "confidence_score": 0.85,
  "months_used": 8,
  "status": "success",
  "message": "Prediction based on 8 months of data"
}
```

## Machine Learning Implementation

The system includes multiple ML models for financial intelligence:

### 1. Expense Forecasting (Linear Regression)

- **Purpose**: Predict next month's expenses
- **Algorithm**: Linear Regression (y = a\*X + b)
- **Data**: Monthly expense aggregates for last 6-12 months
- **Output**: Predicted amount + confidence score (R²)
- **Requirements**: At least 3 months of historical data

### 2. Auto-Categorization (TF-IDF + Random Forest)

- **Purpose**: Automatically suggest category for transactions
- **Algorithm**: TF-IDF vectorizer + Random Forest classifier
- **Input**: Transaction description
- **Output**: Suggested category with confidence

### 3. Budget Alerts

- **Purpose**: Alert users when spending approaches budget
- **Logic**: Compares monthly spending against configured budgets
- **Output**: Alert with overspend percentage and recommendations

### 4. Financial Health Score

- **Purpose**: Calculate user's financial health (0-100)
- **Metrics**: Income/expense ratio, savings rate, spending patterns
- **Output**: Overall score + detailed breakdown

### 5. AI-Powered Financial Advisor (RAG Pipeline)

- **Purpose**: Provide intelligent financial advice based on user data
- **Pipeline**:
  1. Intent classification (budget, spending patterns, forecasts, recommendations)
  2. Relevant transaction retrieval with anonymization
  3. ML context injection (forecasts, anomalies, trends)
  4. Dynamic prompt building based on intent
  5. Gemini 2.5 Flash API call with RAG context
- **Safety**: Daily limit of 7 queries per user
- **Privacy**: Transactions anonymized before sending to LLM

## Security Features

- **Field-Level Encryption**: Fernet-based encryption for:
  - User email in accounts
  - Transaction amounts, descriptions
  - Category names
- **Multi-Factor Authentication**:
  - SMS-based 2FA via Twilio
  - TOTP/OTP support for authenticator apps
- **Input Validation**: Strict serializers with field-level validation
- **CORS Configuration**: Restricted origins for React frontend
- **Rate Limiting & Throttling**:
  - Login: 5 requests/minute (with django-axes brute-force protection)
  - AI Advisor: 7 queries/day per user
  - Forecast: 20 requests/hour
  - Default: 100 requests/hour
- **Security Logging**: Audit trails for login attempts, 2FA events, sensitive operations
- **Environment Variables**: All secrets loaded from `.env`, never hardcoded
- **JWT Authentication**: SimpleJWT with refresh/access tokens (15min access, 7-day refresh)
- **Password Security**: Django's password validators, enforced complexity
- **PII Detection**: Detects and flags personally identifiable information
- **Permission Classes**: IsAuthenticated enforced on protected endpoints
- **HTTPS Ready**: SSL/TLS support for production

## Development

### Running Tests

```bash
# Using pytest
pytest tests/ -v --reuse-db

# Using Docker Compose
docker compose exec backend pytest tests/ -v --reuse-db

# Using Django test runner
python manage.py test
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Accessing Django Admin

1. Create superuser: `python manage.py createsuperuser`
2. Visit: `http://localhost:8000/admin/`
3. Login with superuser credentials

### Populate Test Data

```bash
# Populate realistic transaction data for testing
python manage.py populate_lilia_data
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and start containers
docker compose up --build -d

# Run migrations
docker compose exec backend python manage.py migrate

# Create superuser
docker compose exec backend python manage.py createsuperuser

# Run tests
docker compose exec backend pytest tests/ -v --reuse-db
```

## Production Deployment

### Important Settings for Production

1. **Update `.env` file:**

   ```env
   DEBUG=False
   SECRET_KEY=<generate-strong-secret-key>
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

   # Database: Use managed PostgreSQL/Supabase
   DATABASE_URL=<production-database-url>

   # Encryption key: Generate fresh key
   ENCRYPTION_KEY=<fresh-fernet-key>

   # API keys: Use production credentials
   GEMINI_API_KEY=<production-key>
   TWILIO_ACCOUNT_SID=<production-sid>
   TWILIO_AUTH_TOKEN=<production-token>
   ```

2. **Database**: Use Supabase or managed PostgreSQL service

3. **Static Files**: Collect and serve via CDN

   ```bash
   python manage.py collectstatic --noinput
   ```

4. **SSL/HTTPS**: Enforce HTTPS in production

5. **Environment Variables**: Never commit `.env` file to version control

6. **Security Checklist**:
   - [ ] Enable SECURE_SSL_REDIRECT
   - [ ] Set SECURE_HSTS_SECONDS
   - [ ] Configure CSRF_TRUSTED_ORIGINS
   - [ ] Use managed secrets (e.g., AWS Secrets Manager)
   - [ ] Enable database backups
   - [ ] Set up monitoring and alerting

## API Response Examples

### Login Response with 2FA

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "currency_preference": "USD",
    "is_2fa_enabled": true,
    "date_joined": "2024-01-15T10:30:00Z"
  },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  },
  "requires_2fa": true
}
```

### AI Advisor Response

```json
{
  "advice": "Based on your spending patterns over the last 60 days...",
  "conversation_id": 123,
  "intent": "spending_analysis",
  "confidence": 0.95,
  "timestamp": "2024-06-11T10:30:00Z"
}
```
