import logging
import re
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from datetime import date

from .advisor_constants import (
    FINANCE_ALLOWLIST,
    OOT_DENYLIST,
    MIN_FINANCE_HITS,
    MAX_QUERY_LEN,
)
from .advisor_prompts import build_system_prompt
from .anonymization_service import AnonymizationService

logger = logging.getLogger("security")

# ── Optional dependency: google-genai SDK (v1.0+) ───────────────────────────
# Imported lazily so that the module loads cleanly even when the package is
# absent (useful in test environments without the full dependency tree).
_genai_module = None
_genai_available = False
try:
    from google import genai as _genai_module  # type: ignore[import]
    _genai_available = True
except ImportError:
    pass


class FinancialAdvisorService:
    """
    Orchestrates the five-stage RAG pipeline:

    ① Intent classification → ② ORM retrieval → ③ Anonymization
    → ④ Prompt construction → ⑤ LLM generation

    All methods are class methods to remain stateless and thread-safe.
    A single shared ``AnonymizationService`` instance is reused across
    calls; it holds no mutable state.
    """

    _anonymizer: AnonymizationService = AnonymizationService()

    @classmethod
    def get_advice(
        cls,
        user,
        user_query: str,
        *,
        lookback_days: int = 60,
    ) -> dict:
        """
        Process a natural-language financial query and return LLM-generated
        advice, or a canned response if the query is out of scope.

        Args:
            user:          Authenticated Django user instance.
            user_query:    Raw text from the end user.
            lookback_days: Days of transaction history to include in context.
                           Clamped to [30, 90].

        Returns:
            dict with two keys:
            ``status`` — "success" | "out_of_scope" | "no_data" | "error"
            ``reply``  — Human-readable string; always safe to display.
        """
        # Hard-limit query length before any further processing.
        user_query = user_query.strip()[:MAX_QUERY_LEN]

        today = date.today().isoformat()
        cache_key = f"adv_limit_{user.pk}_{today}"
        usage_count = cache.get(cache_key, 0)
        daily_limit = getattr(settings, "ADVISOR_DAILY_LIMIT", 7)

        if usage_count >= daily_limit:
            logger.warning("Advisor limit reached for user %s", user.pk)
            return {
                "status": "limit_reached",
                "reply": f"You have reached your daily request limit ({usage_count}/{daily_limit}). Try again tomorrow!",
                "usage_tracker": f"{usage_count}/{daily_limit}"
            }

        if not cls._is_finance_query(user_query):
            logger.info(
                "FinancialAdvisorService: out-of-scope query rejected "
                "(user_id=%s, query_prefix=%.60r)",
                user.pk, user_query,
            )
            return {
                "status": "out_of_scope",
                "reply": (
                    "I'm your personal Finance Coach and can only help with "
                    "budgeting, spending analysis, savings, and financial "
                    "planning. Your question appears to be outside that scope. "
                    "Please ask me something about your finances!"
                ),
            }

        # Stage ②: RAG retrieval
        since_date, period_label = cls._detect_timeframe(user_query)
        tx_data = cls._retrieve_transactions(user, since_date)
        ml_context = cls._retrieve_ml_context(user)

        if not tx_data["aggregates"]:
            return {
                "status": "no_data",
                "reply": (
                    f"No transactions found for {period_label}. "
                    "Start logging your income and expenses and I'll be able "
                    "to give you personalised guidance!"
                ),
            }

        # Stage ③: Anonymization
        #
        # Only the sample slice passes through the anonymizer.
        # Exact totals come from SQL aggregates and are injected as a pre-computed table.
        anonymised_samples = cls._anonymizer.anonymize(
            tx_data["samples"],
            reference_date=date.today(),
        )

        # Stage ④: Prompt construction
        system_prompt = build_system_prompt(
            tx_data["aggregates"], anonymised_samples, ml_context, period_label,
            user_query=user_query)

        # Stage ⑤: LLM call
        try:
            reply = cls._call_llm(system_prompt, user_query)
            new_usage = usage_count + 1
            cache.set(cache_key, new_usage, timeout=86400)
        except Exception as exc:
            logger.error(
                "FinancialAdvisorService: LLM call failed "
                "(user_id=%s): %s",
                user.pk, exc, exc_info=True,
            )
            return {
                "status": "error",
                "reply": (
                    "The AI advisor is temporarily unavailable. "
                    "Please try again in a moment."
                ),
            }

        logger.info(
            "FinancialAdvisorService: advice delivered "
            "(user_id=%s, category_count=%d, query_len=%d)",
            user.pk, len(tx_data["aggregates"]), len(user_query),
        )
        return {"status": "success", "reply": reply}

    # Intent guardrail
    @classmethod
    def _is_finance_query(cls, query: str) -> bool:
        """
        Two-stage classifier for finance-related queries.
        Stage A: Denylist check (hard blockers).
        Stage B: Allowlist check (affirmative signal).
        """
        lower = query.lower()

        for blocked in OOT_DENYLIST:
            if re.search(rf'\b{re.escape(blocked)}\b', lower):
                return False

        hits = sum(
            1 for term in FINANCE_ALLOWLIST
            if re.search(rf'\b{re.escape(term)}\b', lower)
        )
        return hits >= MIN_FINANCE_HITS

    # RAG retrieval
    @classmethod
    def _detect_timeframe(cls, query: str) -> tuple["date", str]:
        """
        Parse the query for timeframe keywords and return (cutoff_date, period_label).

        Priority order:
        1. "year" / "рік" / "роки" → Jan 1 of the current year.
        2. "N months" / "N місяці" → N × 30 days back.
        3. Default → last 30 days (current month label).
        """
        lower = query.lower()
        today = date.today()

        if re.search(r'\byear\b|\bрік\b|\bроки\b|\bроку\b', lower):
            cutoff = date(today.year, 1, 1)
            return cutoff, str(today.year)

        m = re.search(r'\b(\d+)\s*(?:month|months|місяць|місяці)', lower)
        if m:
            n = max(1, min(int(m.group(1)), 24))  # clamp 1–24
            cutoff = today - timedelta(days=n * 30)
            return cutoff, f"Last {n} month{'s' if n > 1 else ''}"

        cutoff = today - timedelta(days=60)
        start_month = cutoff.strftime("%B")
        end_month = today.strftime("%B %Y")
        period_label = f"Last 2 Months ({start_month} - {end_month})"

        return cutoff, period_label

    @classmethod
    def _retrieve_transactions(cls, user, since_date: "date") -> dict:
        from transactions.models import Transaction
        from collections import defaultdict

        currency = getattr(user, "currency", "USD") or "USD"
        # Отримуємо всі транзакції об'єктами, щоб спрацювало дешифрування[cite: 4, 8]
        base_qs = Transaction.objects.select_related("category").filter(
            user=user, date__gte=since_date
        )

        # --- 1. Агрегація в Python (замість SQL SUM) ---
        agg_map = defaultdict(
            lambda: {"count": 0, "total": 0.0, "type": "Expense"})

        all_txns = list(base_qs)
        for tx in all_txns:
            cat_name = tx.category.decrypted_name
            agg_map[cat_name]["total"] += float(tx.decrypted_amount)
            agg_map[cat_name]["count"] += 1
            agg_map[cat_name]["type"] = tx.category.type

        aggregates = [
            {
                "category_name": name,
                "transaction_type": data["type"],
                "total_amount": data["total"],
                "tx_count": data["count"],
                "currency": currency,
            }
            for name, data in agg_map.items()
        ]
        # Сортуємо за сумою[cite: 8]
        aggregates.sort(key=lambda x: x["total_amount"], reverse=True)

        # --- 2. Вибірка прикладів (Samples) ---
        samples = [
            {
                "amount": float(tx.decrypted_amount),
                "date": tx.date,
                "description": tx.decrypted_description,
                "category_name": tx.category.decrypted_name,
                "transaction_type": tx.category.type,
                "currency": currency,
            }
            for tx in all_txns[:15]
        ]

        return {"aggregates": aggregates, "samples": samples}

    @classmethod
    def _retrieve_ml_context(cls, user) -> dict:
        """
        Pull ML-derived budget and health signals to enrich the context.

        This method is deliberately exception-safe: ML models can fail due to
        insufficient historical data, and that must never abort the main
        advice pipeline.  On any failure an empty dict is returned and the
        prompt section simply reports "No ML signals available."
        """
        from transactions.services.ml_service import (
            BudgetAlertService,
            FinancialHealthService,
        )

        result: dict = {}

        try:
            budget = BudgetAlertService.get_budget_prediction(user)
            result["budget"] = budget
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "FinancialAdvisorService: BudgetAlertService failed: %s", exc
            )

        try:
            health = FinancialHealthService.calculate_health_score(user)
            if health.get("status") != "insufficient_data":
                result["health"] = health
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "FinancialAdvisorService: FinancialHealthService failed: %s",
                exc,
            )

        return result

    # LLM call
    @classmethod
    def _call_llm(cls, system_prompt: str, user_query: str) -> str:
        """
        Deliver the sanitised prompt + user query to the Gemini 2.5 Flash API
        via the google-genai v1.0+ SDK.

        Security notes
        ──────────────
        • ``system_instruction`` is passed via ``GenerateContentConfig``, which
          is structurally separate from ``contents`` (conversation turns).
          Negative constraints therefore live at a higher privilege level than
          the user message and cannot be overridden by prompt injection.
        • ``temperature=0.4`` balances creativity with factual grounding.
        • ``max_output_tokens=1024`` caps response size to control cost.
        • A new ``Client`` is instantiated per call for thread safety.

        Raises:
            RuntimeError:   If the google-genai package is missing or the API
                            key is not configured.
            Exception:      Gemini API / network errors are re-raised for
                            upstream handling in ``get_advice``.
        """
        if not _genai_available or _genai_module is None:
            raise RuntimeError(
                "The 'google-genai' package is not installed. "
                "Add it to requirements.txt: google-genai>=1.0.0"
            )

        api_key: str | None = getattr(settings, "GOOGLE_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured in Django settings. "
                "Set it via the GOOGLE_API_KEY environment variable."
            )

        model_name: str = getattr(
            settings, "ADVISOR_LLM_MODEL", "gemini-2.5-flash"
        )

        from google.genai import types

        client = _genai_module.Client(api_key=api_key)

        safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            # 0.7 — enough variation for natural advisory language while
            # still grounding outputs in the figures supplied in the prompt.
            temperature=0.7,
            # 3000 visible tokens — covers the full structured response
            # (stats + analysis + observations + tactics) without risk of
            # truncation.
            max_output_tokens=3000,
            safety_settings=safety_settings,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        response = client.models.generate_content(
            model=model_name,
            contents=user_query,
            config=config,
        )

        candidate = response.candidates[0]
        finish_reason = candidate.finish_reason
        # Compare by name — the integer mapping can differ across SDK versions.
        finish_name: str = (
            finish_reason.name
            if hasattr(finish_reason, "name")
            else str(finish_reason)
        )
        logger.info(
            "Gemini finish_reason=%s (raw=%s)",
            finish_name, getattr(finish_reason, "value", finish_reason),
        )

        # In google-genai v1.0+, response.text is accessible for both STOP
        # and MAX_TOKENS (partial output) — attempt it first in all cases.
        try:
            text = response.text
            if text:
                if finish_name != "STOP":
                    logger.warning(
                        "Gemini non-STOP finish_reason=%s — returning partial response",
                        finish_name,
                    )
                return text.strip()
        except (ValueError, AttributeError):
            pass

        # Last-resort: stitch parts manually (e.g. SAFETY block with partial output).
        try:
            parts = candidate.content.parts
            partial = "".join(
                p.text for p in parts if hasattr(p, "text")
            ).strip()
            if partial:
                return partial
        except (AttributeError, TypeError):
            pass

        raise RuntimeError(
            f"Gemini response blocked or empty (finish_reason={finish_name})")
