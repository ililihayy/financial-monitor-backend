"""
Prompt-building utilities for the FinancialAdvisorService RAG pipeline.

All functions are pure (no side effects, no Django dependencies) so they
can be unit-tested in isolation without a running Django application.
"""
from __future__ import annotations

import re

from .advisor_constants import DEFAULT_FOCUS, INTENT_PATTERNS


# ── Intent classifier ─────────────────────────────────────────────────────────

def classify_intent(query: str) -> tuple[str, str]:
    """
    Lightweight regex-based intent classifier.

    Evaluates ``INTENT_PATTERNS`` in declaration order and returns the first
    match as ``(intent_label, focus_instruction)``.  Falls back to
    ``("general_analysis", DEFAULT_FOCUS)`` when nothing matches.
    """
    lower = query.lower()
    for intent_label, pattern, focus in INTENT_PATTERNS:
        if re.search(pattern, lower):
            return intent_label, focus
    return "general_analysis", DEFAULT_FOCUS


# ── Aggregate table formatter ─────────────────────────────────────────────────

def format_aggregates(aggregates: list[dict], period_label: str) -> str:
    """
    Render SQL-aggregated category totals as a compact ASCII table.

    Pre-computing row and grand totals here (rather than letting the LLM
    derive them) gives the model exact figures to reference, eliminating
    arithmetic errors and avoiding raw high-value amounts that may trigger
    Gemini safety filters.
    """
    if not aggregates:
        return "No transaction data available."

    currency = aggregates[0].get("currency", "USD")
    total_out = sum(
        r["total_amount"] for r in aggregates if r["transaction_type"] == "Expense"
    )
    total_in = sum(
        r["total_amount"] for r in aggregates if r["transaction_type"] == "Income"
    )

    lines: list[str] = [
        f"Period: {period_label}  |  Currency: {currency}",
        f"{'Category':<26} {'Type':<9} {'Total':>10}  {'Txns':>4}",
        "-" * 54,
    ]
    for r in aggregates:
        lines.append(
            f"{r['category_name']:<26} {r['transaction_type']:<9} "
            f"{r['total_amount']:>10.2f}  {r['tx_count']:>4}"
        )
    lines += [
        "-" * 54,
        f"{'TOTAL EXPENSE':<26} {'':9} {total_out:>10.2f}",
        f"{'TOTAL INCOME':<26} {'':9} {total_in:>10.2f}",
    ]
    return "\n".join(lines)


# ── ML signals formatter ──────────────────────────────────────────────────────

def format_ml_context(ml: dict) -> str:
    """
    Render the ML signals dict into a readable plain-text block.

    Only keys that are present and non-null are emitted, keeping the prompt
    compact when ML data is unavailable.
    """
    if not ml:
        return "No ML signals available for this period."

    lines: list[str] = []

    budget = ml.get("budget")
    if budget:
        risk = budget.get("risk_level", "unknown").upper()
        spent = budget.get("total_spent_this_month", 0)
        velocity = budget.get("daily_velocity", 0)
        projected = budget.get("projected_month_end", 0)
        limit = budget.get("budget")
        pct = budget.get("budget_percent_used")
        hit_date = budget.get("budget_hit_date")

        lines.append(f"Budget Risk Level      : {risk}")
        lines.append(f"Spent This Month       : {spent:.2f}")
        lines.append(f"Daily Spend Velocity   : {velocity:.2f}")
        lines.append(f"Projected Month-End    : {projected:.2f}")
        if limit:
            lines.append(f"Monthly Budget Limit   : {limit:.2f}")
        if pct is not None:
            lines.append(f"Budget Used            : {pct:.1f}%")
        if hit_date:
            lines.append(f"Budget Exhaustion Date : {hit_date}")

    health = ml.get("health")
    if health:
        score = health.get("total_score") or health.get("score")
        if score is not None:
            lines.append(f"Financial Health Score : {score}/100")
        savings_pct = health.get("savings_rate_pct")
        if savings_pct is not None:
            lines.append(f"Savings Rate           : {savings_pct}%")

    return "\n".join(lines) if lines else "No ML signals available."


# ── System prompt assembler ───────────────────────────────────────────────────

def build_system_prompt(
    aggregates: list[dict],
    anonymised_samples: str,
    ml_context: dict,
    period_label: str,
    user_query: str = "",
) -> str:
    """
    Dynamically assemble a system prompt tailored to the user's intent.

    The persona is a "Proactive Financial Strategist" whose focus instruction
    is derived from the classified intent of the user's query.  The data
    sections (aggregates, anonymized samples, ML signals) are unchanged —
    only the framing, focus, and output-format instructions adapt per query.
    """
    ml_section = format_ml_context(ml_context)
    agg_section = format_aggregates(aggregates, period_label)
    intent_label, focus_instruction = classify_intent(user_query)

    return (
        "You are a Proactive Financial Strategist — an expert advisor who "
        "combines precise data analysis with practical, personalized financial "
        "guidance. You have access to pre-computed SQL aggregates (authoritative "
        "totals) and anonymized transaction samples (behavioral context). "
        "Your role is to connect the numbers directly to the user's specific "
        "question and deliver a response that is both data-grounded and "
        "genuinely actionable.\n\n"

        f"## USER INTENT: {intent_label.upper().replace('_', ' ')}\n"
        f"{focus_instruction}\n\n"

        "## PRE-COMPUTED CATEGORY TOTALS (authoritative — do not recalculate)\n"
        f"{agg_section}\n\n"

        "## ANONYMIZED TRANSACTION SAMPLES (behavioral context)\n"
        "Mine these for: repeated small amounts (subscriptions / daily habits), "
        "temporal clustering (weekend spikes, end-of-month bursts), "
        "high-frequency low-value transactions, and any anomalies vs the category totals.\n"
        f"{anonymised_samples}\n\n"

        "## ML SIGNALS\n"
        f"{ml_section}\n\n"

        "## RESPONSE FORMAT\n"
        "Write each section below. Be specific, cite exact figures, "
        "vary your language — never repeat the same phrasing across responses.\n\n"
        "**Analysis:**\n"
        "[2–4 sentences that directly address the user's question using the "
        "figures above. Reference specific amounts. Never restate the question.]\n\n"
        "**Key Observations:**\n"
        "- [Behavioral pattern or anomaly found in the transaction samples]\n"
        "- [Data-driven insight linking a category trend to the user's intent]\n"
        "- [Forward-looking observation using ML signals or spending velocity]\n\n"
        "**Tactical Moves:**\n"
        "- [Specific, quantified action — e.g. 'Trimming [Category] by 15% "
        "releases $X/month toward the goal']\n"
        "- [Second tactic targeting a different category or behaviour]\n"
        "- [Optional third tactic — include only if strongly supported by data]\n\n"

        "## STRICT RULES\n"
        "1. Every claim must cite a figure from the provided data. "
        "No generic platitudes.\n"
        "2. Do NOT reference user identifiers, DB IDs, or system internals.\n"
        "3. Do NOT speculate on real merchant names behind abstracted labels.\n"
        "4. Do NOT provide legal, tax, medical, or investment advice.\n"
        "5. If data is genuinely insufficient, state so in one sentence and stop."
    )
