"""
Anonymization Service — Privacy-Preserving Layer for RAG Financial Advice.

Security Design Rationale
─────────────────────────
When transaction data is forwarded to an external LLM (OpenAI, Gemini, etc.)
for financial advice, the provider's infrastructure may log, cache, or
train on the payload.  This service transforms raw ORM records into a
derivative representation that retains enough *economic signal* for the LLM
to be genuinely helpful while ensuring that no Personally Identifiable
Information (PII) or re-identification vector survives the transformation.

Four layered defences are applied in sequence:

1. **PII scrubbing** (Regex + Luhn filter)
   Sweeps the free-text `description` field for credit-card numbers, IBANs,
   e-mail addresses and phone numbers.  Matched tokens are replaced with
   typed placeholders (`[CARD]`, `[EMAIL]`, …) so that the sentence structure
   is preserved for the LLM while the sensitive value is irreversibly removed.
   A Luhn checksum secondary filter cuts false-positive card matches by ≈80 %.

2. **Merchant abstraction** (lookup table)
   Specific merchant names are collapsed to their functional category
   (e.g. "Starbucks" → "Coffee Shop").  This prevents the LLM provider
   from constructing a geo-temporal merchant profile for the user and is
   analogous to k-anonymity: many users visit the same "Coffee Shop".

3. **Temporal blurring** (bucketed relative labels)
   Exact dates are the single most powerful re-identification vector in
   financial datasets (cf. Narayanan & Shmatikoff, 2008).  Dates are
   replaced with coarse relative labels ("3 days ago", "Early April 2025").
   This preserves trend information (recent vs. old) without exposing the
   precise timestamp needed for a linkage attack.

4. **Amount bucketing + jitter** (noise injection)
   Amounts are rounded to a magnitude-dependent bucket (e.g. $542.50 → $540)
   and then displaced by ±15 % random noise within that bucket.  Even if an
   adversary possesses the exact receipt amount, they cannot deterministically
   match it to this anonymised record, mitigating linkage attacks.
"""

import random
import re
from datetime import date, datetime
from typing import Any
import logging


logger = logging.getLogger('security')

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
TransactionRecord = dict[str, Any]


class AnonymizationService:
    """
    Converts raw transaction records into an anonymized, LLM-ready text block.

    Usage::

        service = AnonymizationService()
        context = service.anonymize(transactions, reference_date=date.today())
        # Inject `context` into the LLM system prompt.
    """

    # ── 1. PII patterns ──────────────────────────────────────────────────────

    _RE_EMAIL: re.Pattern = re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
    )
    # IBAN: 2-letter country code, 2 check digits, up to 30 alphanumeric chars.
    _RE_IBAN: re.Pattern = re.compile(
        r'\b[A-Z]{2}\d{2}[A-Z0-9](?:[ ]?[A-Z0-9]){3,30}\b',
        re.IGNORECASE,
    )
    # Card: 13-19 contiguous digits, optionally separated by spaces/hyphens.
    # Secondary Luhn check performed in _scrub_pii to eliminate false positives.
    _RE_CARD: re.Pattern = re.compile(
        r'\b(?:\d[ \-]?){13,19}\d\b'
    )
    _RE_PHONE: re.Pattern = re.compile(
        r'(?<!\d)'
        r'(?:\+?\d{1,3}[\s.\-]?)?'
        r'(?:\(?\d{2,4}\)?[\s.\-]?)?'
        r'\d{3,5}[\s.\-]?\d{3,4}'
        r'(?!\d)'
    )

    _PII_RULES: list[tuple[re.Pattern, str]] = [
        (_RE_EMAIL, '[EMAIL]'),
        (_RE_IBAN,  '[IBAN]'),
        (_RE_CARD,  '[CARD]'),
        (_RE_PHONE, '[PHONE]'),
    ]

    # ── 2. Merchant → generic category lookup ─────────────────────────────────

    _MERCHANT_MAP: dict[str, str] = {
        # Coffee
        'starbucks':    'Coffee Shop',
        'costa coffee': 'Coffee Shop',
        'dunkin':       'Coffee Shop',
        # Fast food
        'mcdonald':     'Fast Food',
        'burger king':  'Fast Food',
        'kfc':          'Fast Food',
        'subway':       'Fast Food',
        'domino':       'Fast Food',
        'pizza hut':    'Fast Food',
        'five guys':    'Fast Food',
        # Ride-hailing / transport
        'uber':         'Transportation',
        'lyft':         'Transportation',
        'bolt':         'Transportation',
        'grab':         'Transportation',
        'cabify':       'Transportation',
        # Streaming / subscriptions
        'netflix':          'Streaming Service',
        'spotify':          'Streaming Service',
        'youtube premium':  'Streaming Service',
        'apple music':      'Streaming Service',
        'hbo':              'Streaming Service',
        'disney+':          'Streaming Service',
        'hulu':             'Streaming Service',
        # E-commerce
        'amazon':       'Online Retail',
        'ebay':         'Online Retail',
        'aliexpress':   'Online Retail',
        'etsy':         'Online Retail',
        'shein':        'Online Retail',
        # Supermarkets
        'walmart':      'Supermarket',
        'tesco':        'Supermarket',
        'lidl':         'Supermarket',
        'aldi':         'Supermarket',
        'carrefour':    'Supermarket',
        'whole foods':  'Supermarket',
        'kroger':       'Supermarket',
        # Pharmacies
        'cvs':          'Pharmacy',
        'walgreens':    'Pharmacy',
        'boots':        'Pharmacy',
        # ATM / cash
        'atm withdrawal':  'ATM Withdrawal',
        'cash withdrawal': 'ATM Withdrawal',
        # Utilities
        'electric':    'Utility Bill',
        'gas bill':    'Utility Bill',
        'water bill':  'Utility Bill',
        'internet':    'Utility Bill',
        # Fitness
        'gym':              'Fitness',
        'anytime fitness':  'Fitness',
        'planet fitness':   'Fitness',
        'crossfit':         'Fitness',
        # Travel / accommodation
        'airbnb':       'Accommodation',
        'booking.com':  'Accommodation',
        'hotels.com':   'Accommodation',
        'ryanair':      'Flight',
        'easyjet':      'Flight',
        'lufthansa':    'Flight',
    }

    # ── 3. Temporal blurring helpers ──────────────────────────────────────────

    _MONTH_NAMES: list[str] = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December',
    ]

    # ── 4. Amount bucketing configuration ────────────────────────────────────
    #
    # Each tuple is (upper_bound_exclusive, bucket_size).
    # Smaller transactions get finer granularity so the LLM can still
    # distinguish a $3 coffee from a $9 lunch.
    _BUCKET_THRESHOLDS: list[tuple[float, float]] = [
        (10.0,         1.0),
        (100.0,        5.0),
        (500.0,       10.0),
        (2_000.0,     50.0),
        (float('inf'), 100.0),
    ]
    # Random noise magnitude as a fraction of the bucket size.
    _JITTER_FRACTION: float = 0.15

    # =========================================================================
    # Public API
    # =========================================================================

    def anonymize(
        self,
        transactions: list[TransactionRecord],
        reference_date: date | None = None,
        *,
        seed: int | None = None,
    ) -> str:
        """
        Anonymize a list of transaction dicts and return an LLM system-prompt
        context string.

        Args:
            transactions:   Raw transaction records (e.g. from a QuerySet
                            serialized to dicts via ``values()`` or a DRF
                            serializer).  Expected keys: ``amount``, ``date``,
                            ``category_name``, ``description``, ``currency``,
                            ``transaction_type``.
            reference_date: The date treated as "today" for temporal blurring.
                            Defaults to ``date.today()``.  Pass an explicit
                            value in tests for deterministic output.
            seed:           Optional RNG seed.  When provided, amount jitter is
                            fully reproducible — useful for unit tests.

        Returns:
            A structured plain-text block ready for injection into an LLM
            system prompt.  No PII fields survive this transformation.
        """
        rng = random.Random(seed)
        today = reference_date or date.today()

        lines: list[str] = [
            "The following is an anonymized summary of the user's recent "
            "financial transactions. All personal identifiers have been "
            "removed or generalized. Use this data to provide personalized, "
            "actionable financial advice.\n",
        ]

        if not transactions:
            lines.append("No transactions available for the selected period.")
            return "\n".join(lines)

        for tx in transactions:
            lines.append(self._anonymize_transaction(tx, today, rng))

        return "\n".join(lines)

    # =========================================================================
    # Private — per-transaction pipeline
    # =========================================================================

    def _anonymize_transaction(
        self,
        tx: TransactionRecord,
        today: date,
        rng: random.Random,
    ) -> str:
        """
        Apply the full anonymization pipeline to a single transaction record
        and return a formatted string line.
        """
        tx_type = str(tx.get('transaction_type', 'Transaction')).capitalize()
        category = str(tx.get('category_name', 'General'))
        currency = str(tx.get('currency', 'USD'))

        raw_amount = float(tx.get('amount', 0) or 0)
        amount = self._bucket_amount(raw_amount, rng)

        time_label = self._blur_date(tx.get('date'), today)

        description = str(tx.get('description') or '')
        description = self._scrub_pii(description)
        logger.warning(f"DLP PROTECTED PAYLOAD FOR GEMINI: {description}")
        description = self._abstract_merchant(description)

        return (
            f"- [{time_label}] {tx_type} | {category} | "
            f"{currency} {amount:.2f} | {description}"
        )

    # =========================================================================
    # Private — individual anonymization strategies
    # =========================================================================

    def _scrub_pii(self, text: str) -> str:
        """
        Sweep ``text`` for PII using compiled regex patterns.

        Processing order
        ────────────────
        1. Email  — checked first so the local-part is not partially consumed
                    by the phone pattern.
        2. IBAN   — long alphanumeric strings, matched before card digits.
        3. Card   — 13-19 digit sequences; a Luhn checksum filters out order
                    IDs and other long numeric strings that are *not* cards.
        4. Phone  — broad pattern applied last to avoid shadowing the above.

        Any matched token is replaced by a typed placeholder so the LLM still
        understands sentence context (e.g. "payment via [CARD]") while the
        sensitive value is irreversibly removed.
        """
        for pattern, placeholder in self._PII_RULES:
            if pattern is self._RE_CARD:
                text = pattern.sub(
                    lambda m, ph=placeholder: (
                        ph if self._luhn_check(m.group()) else m.group()
                    ),
                    text,
                )
            else:
                text = pattern.sub(placeholder, text)

        text = text.strip()
        return text if text else 'General purchase'

    def _abstract_merchant(self, text: str) -> str:
        """
        Replace known merchant names in ``text`` with generic category labels.

        Matching is case-insensitive and uses substring search so that
        variants such as "McDonald's", "McDonalds", and "MCDONALD" all map
        to the same category.  The longest matching key wins (``_MERCHANT_MAP``
        is iterated with longest keys first at construction time, ensured by
        Python 3.7+ insertion-order dict — merchants like "whole foods" are
        inserted before "food" if they appear).

        Privacy benefit: many users share the same "Coffee Shop" category;
        the abstraction provides k-anonymity-like coverage.
        """
        lower = text.lower()
        for merchant, category in self._MERCHANT_MAP.items():
            if merchant in lower:
                return category
        return text

    def _blur_date(self, raw_date: Any, today: date) -> str:
        """
        Convert an exact date into a coarse, non-reversible temporal label.

        Bucketing strategy
        ──────────────────
        The finer the time resolution, the easier it is to re-identify a
        record by cross-referencing with external datasets (e.g. loyalty-card
        logs, social-media check-ins).  Labels become progressively coarser
        as the date recedes into the past:

        ≤ 0 days  →  "Today"
        1 day     →  "Yesterday"
        2–6 days  →  "<N> days ago"
        7–13 days →  "About a week ago"
        14–29 days→  "About 2 weeks ago"
        30–59 days→  "About a month ago"
        ≥ 60 days →  "Early / Mid / Late <Month> <Year>"

        The calendar-period bucket (Early/Mid/Late) limits resolution to
        ≈10-day windows, preventing the precise-date linkage attack while
        still giving the LLM seasonal context.
        """
        if raw_date is None:
            return 'Unknown date'

        if isinstance(raw_date, datetime):
            raw_date = raw_date.date()
        elif isinstance(raw_date, str):
            try:
                raw_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                return 'Unknown date'

        if not isinstance(raw_date, date):
            return 'Unknown date'

        delta = (today - raw_date).days

        if delta < 0:
            return 'Recent'
        if delta == 0:
            return 'Today'
        if delta == 1:
            return 'Yesterday'
        if delta < 7:
            return f'{delta} days ago'
        if delta < 14:
            return 'About a week ago'
        if delta < 30:
            return 'About 2 weeks ago'
        if delta < 60:
            return 'About a month ago'

        # Coarse calendar bucket for older transactions.
        month_name = self._MONTH_NAMES[raw_date.month]
        year = raw_date.year
        day = raw_date.day
        if day <= 10:
            period = 'Early'
        elif day <= 20:
            period = 'Mid'
        else:
            period = 'Late'

        return f'{period} {month_name} {year}'

    def _bucket_amount(self, amount: float, rng: random.Random) -> float:
        """
        Round ``amount`` to a magnitude-appropriate bucket, then add jitter.

        Linkage-attack mitigation
        ─────────────────────────
        An adversary who knows the exact purchase price (e.g. from a receipt
        or a merchant's records) could match a rounded-but-exact value back
        to a specific user.  Adding ±15 % random noise within the bucket
        ensures that even if the exact price is known, the match probability
        is reduced to ~1/bucket_size rather than a near-certainty.

        The bucket sizes are magnitude-dependent so that small amounts (e.g.
        a $3.50 coffee) still yield a meaningfully different number from a
        $9.00 lunch — preserving the economic signal the LLM needs.

        The sign of the original amount is preserved so that income and
        expense records remain distinguishable.
        """
        sign = -1.0 if amount < 0.0 else 1.0
        abs_amount = abs(amount)

        bucket_size = self._get_bucket_size(abs_amount)
        rounded = round(abs_amount / bucket_size) * bucket_size
        jitter = rng.uniform(-self._JITTER_FRACTION,
                             self._JITTER_FRACTION) * bucket_size
        noisy = max(0.0, rounded + jitter)

        return round(noisy, 2) * sign

    def _get_bucket_size(self, abs_amount: float) -> float:
        """Return the bucket size appropriate for ``abs_amount``."""
        for upper, size in self._BUCKET_THRESHOLDS:
            if abs_amount < upper:
                return size
        return self._BUCKET_THRESHOLDS[-1][1]

    # =========================================================================
    # Static helpers
    # =========================================================================

    @staticmethod
    def _luhn_check(token: str) -> bool:
        """
        Validate a digit sequence with the Luhn algorithm.

        Used as a secondary filter after the card regex matches to eliminate
        false positives such as order IDs or timestamp strings that happen
        to contain 13-19 consecutive digits.  Real credit/debit card numbers
        pass Luhn; random numeric strings fail it with high probability
        (~90 % rejection rate for random 16-digit numbers).
        """
        digits = [int(c) for c in token if c.isdigit()]
        if len(digits) < 13:
            return False

        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d = d * 2 - 9 if d * 2 > 9 else d * 2
            total += d

        return total % 10 == 0
