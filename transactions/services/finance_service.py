"""
Finance Service Layer - Business logic for financial calculations.

Handles balance calculations, expense aggregations, and financial analytics.
All business logic is centralized here following the Service Layer pattern.
"""

from django.db.models import Sum, Q, DecimalField
from django.db.models.functions import TruncMonth
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
from django.contrib.auth import get_user_model

User = get_user_model()


class FinanceService:
    """
    Service class for financial calculations and aggregations.
    
    Provides methods for:
    - Calculating current monthly balance (Income - Expenses)
    - Aggregating expenses by category for a specific month/year
    - Getting financial totals and statistics
    """

    @staticmethod
    def calculate_monthly_balance(user, year: int, month: int) -> Decimal:
        """
        Calculate the current monthly balance: Income - Expenses.
        
        Args:
            user: User instance for which to calculate balance
            year: Year (e.g., 2024)
            month: Month (1-12)
            
        Returns:
            Decimal: Monthly balance (Income - Expenses)
            
        Example:
            >>> balance = FinanceService.calculate_monthly_balance(user, 2024, 3)
            >>> print(balance)  # 1500.00 (if Income=5000, Expenses=3500)
        """
        from transactions.models import Transaction, Category
        
        # Get start and end dates for the month
        start_date = date(year, month, 1)
        # Calculate last day of the month
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # Calculate total income
        income_total = Transaction.objects.filter(
            user=user,
            category__type='Income',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('amount', output_field=DecimalField())
        )['total'] or Decimal('0.00')
        
        # Calculate total expenses
        expenses_total = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('amount', output_field=DecimalField())
        )['total'] or Decimal('0.00')
        
        # Balance = Income - Expenses
        balance = income_total - expenses_total
        
        return balance

    @staticmethod
    def aggregate_expenses_by_category(
        user,
        year: int,
        month: int,
        category_type: str = 'Expense'
    ) -> List[Dict]:
        """
        Aggregate expenses (or income) by category for a specific month/year.
        
        Args:
            user: User instance
            year: Year (e.g., 2024)
            month: Month (1-12)
            category_type: 'Expense' or 'Income' (default: 'Expense')
            
        Returns:
            List[Dict]: List of dictionaries with category info and total amount
            Format: [
                {
                    'category_id': 1,
                    'category_name': 'Food',
                    'category_type': 'Expense',
                    'icon_identifier': 'food',
                    'total_amount': Decimal('500.00'),
                    'transaction_count': 15
                },
                ...
            ]
        """
        from transactions.models import Transaction, Category
        
        # Get start and end dates for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # Aggregate transactions by category
        aggregations = Transaction.objects.filter(
            user=user,
            category__type=category_type,
            date__gte=start_date,
            date__lt=end_date
        ).values('category').annotate(
            total_amount=Sum('amount', output_field=DecimalField()),
            transaction_count=Sum(1)
        ).order_by('-total_amount')
        
        # Enrich with category details
        result = []
        for agg in aggregations:
            try:
                category = Category.objects.get(pk=agg['category'])
                result.append({
                    'category_id': category.id,
                    'category_name': category.name,
                    'category_type': category.type,
                    'icon_identifier': category.icon_identifier,
                    'total_amount': agg['total_amount'] or Decimal('0.00'),
                    'transaction_count': agg['transaction_count'] or 0,
                })
            except Category.DoesNotExist:
                continue
        
        return result

    @staticmethod
    def get_dashboard_totals(user, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        """
        Get total income, expenses, and balance for dashboard.
        
        Args:
            user: User instance
            year: Optional year filter (default: current year)
            month: Optional month filter (default: current month)
            
        Returns:
            Dict: Dictionary with totals
            Format: {
                'total_income': Decimal('5000.00'),
                'total_expenses': Decimal('3500.00'),
                'balance': Decimal('1500.00'),
                'year': 2024,
                'month': 3
            }
        """
        from transactions.models import Transaction, Category
        
        # Use current date if not provided
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month
        
        # Get date range
        start_date = date(target_year, target_month, 1)
        if target_month == 12:
            end_date = date(target_year + 1, 1, 1)
        else:
            end_date = date(target_year, target_month + 1, 1)
        
        # Calculate totals
        income_total = Transaction.objects.filter(
            user=user,
            category__type='Income',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('amount', output_field=DecimalField())
        )['total'] or Decimal('0.00')
        
        expenses_total = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('amount', output_field=DecimalField())
        )['total'] or Decimal('0.00')
        
        balance = income_total - expenses_total
        
        return {
            'total_income': income_total,
            'total_expenses': expenses_total,
            'balance': balance,
            'year': target_year,
            'month': target_month,
        }

    @staticmethod
    def get_pie_chart_data(user, year: int, month: int) -> Dict:
        """
        Get data formatted for pie chart visualization.
        
        Args:
            user: User instance
            year: Year
            month: Month
            
        Returns:
            Dict: Formatted data for pie chart
            Format: {
                'labels': ['Food', 'Transport', 'Shopping'],
                'values': [500.00, 300.00, 200.00],
                'colors': ['#FF6384', '#36A2EB', '#FFCE56'],  # Optional
            }
        """
        expense_data = FinanceService.aggregate_expenses_by_category(
            user, year, month, category_type='Expense'
        )
        
        labels = [item['category_name'] for item in expense_data]
        values = [float(item['total_amount']) for item in expense_data]
        
        return {
            'labels': labels,
            'values': values,
        }

    @staticmethod
    def get_dashboard_summary(user, month: int, year: int) -> Dict:
        current_totals = FinanceService.get_dashboard_totals(user, year, month)
        
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year

        prev_totals = FinanceService.get_dashboard_totals(user, prev_year, prev_month)

        def calculate_percent_change(current, previous):
            curr_f = float(current)
            prev_f = float(previous)
            if prev_f == 0:
                return 100.0 if curr_f > 0 else 0.0
            return round(((curr_f - prev_f) / prev_f) * 100, 2)

        return {
            'total_income': current_totals['total_income'],
            'total_spent': current_totals['total_expenses'],
            'current_balance': current_totals['balance'],
            'income_percent_change': calculate_percent_change(current_totals['total_income'], prev_totals['total_income']),
            'spent_percent_change': calculate_percent_change(current_totals['total_expenses'], prev_totals['total_expenses']),
            'balance_percent_change': calculate_percent_change(current_totals['balance'], prev_totals['balance']),
            'year': year,
            'month': month
        }

    @staticmethod
    def get_category_distribution(user, month: int, year: int) -> List[Dict]:
        expenses_by_category = FinanceService.aggregate_expenses_by_category(user, year, month)
        
        return [
            {
                'name': item['category_name'],
                'value': float(item['total_amount'])
            }
            for item in expenses_by_category
        ]
    