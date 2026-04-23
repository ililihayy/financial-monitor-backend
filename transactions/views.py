"""
Views for transactions app.

Includes views for categories, transactions, and analytics.
All business logic is delegated to the service layer.
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from django.db.models import Q
from datetime import datetime
from .models import Category, Transaction, AdvisorConversation, AdvisorMessage
from .serializers import (
    CategorySerializer, TransactionSerializer, TransactionListSerializer,
    AdvisorConversationSerializer, AdvisorConversationDetailSerializer,
    AdvisorMessageSerializer,
)
from .services import FinanceService, MLForecastService
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from .models import Transaction, Category
from .services import (
    FinanceService, MLForecastService,
    AnomalyDetectionService, AutoCategorizationService,
    BudgetAlertService, FinancialHealthService, MLRetrainingService,
)


# ========== Category Views ==========

class CategoryListCreateView(generics.ListCreateAPIView):
    """
    List all categories (system-default + user-created) or create a new category.

    GET /api/categories/ - List all categories
    POST /api/categories/ - Create a new category
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def get_queryset(self):
        """Return active system categories and user's active categories."""
        user = self.request.user
        return Category.objects.filter(
            # User's active categories or system active categories
            Q(user=user, is_active=True) | Q(user=None, is_active=True)
        ).distinct()

    def perform_create(self, serializer):
        """Set the user when creating a category."""
        serializer.save(user=self.request.user)


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a category.

    GET /api/categories/{id}/ - Get category details
    PUT /api/categories/{id}/ - Update category
    PATCH /api/categories/{id}/ - Partial update category
    DELETE /api/categories/{id}/ - Delete category
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def get_queryset(self):
        """Only return user's own categories (cannot delete system categories)."""
        user = self.request.user
        # Only allow access to user's own categories, not system categories
        return Category.objects.filter(user=user)

    def perform_destroy(self, instance):
        """Prevent deletion of system categories."""
        if instance.user is None:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cannot delete system categories.")
        instance.delete()


# ========== Transaction Views ==========

class TransactionListCreateView(generics.ListCreateAPIView):
    """
    List transactions with filtering or create a new transaction.

    GET /api/transactions/?date_from=2024-01-01&date_to=2024-12-31&category=1
    POST /api/transactions/ - Create a new transaction
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        """Filter transactions by user and optional filters."""
        user = self.request.user
        queryset = Transaction.objects.filter(user=user)

        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)

        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Filter by type (Income/Expense)
        transaction_type = self.request.query_params.get('type', None)
        if transaction_type:
            queryset = queryset.filter(category__type=transaction_type)

        return queryset.order_by('-date', '-created_at')

    def perform_create(self, serializer):
        """Set the user when creating a transaction, then run ML post-processing."""
        from django.conf import settings as django_settings
        from accounts.services import EncryptionService, PIIDetectionService, AuditService

        transaction = serializer.save(user=self.request.user)
        ip = self.request.META.get('REMOTE_ADDR', 'unknown')

        # 1. Encrypt description if non-empty
        if transaction.description:
            transaction.description = EncryptionService.encrypt(
                transaction.description)
            transaction.is_encrypted = True
            transaction.save(update_fields=['description', 'is_encrypted'])

        # 2. Large transaction audit
        threshold = getattr(
            django_settings, 'LARGE_TRANSACTION_THRESHOLD', 10000)
        if float(transaction.amount) >= threshold:
            AuditService.log_large_transaction(
                self.request.user, ip, transaction.amount, threshold,
            )

        # 3. PII warning audit (if serializer detected PII)
        pii = getattr(serializer, '_pii_warnings', None)
        if pii:
            AuditService.log_pii_warning(
                self.request.user, ip, [p['type'] for p in pii],
            )

        # 4. Background ML: anomaly scoring + auto-categorization
        MLRetrainingService.auto_categorize_async(
            self.request.user, transaction)


class TransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a transaction.

    GET /api/transactions/{id}/ - Get transaction details
    PUT /api/transactions/{id}/ - Update transaction
    PATCH /api/transactions/{id}/ - Partial update transaction
    DELETE /api/transactions/{id}/ - Delete transaction
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        """Only return transactions belonging to the current user."""
        return Transaction.objects.filter(user=self.request.user)


# ========== Analytics Views ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    """
    Get dashboard data: summary with totals, balance, and category distribution.

    GET /api/analytics/dashboard/?year=2024&month=3

    Returns: {
        "total_income": 5000.00,
        "total_spent": 3500.00,
        "current_balance": 1500.00,
        "percent_change": 5.5,
        "category_distribution": [
            {"category": "Food", "amount": 450.00},
            {"category": "Transport", "amount": 300.00}
        ],
        "year": 2024,
        "month": 3
    }
    """
    # Get optional filters
    year = request.query_params.get('year', None)
    month = request.query_params.get('month', None)

    # Use current date if not provided
    from datetime import date
    today = date.today()
    target_year = int(year) if year else today.year
    target_month = int(month) if month else today.month

    # Get dashboard summary (includes totals and percent change)
    summary = FinanceService.get_dashboard_summary(
        request.user, target_month, target_year)

    # Get category distribution for Donut Chart
    category_distribution = FinanceService.get_category_distribution(
        request.user, target_month, target_year
    )

    # Add category distribution to response
    summary['category_distribution'] = category_distribution

    return Response(summary, status=status.HTTP_200_OK)


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @throttle_classes([ScopedRateThrottle])
# def forecast_view(request):
#     """
#     Get ML-based expense forecast for the next month.

#     GET /api/analytics/forecast/?months_back=12

#     Returns: {
#         "predicted_amount": 1250.50,
#         "confidence_score": 0.85,
#         "months_used": 8,
#         "status": "success",
#         "message": "Prediction based on 8 months of data"
#     }
#     """
#     # Get optional parameter
#     months_back = request.query_params.get('months_back', 12)
#     months_back = int(months_back) if months_back else 12

#     # Ensure valid range
#     months_back = max(6, min(months_back, 24))  # Between 6 and 24 months

#     # Get prediction
#     prediction = MLForecastService.predict_next_month_expense(
#         request.user, months_back
#     )

#     return Response(prediction, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forecast_view(request):
    """
    Головний ендпоінт аналітики: Тренди + Монте-Карло.
    """
    try:
        # 1. Розрахунок поточного балансу для симуляції
        income = Transaction.objects.filter(
            user=request.user, category__type='Income'
        ).aggregate(total=Sum('amount'))['total'] or 0

        expenses = Transaction.objects.filter(
            user=request.user, category__type='Expense'
        ).aggregate(total=Sum('amount'))['total'] or 0

        current_balance = float(income - expenses)

        # 2. Виклик сервісу комбінованої аналітики
        analysis = MLForecastService.get_comprehensive_analysis(
            request.user, current_balance)

        return Response(analysis, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# transactions/views.py


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    """
    Отримує дані для дашборду: підсумки, баланс та розподіл за категоріями.
    """
    try:
        from datetime import date

        # 1. Отримуємо параметри з запиту або ставимо поточні за замовчуванням
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        today = date.today()
        target_year = int(year) if year else today.year
        target_month = int(month) if month else today.month

        # 2. ВИПРАВЛЕННЯ: Передаємо всі 3 обов'язкові аргументи
        summary = FinanceService.get_dashboard_summary(
            request.user,
            target_month,
            target_year
        )

        # 3. Додаємо розподіл категорій (якщо сервіс його не включив)
        category_distribution = FinanceService.get_category_distribution(
            request.user, target_month, target_year
        )
        summary['category_distribution'] = category_distribution

        return Response(summary, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Dashboard Error: {str(e)}")
        return Response(
            {"status": "error", "message": "Не вдалося отримати дані дашборду"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_view(request):
    """
    Get monthly balance (Income - Expenses).

    GET /api/analytics/balance/?year=2024&month=3

    Returns: {
        "balance": 1500.00,
        "year": 2024,
        "month": 3
    }
    """
    # Get optional filters
    year = request.query_params.get('year', None)
    month = request.query_params.get('month', None)

    # Use current date if not provided
    from datetime import date
    today = date.today()
    target_year = int(year) if year else today.year
    target_month = int(month) if month else today.month

    # Calculate balance
    balance = FinanceService.calculate_monthly_balance(
        request.user, target_year, target_month
    )

    return Response({
        'balance': balance,
        'year': target_year,
        'month': target_month,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trend_view(request):
    """
    Get monthly trend data for analytics visualization.

    GET /api/analytics/trend/?months_back=12

    Returns: [
        {
            "month": "2024-01",
            "income": 5000.00,
            "expenses": 3500.00,
            "balance": 1500.00
        },
        ...
    ]
    """
    from transactions.models import Transaction, Category
    from django.db.models import Sum, Q
    from django.db.models.functions import TruncMonth
    from django.db.models import DecimalField
    from decimal import Decimal
    from datetime import date, timedelta

    # Get optional parameter
    months_back = request.query_params.get('months_back', 12)
    months_back = int(months_back) if months_back else 12
    months_back = max(6, min(months_back, 24))  # Between 6 and 24 months

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=months_back * 31)

    # Get monthly income
    monthly_income = Transaction.objects.filter(
        user=request.user,
        category__type='Income',
        date__gte=start_date,
        date__lte=end_date
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total=Sum('amount', output_field=DecimalField())
    ).order_by('month')

    # Get monthly expenses
    monthly_expenses = Transaction.objects.filter(
        user=request.user,
        category__type='Expense',
        date__gte=start_date,
        date__lte=end_date
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total=Sum('amount', output_field=DecimalField())
    ).order_by('month')

    # Create dictionaries for quick lookup
    income_dict = {item['month']: float(
        item['total'] or Decimal('0.00')) for item in monthly_income}
    expenses_dict = {item['month']: float(
        item['total'] or Decimal('0.00')) for item in monthly_expenses}

    # Get all unique months
    all_months = sorted(
        set(list(income_dict.keys()) + list(expenses_dict.keys())))

    # Build response
    result = []
    for month in all_months:
        income = income_dict.get(month, 0.0)
        expenses = expenses_dict.get(month, 0.0)
        result.append({
            'month': month.strftime('%Y-%m'),
            'income': income,
            'expenses': expenses,
            'balance': income - expenses
        })

    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_insights_view(request):
    """
    Get AI-generated insights and tips based on transaction analysis.

    GET /api/analytics/insights/?year=2024&month=3

    Returns: {
        "insights": [
            "Rent is your biggest expense this month.",
            "You spent 20% more on Food compared to last month.",
            "Your balance is positive this month. Great job!"
        ],
        "year": 2024,
        "month": 3
    }
    """
    from datetime import date
    from decimal import Decimal

    # Get optional filters
    year = request.query_params.get('year', None)
    month = request.query_params.get('month', None)

    # Use current date if not provided
    today = date.today()
    target_year = int(year) if year else today.year
    target_month = int(month) if month else today.month

    insights = []

    # Get current month summary
    current_summary = FinanceService.get_dashboard_summary(
        request.user, target_month, target_year)
    current_spent = current_summary['total_spent']
    current_income = current_summary['total_income']
    current_balance = current_summary['current_balance']

    # Get category distribution
    category_distribution = FinanceService.get_category_distribution(
        request.user, target_month, target_year
    )

    # Insight 1: Biggest expense category
    if category_distribution:
        biggest_category = max(category_distribution,
                               key=lambda x: x['amount'])
        if biggest_category['amount'] > 0:
            insights.append(
                f"{biggest_category['category']} is your biggest expense this month."
            )

    # Insight 2: Percentage change from previous month
    percent_change = current_summary.get('percent_change', 0)
    if percent_change > 10:
        insights.append(
            f"You spent {abs(percent_change):.1f}% more this month compared to last month. "
            "Consider reviewing your expenses."
        )
    elif percent_change < -10:
        insights.append(
            f"Great! You spent {abs(percent_change):.1f}% less this month compared to last month."
        )

    # Insight 3: Balance status
    if current_balance > 0:
        insights.append("Your balance is positive this month. Great job!")
    elif current_balance < 0:
        insights.append(
            f"Warning: You spent {abs(current_balance):.2f} more than you earned this month. "
            "Consider reducing expenses."
        )

    # Insight 4: High spending threshold (if any category > 50% of total spending)
    if current_spent > 0 and category_distribution:
        for cat in category_distribution:
            percentage = (cat['amount'] / float(current_spent)) * 100
            if percentage > 50:
                insights.append(
                    f"{cat['category']} accounts for {percentage:.1f}% of your total spending. "
                    "This might be worth reviewing."
                )

    # Insight 5: Income vs expenses ratio
    if current_income > 0:
        expense_ratio = (float(current_spent) / float(current_income)) * 100
        if expense_ratio > 90:
            insights.append(
                "You're spending over 90% of your income. Consider building an emergency fund."
            )
        elif expense_ratio < 50:
            insights.append(
                "You're saving well! Keep up the good work."
            )

    # If no insights, provide a default message
    if not insights:
        insights.append(
            "Keep tracking your expenses to receive personalized insights!")

    return Response({
        'insights': insights,
        'year': target_year,
        'month': target_month,
    }, status=status.HTTP_200_OK)


# ========== New ML Analytics Views ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def anomaly_detection_view(request):
    """
    Run Isolation Forest anomaly detection on the user's transactions.

    GET /api/analytics/anomalies/
    """
    try:
        result = AnomalyDetectionService.detect_anomalies(request.user)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_categorize_view(request):
    """
    Predict the category for a given description.

    POST /api/analytics/categorize/
    Body: {"description": "Uber trip to airport"}
    """
    description = request.data.get('description', '')
    if not description:
        return Response(
            {"error": "Description is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = AutoCategorizationService.predict_category(
        request.user, description)
    if result is None:
        return Response(
            {"status": "insufficient_data",
                "message": "Not enough labelled transactions to train the model."},
            status=status.HTTP_200_OK,
        )
    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_alert_view(request):
    """
    Predictive budget alert: when will the user hit their monthly budget?

    GET /api/analytics/budget-alert/
    """
    result = BudgetAlertService.get_budget_prediction(request.user)
    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_score_view(request):
    """
    Financial health score (0-100) with grade and sub-score breakdown.

    GET /api/analytics/health-score/
    """
    result = FinancialHealthService.calculate_health_score(request.user)
    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advisor_conversations_view(request):
    """
    GET /api/analytics/advisor/conversations/
    Returns a list of the authenticated user's conversation threads,
    ordered by most-recently updated first.
    """
    conversations = AdvisorConversation.objects.filter(user=request.user)
    serializer = AdvisorConversationSerializer(conversations, many=True)
    return Response(serializer.data)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def advisor_conversation_detail_view(request, pk: int):
    """
    GET    /api/analytics/advisor/conversations/<pk>/  — full conversation with messages
    DELETE /api/analytics/advisor/conversations/<pk>/  — delete the conversation
    """
    try:
        conversation = AdvisorConversation.objects.get(
            pk=pk, user=request.user)
    except AdvisorConversation.DoesNotExist:
        return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = AdvisorConversationDetailSerializer(conversation)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def financial_advisor_view(request):
    """
    AI Financial Advisor — RAG pipeline with privacy-preserving anonymization.

    POST /api/analytics/advisor/
    Body  : {
        "query": "What are my biggest expenses this month?",
        "conversation_id": 42   # optional — omit to start a new conversation
    }

    Responses:
        200 {"status": "success",      "reply": "...", "conversation_id": 42}
        200 {"status": "out_of_scope", "reply": "...", "conversation_id": 42}
        200 {"status": "no_data",      "reply": "...", "conversation_id": 42}
        400 {"error": "A non-empty 'query' field is required."}
        503 {"status": "error",        "reply": "...", "conversation_id": 42}

    Security notes
    ──────────────
    • The view applies ScopedRateThrottle (see 'advisor' key in settings).
    • The service layer enforces a 600-character query cap to limit
      prompt-injection surface area.
    • Raw transaction data is NEVER forwarded to the LLM; it passes through
      AnonymizationService first (PII scrub, merchant abstraction, temporal
      blurring, amount jitter).
    """
    from .services.advisor_service import FinancialAdvisorService

    query: str = (request.data.get("query") or "").strip()
    if not query:
        return Response(
            {"error": "A non-empty 'query' field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Resolve or create the conversation thread ────────────────────────────
    conversation_id = request.data.get("conversation_id")
    conversation: AdvisorConversation | None = None

    if conversation_id:
        try:
            conversation = AdvisorConversation.objects.get(
                pk=conversation_id, user=request.user
            )
        except AdvisorConversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    # ── Call the RAG service ─────────────────────────────────────────────────
    lookback_days: int = int(request.data.get("lookback_days", 60))
    result = FinancialAdvisorService.get_advice(
        request.user, query, lookback_days=lookback_days
    )

    # ── Persist messages (create conversation on first turn) ─────────────────
    if conversation is None:
        title = query[:97] + "..." if len(query) > 100 else query
        conversation = AdvisorConversation.objects.create(
            user=request.user, title=title
        )

    AdvisorMessage.objects.create(
        conversation=conversation,
        role=AdvisorMessage.ROLE_USER,
        content=query,
    )
    AdvisorMessage.objects.create(
        conversation=conversation,
        role=AdvisorMessage.ROLE_ASSISTANT,
        content=result["reply"],
        status=result["status"],
    )
    # Touch updated_at so the list re-sorts correctly.
    conversation.save(update_fields=["updated_at"])

    result["conversation_id"] = conversation.pk

    http_status = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if result["status"] == "error"
        else status.HTTP_200_OK
    )
    return Response(result, status=http_status)
