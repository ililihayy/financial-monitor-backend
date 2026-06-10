from __future__ import annotations

# Finance-domain terms — a query must match at least one to be in-scope.
FINANCE_ALLOWLIST: frozenset[str] = frozenset({
    # Core financial concepts
    "budget", "spend", "spending", "expense", "expenses", "income", "salary",
    "saving", "savings", "invest", "investment", "debt", "loan", "credit",
    "debit", "mortgage", "interest", "balance", "cash", "money", "fund",
    "funds", "finance", "financial", "wealth", "net worth", "portfolio",
    # Transaction vocabulary
    "transaction", "purchase", "payment", "transfer", "deposit",
    "withdrawal", "bill", "subscription", "rent", "grocery", "groceries",
    # Analysis / planning
    "forecast", "predict", "analysis", "trend", "advice", "tip", "afford",
    "cost", "price", "rate", "tax", "insurance", "pension", "retirement",
    "emergency fund", "goal", "monthly", "yearly", "annual", "quarter",
    "year", "month", "months",
    # Common category names that appear in transaction data
    "food", "transport", "entertainment", "health", "education", "utility",
    "utilities", "restaurant", "coffee", "shopping",
    # Ukrainian finance terms
    "рік", "роки", "місяць", "місяці", "витрати", "витрат", "дохід",
    "бюджет", "заощадження", "гроші", "фінанси", "фінансовий", "зарплата",
    "борг", "кредит", "баланс", "інвестиції", "пенсія", "страхування",
})

# Out-of-topic terms — a single hit causes immediate rejection.
OOT_DENYLIST: frozenset[str] = frozenset({
    "politic", "election", "president", "government", "war", "military",
    "religion", "coding", "programming", "javascript", "algorithm",
    "recipe", "cooking", "weather", "sport", "football", "soccer",
    "basketball", "movie", "film", "music", "celebrity", "gossip",
    "dating", "relationship", "lawsuit", "diagnosis", "vaccine",
    "astrology", "horoscope",
})

# How many allowlist terms must match for the query to be accepted.
MIN_FINANCE_HITS: int = 1

# Hard cap on user-supplied query length (characters).
# Limits the surface area for prompt-injection payloads.
MAX_QUERY_LEN: int = 600

# ── Intent → focus-instruction mapping ──────────────────────────────────────
# Each tuple: (intent_label, regex_pattern, focus_instruction).
# Evaluated in order — first match wins; DEFAULT_FOCUS is the fallback.
INTENT_PATTERNS: list[tuple[str, str, str]] = [
    (
        "savings_goal",
        r'\bsav(e|ing|ings)\b|\bgoal\b|\bcar\b|\bvacation\b|\bhome\b'
        r'|\bemergency.?fund\b|\bdown.?payment\b|\bput aside\b',
        (
            "The user wants actionable savings strategies toward a specific goal. "
            "Identify which expense categories have reduction potential, "
            "compute the monthly surplus (Income minus Expense) from the data, "
            "and map a concrete path — timeline plus monthly savings target — toward "
            "their stated goal. Quantify every suggestion with exact figures from "
            "the aggregates table."
        ),
    ),
    (
        "expense_analysis",
        r'\bexpens(e|es|ive)\b|\bspend(ing)?\b|\bbiggest\b|\bmost\b'
        r'|\bwhere.*money\b|\bcategor(y|ies)\b',
        (
            "The user wants to understand their spending distribution. "
            "Rank expense categories by total and by percentage share of total outflow. "
            "Flag any category whose share appears disproportionate relative to its type. "
            "Use the anonymized transaction samples to surface behavioral micro-patterns: "
            "high-frequency low-value charges (subscriptions, daily habits), "
            "weekend clustering, or impulse-spend signatures."
        ),
    ),
    (
        "budget_check",
        r'\bbudget\b|\bover.?spen(t|ding)\b|\bleft\b|\bremain(ing)?\b'
        r'|\bon track\b|\bhow much\b',
        (
            "The user is asking about their budget status and remaining capacity. "
            "Lead with the ML signals: Budget Risk Level, % Used, projected month-end total. "
            "Cross-reference against the aggregate totals to explain which categories "
            "are the primary drivers of any overrun risk. "
            "Deliver a clear verdict — on track / at risk / over budget — backed by evidence."
        ),
    ),
    (
        "trend_analysis",
        r'\btrend\b|\bpattern\b|\bcompare\b|\blast month\b|\bover time\b'
        r'|\bchanged\b|\bhistory\b|\bforecast\b|\bpredict\b',
        (
            "The user wants to understand behavioral and spending trends over time. "
            "Look for frequency patterns in the anonymized samples: time clustering, "
            "repeated amounts, and shifts in category mix. "
            "Use the ML health score, savings rate, and daily velocity to frame "
            "the narrative trajectory and project where spending is heading."
        ),
    ),
    (
        "general_advice",
        r'\btip\b|\badvice\b|\bimprove\b|\bbetter\b|\boptimize\b|\bstrateg(y|ies)\b',
        (
            "The user is asking for holistic financial improvement strategies. "
            "Prioritize the highest-impact levers: the largest expense categories, "
            "the savings rate gap, and the budget velocity. "
            "Propose 2–3 concrete, quantified tactics each backed by a specific "
            "figure from the data."
        ),
    ),
    (
        "yearly_analysis", 
        r"\byear\b|\bannual\b|\bрік\b|\bрічний\b", 
        "Focus on long-term trends, comparing months and identifying seasonal spending spikes."
    ),
]

DEFAULT_FOCUS: str = (
    "Provide a comprehensive financial analysis covering spending distribution, "
    "budget status, and key behavioral patterns observed in the transaction data."
)
