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
from .models import Category, Transaction
from .serializers import (
    CategorySerializer, TransactionSerializer, TransactionListSerializer
)
from .services import FinanceService, MLForecastService


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
        """Return system categories and user's categories."""
        user = self.request.user
        return Category.objects.filter(
            Q(user=user) | Q(user=None)  # User's categories or system categories
        ).distinct()

    def perform_create(self, serializer):
        """Set the user when creating a category."""
        serializer.save(user=self.request.user)


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
        """Set the user when creating a transaction."""
        serializer.save(user=self.request.user)


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
    Get dashboard data: totals, balance, and pie chart data.
    
    GET /api/analytics/dashboard/?year=2024&month=3
    
    Returns: {
        "totals": {
            "total_income": 5000.00,
            "total_expenses": 3500.00,
            "balance": 1500.00,
            "year": 2024,
            "month": 3
        },
        "expenses_by_category": [
            {
                "category_id": 1,
                "category_name": "Food",
                "total_amount": 500.00,
                "transaction_count": 15
            },
            ...
        ],
        "pie_chart_data": {
            "labels": ["Food", "Transport"],
            "values": [500.00, 300.00]
        }
    }
    """
    # Get optional filters
    year = request.query_params.get('year', None)
    month = request.query_params.get('month', None)
    
    # Convert to integers if provided
    year = int(year) if year else None
    month = int(month) if month else None
    
    # Get totals
    totals = FinanceService.get_dashboard_totals(request.user, year, month)
    
    # Get expenses by category
    target_year = totals['year']
    target_month = totals['month']
    expenses_by_category = FinanceService.aggregate_expenses_by_category(
        request.user, target_year, target_month, category_type='Expense'
    )
    
    # Get pie chart data
    pie_chart_data = FinanceService.get_pie_chart_data(
        request.user, target_year, target_month
    )
    
    return Response({
        'totals': totals,
        'expenses_by_category': expenses_by_category,
        'pie_chart_data': pie_chart_data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def forecast_view(request):
    """
    Get ML-based expense forecast for the next month.
    
    GET /api/analytics/forecast/?months_back=12
    
    Returns: {
        "predicted_amount": 1250.50,
        "confidence_score": 0.85,
        "months_used": 8,
        "status": "success",
        "message": "Prediction based on 8 months of data"
    }
    """
    # Get optional parameter
    months_back = request.query_params.get('months_back', 12)
    months_back = int(months_back) if months_back else 12
    
    # Ensure valid range
    months_back = max(6, min(months_back, 24))  # Between 6 and 24 months
    
    # Get prediction
    prediction = MLForecastService.predict_next_month_expense(
        request.user, months_back
    )
    
    return Response(prediction, status=status.HTTP_200_OK)


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
