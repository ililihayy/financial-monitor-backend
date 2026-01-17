"""
ML Forecast Service - Machine Learning predictions using Linear Regression.

Implements Linear Regression using Scikit-learn to predict future expenses
based on historical data. Uses month index as feature (X) and total spent as target (y).
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.db.models import DecimalField

User = get_user_model()


class MLForecastService:
    """
    Service class for Machine Learning-based expense forecasting.
    
    Implements Linear Regression to predict future monthly expenses based on
    historical spending patterns (last 6-12 months).
    
    Methodology:
    1. Group user expenses by month for the last 6-12 months
    2. Feature (X): Month index (0, 1, 2, ...)
    3. Target (y): Total spent per month
    4. Train Linear Regression model
    5. Predict next month's spending
    6. Return prediction and confidence score (R-squared)
    """

    @staticmethod
    def prepare_training_data(user, months_back: int = 12) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data from historical transactions.
        
        Groups expenses by month and creates feature matrix (X) and target vector (y).
        
        Args:
            user: User instance
            months_back: Number of months to look back (default: 12, minimum: 6)
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (X, y) where:
                X: Feature matrix (month indices, shape: (n_months, 1))
                y: Target vector (total expenses per month, shape: (n_months,))
        
        Example:
            >>> X, y = MLForecastService.prepare_training_data(user, months_back=6)
            >>> print(X.shape)  # (6, 1)
            >>> print(y.shape)  # (6,)
        """
        from transactions.models import Transaction, Category
        
        # Ensure minimum months
        months_back = max(months_back, 6)
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=months_back * 31)  # Approximate
        
        # Aggregate expenses by month
        monthly_expenses = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=start_date,
            date__lte=end_date
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total=Sum('amount', output_field=DecimalField())
        ).order_by('month')
        
        # Convert to lists
        months = []
        totals = []
        
        for item in monthly_expenses:
            months.append(item['month'])
            totals.append(float(item['total'] or Decimal('0.00')))
        
        # If we don't have enough data, return empty arrays
        if len(months) < 3:  # Need at least 3 data points for regression
            return np.array([]).reshape(-1, 1), np.array([])
        
        # Create feature matrix: month indices (0, 1, 2, ...)
        X = np.arange(len(months)).reshape(-1, 1)
        
        # Create target vector: total expenses
        y = np.array(totals)
        
        return X, y

    @staticmethod
    def predict_next_month_expense(user, months_back: int = 12) -> Dict:
        """
        Predict next month's expense using Linear Regression.
        
        Trains a Linear Regression model on historical data and predicts
        the next month's total expenses.
        
        Args:
            user: User instance
            months_back: Number of months to use for training (default: 12)
            
        Returns:
            Dict: Prediction results
            Format: {
                'predicted_amount': Decimal('1250.50'),
                'confidence_score': 0.85,  # R-squared score (0-1)
                'months_used': 8,
                'status': 'success',
                'message': 'Prediction based on 8 months of data'
            }
            
        Example:
            >>> result = MLForecastService.predict_next_month_expense(user)
            >>> print(result['predicted_amount'])  # 1250.50
            >>> print(result['confidence_score'])  # 0.85
        """
        # Prepare training data
        X, y = MLForecastService.prepare_training_data(user, months_back)
        
        # Check if we have enough data
        if len(X) < 3:
            return {
                'predicted_amount': Decimal('0.00'),
                'confidence_score': 0.0,
                'months_used': len(X),
                'status': 'insufficient_data',
                'message': 'Not enough historical data (minimum 3 months required)'
            }
        
        # Train Linear Regression model
        # Linear Regression: y = a*X + b
        # Where X is the month index and y is the total expense
        model = LinearRegression()
        model.fit(X, y)
        
        # Calculate R-squared (coefficient of determination) as confidence score
        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)
        
        # Predict next month (next month index)
        next_month_index = len(X)
        next_month_prediction = model.predict([[next_month_index]])[0]
        
        # Ensure non-negative prediction
        predicted_amount = max(0.0, next_month_prediction)
        
        # Round to 2 decimal places
        predicted_amount = round(predicted_amount, 2)
        
        return {
            'predicted_amount': Decimal(str(predicted_amount)),
            'confidence_score': round(float(r2), 4),  # R-squared score (0-1)
            'months_used': len(X),
            'status': 'success',
            'message': f'Prediction based on {len(X)} months of data'
        }

    @staticmethod
    def get_expense_trend(user, months_back: int = 12) -> Dict:
        """
        Get expense trend analysis with predictions.
        
        Provides both historical data and future prediction.
        
        Args:
            user: User instance
            months_back: Number of months to analyze
            
        Returns:
            Dict: Trend data with historical and predicted values
            Format: {
                'historical': [
                    {'month': '2024-01', 'amount': 1000.00},
                    {'month': '2024-02', 'amount': 1100.00},
                    ...
                ],
                'prediction': {
                    'predicted_amount': 1250.50,
                    'confidence_score': 0.85,
                    'next_month': '2024-04'
                },
                'trend': 'increasing'  # 'increasing', 'decreasing', 'stable'
            }
        """
        from transactions.models import Transaction, Category
        
        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=months_back * 31)
        
        monthly_expenses = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=start_date,
            date__lte=end_date
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total=Sum('amount', output_field=DecimalField())
        ).order_by('month')
        
        historical = [
            {
                'month': item['month'].strftime('%Y-%m'),
                'amount': float(item['total'] or Decimal('0.00'))
            }
            for item in monthly_expenses
        ]
        
        # Get prediction
        prediction_result = MLForecastService.predict_next_month_expense(user, months_back)
        
        # Calculate next month label
        next_month = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        next_month_str = next_month.strftime('%Y-%m')
        
        # Determine trend (simple: compare last 3 months average vs first 3 months)
        if len(historical) >= 6:
            recent_avg = np.mean([h['amount'] for h in historical[-3:]])
            older_avg = np.mean([h['amount'] for h in historical[:3]])
            
            if recent_avg > older_avg * 1.1:
                trend = 'increasing'
            elif recent_avg < older_avg * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'historical': historical,
            'prediction': {
                'predicted_amount': prediction_result['predicted_amount'],
                'confidence_score': prediction_result['confidence_score'],
                'next_month': next_month_str
            },
            'trend': trend
        }
