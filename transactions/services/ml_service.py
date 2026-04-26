"""
ML Service Layer — scikit-learn powered analytics.

Services:
- MLForecastService: Linear Regression expense forecasting (existing)
- AnomalyDetectionService: Isolation Forest suspicious transaction flagging
- AutoCategorizationService: TF-IDF + RandomForest category prediction
- BudgetAlertService: Velocity-based budget-limit prediction
- FinancialHealthService: Composite 0-100 financial health score
"""

import logging
import threading
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np
from django.db.models import Avg, Count, StdDev, Sum
from django.db.models.functions import TruncMonth
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from transactions.models import Transaction

logger = logging.getLogger('security')


# ---------------------------------------------------------------------------
# 1. Existing: Linear Regression Forecast
# ---------------------------------------------------------------------------

class MLForecastService:
    @staticmethod
    def get_comprehensive_analysis(user, current_balance):
        today = date.today()

        six_months_ago = today - timedelta(days=365)
        monthly_data = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=six_months_ago,
        ).annotate(
            m_date=TruncMonth('date'),
        ).values('m_date').annotate(
            total=Sum('amount'),
        ).order_by('m_date')

        if len(monthly_data) < 3:
            return {"status": "insufficient_data", "message": "Need at least 3 months of history."}

        X = np.arange(len(monthly_data)).reshape(-1, 1)
        y = np.array([float(item['total'] or 0) for item in monthly_data])

        model = LinearRegression()
        model.fit(X, y)

        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)

        next_index = len(monthly_data)
        prediction = max(0, round(float(model.predict([[next_index]])[0]), 2))

        historical = [
            {"month": item['m_date'].strftime(
                '%b %Y'), "amount": float(item['total'] or 0)}
            for item in monthly_data
        ]

        slope = model.coef_[0]
        trend_direction = "increasing" if slope > 0 else "decreasing"

        return {
            "status": "success",
            "forecast": {
                "predicted_amount": prediction,
                "confidence_score": round(float(r2), 4),
                "trend_direction": trend_direction,
                "next_month": (today.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%b %Y'),
            },
            "historical_trends": historical,
            "mathematical_summary": {
                "r_squared": round(float(r2), 4),
                "slope": round(float(slope), 2),
                "intercept": round(float(model.intercept_), 2),
            },
        }


# ---------------------------------------------------------------------------
# 2. Anomaly Detection — Isolation Forest
# ---------------------------------------------------------------------------

class AnomalyDetectionService:
    """
    Flags suspicious transactions using sklearn's IsolationForest.

    Features per transaction:
    - amount (normalised against the user's mean)
    - day_of_week (0-6)
    - day_of_month (1-31)
    - hour_of_creation (0-23, from created_at)
    """

    MIN_SAMPLES = 20  # Need enough history for meaningful anomaly detection

    @classmethod
    def detect_anomalies(cls, user, transaction_ids: Optional[List[int]] = None) -> Dict:
        """
        Run anomaly detection for a user.

        If *transaction_ids* is provided, only those transactions are scored.
        Otherwise all of the user's transactions are scored.

        Returns dict with scored transactions and model metadata.
        """
        # Fetch raw data
        qs = Transaction.objects.filter(user=user).select_related('category')
        all_txns = list(qs.order_by('date'))

        if len(all_txns) < cls.MIN_SAMPLES:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {cls.MIN_SAMPLES} transactions for anomaly detection.",
                "flagged": [],
            }

        # Build feature matrix
        features, txn_list = cls._build_features(all_txns)

        # Train model
        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,  # expect ~5 % anomalies
            random_state=42,
        )
        model.fit(features)
        scores = model.decision_function(features)
        predictions = model.predict(features)  # 1 = normal, -1 = anomaly

        flagged = []
        for txn, score, pred in zip(txn_list, scores, predictions):
            is_anomaly = pred == -1

            if transaction_ids and txn.id not in transaction_ids and not is_anomaly:
                continue

            if is_anomaly:
                flagged.append({
                    'transaction_id': txn.id,
                    'amount': float(txn.amount),
                    'date': str(txn.date),
                    'category': txn.category.name,
                    'anomaly_score': round(float(score), 4),
                })

            # Persist flag
            if txn.is_suspicious != is_anomaly or txn.anomaly_score != round(float(score), 4):
                txn.is_suspicious = is_anomaly
                txn.anomaly_score = round(float(score), 4)
                txn.save(update_fields=['is_suspicious', 'anomaly_score'])

        return {
            "status": "success",
            "total_analysed": len(all_txns),
            "anomalies_found": len(flagged),
            "flagged_transactions": flagged,
        }

    @classmethod
    def score_single(cls, user, transaction) -> Dict:
        """
        Quick anomaly check for a single newly-created transaction.

        Fits the Isolation Forest on the user's history then scores the
        new transaction in isolation.
        """
        qs = Transaction.objects.filter(user=user).exclude(pk=transaction.pk)
        history = list(qs.order_by('date'))

        if len(history) < cls.MIN_SAMPLES:
            return {"is_suspicious": False, "anomaly_score": None}

        features_hist, _ = cls._build_features(history)
        features_new, _ = cls._build_features([transaction])

        model = IsolationForest(
            n_estimators=100, contamination=0.05, random_state=42)
        model.fit(features_hist)

        score = float(model.decision_function(features_new)[0])
        pred = model.predict(features_new)[0]
        is_anomaly = pred == -1

        transaction.is_suspicious = is_anomaly
        transaction.anomaly_score = round(score, 4)
        transaction.save(update_fields=['is_suspicious', 'anomaly_score'])

        return {"is_suspicious": is_anomaly, "anomaly_score": round(score, 4)}

    @staticmethod
    def _build_features(transactions: list) -> tuple:
        """Build numpy feature matrix from a list of Transaction instances."""
        rows = []
        valid_txns = []
        for txn in transactions:
            created_hour = txn.created_at.hour if txn.created_at else 12
            rows.append([
                float(txn.amount),
                txn.date.weekday(),
                txn.date.day,
                created_hour,
            ])
            valid_txns.append(txn)
        return np.array(rows), valid_txns


# ---------------------------------------------------------------------------
# 3. Auto-Categorization — TF-IDF + Random Forest
# ---------------------------------------------------------------------------

class AutoCategorizationService:
    """
    Predicts the most likely Category for a transaction based on its description.

    Uses TF-IDF vectorisation of descriptions → RandomForestClassifier.
    Trained on the user's own labelled transactions.
    """

    MIN_TRAINING_SAMPLES = 30
    MIN_DESCRIPTION_LENGTH = 3

    @classmethod
    def predict_category(cls, user, description: str) -> Optional[Dict]:
        """
        Predict the category for a given description.

        Returns dict with predicted category info and confidence, or None
        if the model can't be trained (not enough data).
        """
        if not description or len(description.strip()) < cls.MIN_DESCRIPTION_LENGTH:
            return None

        # Get labelled training data (transactions with descriptions)
        training_qs = Transaction.objects.filter(
            user=user,
            description__isnull=False,
        ).exclude(description='').select_related('category')

        training_data = list(training_qs)
        if len(training_data) < cls.MIN_TRAINING_SAMPLES:
            return None

        descriptions = [t.description for t in training_data]
        labels = [t.category_id for t in training_data]

        # TF-IDF vectorisation
        vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
        X = vectorizer.fit_transform(descriptions)
        y = np.array(labels)

        # Train Random Forest
        clf = RandomForestClassifier(
            n_estimators=50, random_state=42, n_jobs=-1)
        clf.fit(X, y)

        # Predict
        X_new = vectorizer.transform([description.strip()])
        predicted_id = clf.predict(X_new)[0]
        probabilities = clf.predict_proba(X_new)[0]
        confidence = float(max(probabilities))

        from transactions.models import Category
        try:
            category = Category.objects.get(pk=int(predicted_id))
        except Category.DoesNotExist:
            return None

        return {
            "predicted_category_id": category.id,
            "predicted_category_name": category.name,
            "predicted_category_type": category.type,
            "confidence": round(confidence, 4),
        }

    @classmethod
    def auto_label(cls, user, transaction) -> bool:
        """
        Auto-set ``predicted_category`` on a transaction if confidence is high.

        Returns True if a prediction was made.
        """
        if not transaction.description:
            return False

        result = cls.predict_category(user, transaction.description)
        if result and result['confidence'] >= 0.6:
            transaction.predicted_category_id = result['predicted_category_id']
            transaction.save(update_fields=['predicted_category'])
            return True
        return False


# ---------------------------------------------------------------------------
# 4. Predictive Budget Alerts
# ---------------------------------------------------------------------------

class BudgetAlertService:
    """
    Predicts when the user will exhaust their monthly budget based on
    current spending velocity.
    """

    @staticmethod
    def get_budget_prediction(user) -> Dict:
        """
        Calculate:
        - daily spending velocity this month
        - projected month-end total
        - estimated day the budget will be hit (if set)
        - risk level (low / medium / high / critical)
        """
        from django.contrib.auth import get_user_model
        today = date.today()
        month_start = today.replace(day=1)
        days_elapsed = max((today - month_start).days, 1)

        # Current month expenses
        total_spent = Transaction.objects.filter(
            user=user,
            category__type='Expense',
            date__gte=month_start,
            date__lte=today,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_spent_f = float(total_spent)
        daily_velocity = total_spent_f / days_elapsed

        # Days left in month
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(today.year, today.month +
                             1, 1) - timedelta(days=1)
        days_remaining = (month_end - today).days
        days_in_month = (month_end - month_start).days + 1

        # Projected month-end spending
        projected_total = total_spent_f + (daily_velocity * days_remaining)

        budget = float(user.monthly_budget) if user.monthly_budget else None
        budget_hit_day = None
        risk_level = 'low'
        percent_used = 0.0

        if budget and budget > 0:
            percent_used = round((total_spent_f / budget) * 100, 1)

            if daily_velocity > 0:
                remaining_budget = budget - total_spent_f
                if remaining_budget > 0:
                    days_until_hit = remaining_budget / daily_velocity
                    budget_hit_date = today + \
                        timedelta(days=int(days_until_hit))
                    if budget_hit_date <= month_end:
                        budget_hit_day = budget_hit_date.isoformat()
                else:
                    budget_hit_day = today.isoformat()  # already exceeded

            # Risk classification
            if percent_used >= 100:
                risk_level = 'critical'
            elif percent_used >= 80:
                risk_level = 'high'
            elif percent_used >= 60:
                risk_level = 'medium'
            else:
                risk_level = 'low'

        return {
            "total_spent_this_month": round(total_spent_f, 2),
            "daily_velocity": round(daily_velocity, 2),
            "projected_month_end": round(projected_total, 2),
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "budget": budget,
            "budget_percent_used": percent_used if budget else None,
            "budget_hit_date": budget_hit_day,
            "risk_level": risk_level,
        }


# ---------------------------------------------------------------------------
# 5. Financial Health Score (0 – 100)
# ---------------------------------------------------------------------------

class FinancialHealthService:
    """
    Composite financial health score derived from four sub-scores:

    1. Savings Rate Score (0-30 pts):  (income-expenses)/income
    2. Expense Volatility Score (0-25 pts):  lower monthly stddev = better
    3. Budget Adherence Score (0-25 pts):  staying under monthly budget
    4. Consistency Score (0-20 pts):  regular transaction tracking
    """

    @staticmethod
    def calculate_health_score(user) -> Dict:
        today = date.today()
        six_months_ago = today - timedelta(days=180)

        # --- Gather aggregated monthly data ---
        monthly_income = list(
            Transaction.objects.filter(
                user=user, category__type='Income', date__gte=six_months_ago,
            ).annotate(m=TruncMonth('date')).values('m').annotate(
                total=Sum('amount'),
            ).order_by('m')
        )
        monthly_expenses = list(
            Transaction.objects.filter(
                user=user, category__type='Expense', date__gte=six_months_ago,
            ).annotate(m=TruncMonth('date')).values('m').annotate(
                total=Sum('amount'),
            ).order_by('m')
        )

        inc_values = [float(m['total'] or 0) for m in monthly_income]
        exp_values = [float(m['total'] or 0) for m in monthly_expenses]

        total_income = sum(inc_values)
        total_expenses = sum(exp_values)

        if len(exp_values) < 2 and total_income == 0:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 months of financial data.",
            }

        # 1. Savings Rate Score (0-30)
        if total_income > 0:
            savings_rate = (total_income - total_expenses) / total_income
            # 30 % savings → 30 pts
            savings_score = max(0, min(30, round(savings_rate * 100)))
        else:
            savings_score = 0
        savings_rate_pct = round(
            (savings_rate if total_income > 0 else 0) * 100, 1)

        # 2. Expense Volatility Score (0-25)
        if len(exp_values) >= 2:
            exp_std = float(np.std(exp_values))
            exp_mean = float(np.mean(exp_values)) or 1.0
            cv = exp_std / exp_mean  # Coefficient of variation
            # CV < 0.1 → 25 pts, CV > 0.5 → 0 pts (linear scale)
            volatility_score = max(0, min(25, round(25 * (1 - cv / 0.5))))
        else:
            cv = 0
            volatility_score = 12  # neutral

        # 3. Budget Adherence Score (0-25)
        budget = float(user.monthly_budget) if user.monthly_budget else None
        if budget and budget > 0 and exp_values:
            months_under = sum(1 for e in exp_values if e <= budget)
            adherence_ratio = months_under / len(exp_values)
            budget_score = round(adherence_ratio * 25)
        else:
            budget_score = 15  # neutral when no budget set

        # 4. Consistency Score (0-20)
        # How many of the last 6 months had at least one transaction?
        all_months = set()
        for m in monthly_income:
            all_months.add(m['m'])
        for m in monthly_expenses:
            all_months.add(m['m'])

        total_possible_months = 6
        active_months = len(all_months)
        consistency_score = round((active_months / total_possible_months) * 20)

        # Composite score
        total_score = savings_score + volatility_score + budget_score + consistency_score
        total_score = max(0, min(100, total_score))

        # Grade
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        elif total_score >= 20:
            grade = 'D'
        else:
            grade = 'F'

        return {
            "status": "success",
            "health_score": total_score,
            "grade": grade,
            "breakdown": {
                "savings_rate": {"score": savings_score, "max": 30, "savings_rate_pct": savings_rate_pct},
                "expense_volatility": {"score": volatility_score, "max": 25, "cv": round(cv, 4)},
                "budget_adherence": {"score": budget_score, "max": 25, "budget_set": budget is not None},
                "consistency": {"score": consistency_score, "max": 20, "active_months": active_months},
            },
            "period_months": total_possible_months,
        }


# ---------------------------------------------------------------------------
# Background retraining helper (lightweight — uses threading, no Celery)
# ---------------------------------------------------------------------------

class MLRetrainingService:
    """
    Fire-and-forget background ML tasks using daemon threads.
    Suitable for light workloads; for heavy production use swap to
    django-rq or Celery.
    """

    @staticmethod
    def retrain_anomaly_model_async(user):
        """Retrain anomaly detection for *user* in a background thread."""
        def _run():
            try:
                AnomalyDetectionService.detect_anomalies(user)
                logger.info(
                    'Background anomaly retraining complete for user %s', user.decrypted_email)
            except Exception as exc:
                logger.error('Background anomaly retraining failed: %s', exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @staticmethod
    def auto_categorize_async(user, transaction):
        """Auto-categorize a transaction in the background."""
        def _run():
            try:
                AutoCategorizationService.auto_label(user, transaction)
                logger.info(
                    'Auto-categorization complete for txn %s', transaction.id)
            except Exception as exc:
                logger.error('Auto-categorization failed: %s', exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
