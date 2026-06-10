# Secure Financial Expense Monitoring System with Machine Learning

A production-ready Django REST Framework (DRF) backend for a financial expense monitoring system with machine learning-based expense forecasting.

## Features

- 🔐 **Secure Authentication**: JWT-based authentication with SimpleJWT
- 📊 **Financial Tracking**: Income and expense tracking with categories
- 🤖 **ML Forecasting**: Linear Regression-based expense prediction
- 🔒 **Security Hardened**: Input validation, CORS, rate limiting, security logging
- 📈 **Analytics Dashboard**: Balance calculations, expense aggregations, pie charts
- 🏗️ **Service Layer Pattern**: Clean architecture with business logic in services
- 🗄️ **PostgreSQL Ready**: Configured for Supabase/PostgreSQL

## Tech Stack

- **Framework**: Django 5.x, Django REST Framework (DRF)
- **Database**: PostgreSQL (ready for Supabase)
- **Authentication**: JWT (SimpleJWT)
- **ML/Data Science**: Scikit-learn, Pandas, NumPy
- **Security**: django-cors-headers, django-environ, rate limiting

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
│   ├── models.py               # CustomUser model
│   ├── serializers.py          # User registration/login serializers
│   ├── views.py                # Auth endpoints (register, login, logout)
│   └── urls.py                 # Auth URL routing
├── transactions/               # Transactions app
│   ├── models.py               # Category and Transaction models
│   ├── serializers.py          # Transaction serializers with validation
│   ├── views.py                # CRUD endpoints for transactions
│   ├── services/               # Service layer (business logic)
│   │   ├── finance_service.py  # Financial calculations
│   │   └── ml_service.py       # ML forecasting (Linear Regression)
│   ├── urls_categories.py      # Category URL routing
│   ├── urls_transactions.py    # Transaction URL routing
│   └── urls_analytics.py       # Analytics URL routing
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
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
# Option 1: Supabase (recommended for production)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# Option 2: Local PostgreSQL
# DATABASE_URL=postgresql://username:password@localhost:5432/financial_monitor

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://localhost:3000,https://127.0.0.1:3000
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

### 8. Run Development Server

```bash
python manage.py runserver
```

python manage.py runserver_plus --cert-file localhost+2.pem --key-file localhost+2-key.pem

The API will be available at `https://localhost:8000/`

## API Endpoints

### Authentication (`/api/auth/`)

- `POST /api/auth/register/` - Register a new user
- `POST /api/auth/login/` - Login and get JWT tokens
- `POST /api/auth/refresh/` - Refresh access token
- `POST /api/auth/logout/` - Logout (blacklist refresh token)
- `GET /api/auth/profile/` - Get current user profile

### Categories (`/api/categories/`)

- `GET /api/categories/` - List all categories (system + user-created)
- `POST /api/categories/` - Create a new category

### Transactions (`/api/transactions/`)

- `GET /api/transactions/` - List transactions (with filtering)
  - Query params: `date_from`, `date_to`, `category`, `type`
- `POST /api/transactions/` - Create a new transaction
- `GET /api/transactions/{id}/` - Get transaction details
- `PUT /api/transactions/{id}/` - Update transaction
- `PATCH /api/transactions/{id}/` - Partial update transaction
- `DELETE /api/transactions/{id}/` - Delete transaction

### Analytics (`/api/analytics/`)

- `GET /api/analytics/dashboard/` - Get dashboard data (totals, pie chart)
  - Query params: `year`, `month`
- `GET /api/analytics/forecast/` - Get ML-based expense forecast
  - Query params: `months_back` (default: 12, range: 6-24)
- `GET /api/analytics/balance/` - Get monthly balance
  - Query params: `year`, `month`

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

The ML forecasting uses **Linear Regression** from Scikit-learn:

1. **Data Preparation**: Groups user expenses by month for the last 6-12 months
2. **Features (X)**: Month index (0, 1, 2, ...)
3. **Target (y)**: Total expenses per month
4. **Model**: Linear Regression (y = a*X + b)
5. **Prediction**: Next month's expense
6. **Confidence Score**: R-squared (coefficient of determination, 0-1)

The service requires at least 3 months of historical data for reliable predictions.

## Security Features

- ✅ **Input Validation**: Strict serializers with field-level validation
- ✅ **CORS Configuration**: Allowed origins for React frontend
- ✅ **Rate Limiting**: 
  - Login: 5 requests/minute
  - ML Forecast: 20 requests/hour
  - Default: 100 requests/hour
- ✅ **Security Logging**: Middleware logs 401/403 errors
- ✅ **Environment Variables**: All secrets loaded from `.env`
- ✅ **JWT Authentication**: Secure token-based authentication
- ✅ **Password Validation**: Django's built-in password validators

## Development

### Running Tests

```bash
python manage.py test
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Accessing Django Admin

1. Create superuser: `python manage.py createsuperuser`
2. Visit: `https://localhost:8000/admin/`
3. Login with superuser credentials

## Production Deployment

### Important Settings for Production

1. **Update `.env` file:**
   ```env
   DEBUG=False
   SECRET_KEY=<generate-strong-secret-key>
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   ```

2. **Database**: Use Supabase or a managed PostgreSQL service

3. **Static Files**: Collect static files
   ```bash
   python manage.py collectstatic
   ```

4. **SSL/HTTPS**: Ensure your deployment uses HTTPS

5. **Environment Variables**: Never commit `.env` file to version control

## License

This project is part of a diploma work: "Secure Financial Expense Monitoring System with Machine Learning".

## Author

Diploma Project - Financial Monitor Backend

docker compose up --build -d
Bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createcachetable
docker compose exec backend python manage.py createsuperuser


docker compose exec backend env DJANGO_SETTINGS_MODULE=financial_monitor.settings pytest tests/ -v --reuse-db