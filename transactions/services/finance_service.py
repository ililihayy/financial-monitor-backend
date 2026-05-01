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


# transactions/services.py

class FinanceService:
    @staticmethod
    def calculate_monthly_balance(user, year: int, month: int) -> Decimal:
        from transactions.models import Transaction

        # Отримуємо транзакції замість агрегації в БД[cite: 7]
        transactions = Transaction.objects.filter(
            user=user,
            date__year=year,
            date__month=month
        ).select_related('category')

        income = sum(
            tx.decrypted_amount for tx in transactions if tx.category.type == 'Income')
        expenses = sum(
            tx.decrypted_amount for tx in transactions if tx.category.type == 'Expense')

        return income - expenses

    @staticmethod
    def aggregate_expenses_by_category(user, year: int, month: int, category_type: str = 'Expense') -> List[Dict]:
        from transactions.models import Transaction, Category
        from collections import defaultdict

        # Отримуємо всі транзакції за місяць[cite: 7]
        transactions = Transaction.objects.filter(
            user=user,
            category__type=category_type,
            date__year=year,
            date__month=month
        ).select_related('category')

        # Групуємо в коді Python[cite: 7]
        cat_map = defaultdict(
            lambda: {'total': Decimal('0.00'), 'count': 0, 'obj': None})

        for tx in transactions:
            cat_id = tx.category.id
            cat_map[cat_id]['total'] += tx.decrypted_amount
            cat_map[cat_id]['count'] += 1
            cat_map[cat_id]['obj'] = tx.category

        result = []
        for cat_id, data in cat_map.items():
            result.append({
                'category_id': cat_id,
                # Дешифрована назва[cite: 1]
                'category_name': data['obj'].decrypted_name,
                'category_type': data['obj'].type,
                'icon_identifier': data['obj'].icon_identifier,
                'total_amount': data['total'],
                'transaction_count': data['count'],
            })

        return sorted(result, key=lambda x: x['total_amount'], reverse=True)

    @staticmethod
    def get_dashboard_totals(user, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        from transactions.models import Transaction
        today = date.today()
        target_year, target_month = year or today.year, month or today.month

        transactions = Transaction.objects.filter(
            user=user, date__year=target_year, date__month=target_month
        ).select_related('category')

        income = sum(
            tx.decrypted_amount for tx in transactions if tx.category.type == 'Income')
        expenses = sum(
            tx.decrypted_amount for tx in transactions if tx.category.type == 'Expense')

        return {
            'total_income': income,
            'total_expenses': expenses,
            'balance': income - expenses,
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

        prev_totals = FinanceService.get_dashboard_totals(
            user, prev_year, prev_month)

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
            'category_distribution': FinanceService.get_category_distribution(user, month, year),
            'year': year,
            'month': month
        }

    @staticmethod
    def get_category_distribution(user, month: int, year: int) -> List[Dict]:
        expenses_by_category = FinanceService.aggregate_expenses_by_category(
            user, year, month)

        return [
            {
                'name': item['category_name'],
                'value': float(item['total_amount'])
            }
            for item in expenses_by_category
        ]
