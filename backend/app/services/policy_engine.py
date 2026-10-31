"""
services/policy_engine.py — Deterministic, standalone policy evaluator.

This module is the trust boundary for spending decisions.
It never trusts AI output, browser input, or URL parameters.
All monetary arithmetic uses integer cents (no floating-point).

Decision codes used in decision_reasons:
  ALLOWED
  UNKNOWN_PRODUCT
  MERCHANT_NOT_APPROVED
  MAX_ORDER_AMOUNT_EXCEEDED
  TOTAL_BUDGET_EXCEEDED
  REQUIRES_HUMAN_APPROVAL
  NEGATIVE_OR_ZERO_PRICE
  INVALID_CURRENCY
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PolicySnapshot:
    """
    Immutable snapshot of policy state passed to the engine.
    All money in integer cents.
    """
    total_budget_cents: int
    max_per_order_cents: int
    currency: str
    approved_merchant_ids: list[str]
    require_approval: bool
    successful_spend_cents: int
    daily_limit_cents: int = 0
    monthly_limit_cents: int = 0
    blocked_categories: list[str] = field(default_factory=list)
    agent_enabled: bool = True
    daily_spend_cents: int = 0
    monthly_spend_cents: int = 0


@dataclass
class ProductSnapshot:
    """
    Authoritative product values fetched from the database.
    The engine never reads price or merchant from AI output or browser input.
    """
    id: str
    price_cents: int
    currency: str
    merchant_id: str
    category: str = "peripherals"


@dataclass
class PolicyResult:
    decision: str                          # "ALLOWED" | "BLOCKED"
    reasons: list[str] = field(default_factory=list)          # machine-readable codes
    explanations: list[str] = field(default_factory=list)     # human-readable messages

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOWED"


def evaluate(
    policy: PolicySnapshot,
    product: ProductSnapshot,
    human_approved: bool = False,
) -> PolicyResult:
    """
    Evaluate a proposed purchase against the current policy.

    Rules (all must pass for ALLOWED):
      0. Agent must be enabled.
      1. Category must not be blocked.
      2. Product price must be positive.
      3. Currency must match.
      4. Price must not exceed max_per_order cap.
      5. Price must not exceed daily limit.
      6. Price must not exceed monthly limit.
      7. Merchant must be in the approved list.
      8. Proposed spend must not exceed remaining budget.
      9. If policy requires human approval, human_approved must be True.

    Returns a PolicyResult with decision and reason codes.
    Never raises — always returns a safe result.
    """
    reasons: list[str] = []
    explanations: list[str] = []

    # Rule 0 — agent enabled check
    if not policy.agent_enabled:
        reasons.append("AGENT_DISABLED")
        explanations.append(
            "The AI purchasing agent is currently disabled by administrator policy."
        )

    # Rule 1 — category block check
    if product.category and any(
        product.category.lower() == c.lower() for c in policy.blocked_categories
    ):
        reasons.append("CATEGORY_BLOCKED")
        explanations.append(
            f"Product category '{product.category}' is blocked by administrator policy."
        )

    # Rule 2 — price sanity
    if product.price_cents <= 0:
        reasons.append("NEGATIVE_OR_ZERO_PRICE")
        explanations.append(
            f"Product price ({product.price_cents} cents) must be a positive integer."
        )

    # Rule 3 — currency match
    if product.currency.upper() != policy.currency.upper():
        reasons.append("INVALID_CURRENCY")
        explanations.append(
            f"Product currency '{product.currency}' does not match policy currency '{policy.currency}'."
        )

    # Rule 4 — per-order cap
    if product.price_cents > policy.max_per_order_cents:
        reasons.append("MAX_ORDER_AMOUNT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} but per-order cap is "
            f"{_fmt(policy.max_per_order_cents)}."
        )

    # Rule 5 — daily spend limit
    if policy.daily_limit_cents > 0 and (policy.daily_spend_cents + product.price_cents) > policy.daily_limit_cents:
        reasons.append("DAILY_LIMIT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} which would exceed the daily limit of "
            f"{_fmt(policy.daily_limit_cents)} (already spent today: {_fmt(policy.daily_spend_cents)})."
        )

    # Rule 6 — monthly spend limit
    if policy.monthly_limit_cents > 0 and (policy.monthly_spend_cents + product.price_cents) > policy.monthly_limit_cents:
        reasons.append("MONTHLY_LIMIT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} which would exceed the monthly limit of "
            f"{_fmt(policy.monthly_limit_cents)} (already spent this month: {_fmt(policy.monthly_spend_cents)})."
        )

    # Rule 7 — merchant allowlist
    if product.merchant_id not in policy.approved_merchant_ids:
        reasons.append("MERCHANT_NOT_APPROVED")
        explanations.append(
            f"Merchant '{product.merchant_id}' is not in the approved merchant list."
        )

    # Rule 8 — remaining budget
    remaining = policy.total_budget_cents - policy.successful_spend_cents
    if product.price_cents > remaining:
        reasons.append("TOTAL_BUDGET_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} but only "
            f"{_fmt(remaining)} remains in the total budget."
        )

    # Rule 9 — human approval gate (only blocks at create-order time, not at proposal time)
    if policy.require_approval and not human_approved:
        reasons.append("REQUIRES_HUMAN_APPROVAL")
        explanations.append(
            "This policy requires explicit human approval before a payment order can be created."
        )

    if reasons:
        return PolicyResult(decision="BLOCKED", reasons=reasons, explanations=explanations)

    return PolicyResult(decision="ALLOWED", reasons=[], explanations=[])


def evaluate_proposal(policy: PolicySnapshot, product: ProductSnapshot) -> PolicyResult:
    """
    Evaluate a proposal without requiring human approval yet.
    Rule 9 (human approval) is intentionally skipped here —
    the user will see the ALLOWED decision and must still click Approve.
    """
    reasons: list[str] = []
    explanations: list[str] = []

    # Rule 0 — agent enabled check
    if not policy.agent_enabled:
        reasons.append("AGENT_DISABLED")
        explanations.append(
            "The AI purchasing agent is currently disabled by administrator policy."
        )

    # Rule 1 — category block check
    if product.category and any(
        product.category.lower() == c.lower() for c in policy.blocked_categories
    ):
        reasons.append("CATEGORY_BLOCKED")
        explanations.append(
            f"Product category '{product.category}' is blocked by administrator policy."
        )

    if product.price_cents <= 0:
        reasons.append("NEGATIVE_OR_ZERO_PRICE")
        explanations.append(f"Product price ({product.price_cents} cents) must be positive.")

    if product.currency.upper() != policy.currency.upper():
        reasons.append("INVALID_CURRENCY")
        explanations.append(
            f"Product currency '{product.currency}' does not match policy currency '{policy.currency}'."
        )

    if product.price_cents > policy.max_per_order_cents:
        reasons.append("MAX_ORDER_AMOUNT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} but per-order cap is "
            f"{_fmt(policy.max_per_order_cents)}."
        )

    if policy.daily_limit_cents > 0 and (policy.daily_spend_cents + product.price_cents) > policy.daily_limit_cents:
        reasons.append("DAILY_LIMIT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} which would exceed the daily limit of "
            f"{_fmt(policy.daily_limit_cents)} (already spent today: {_fmt(policy.daily_spend_cents)})."
        )

    if policy.monthly_limit_cents > 0 and (policy.monthly_spend_cents + product.price_cents) > policy.monthly_limit_cents:
        reasons.append("MONTHLY_LIMIT_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} which would exceed the monthly limit of "
            f"{_fmt(policy.monthly_limit_cents)} (already spent this month: {_fmt(policy.monthly_spend_cents)})."
        )

    if product.merchant_id not in policy.approved_merchant_ids:
        reasons.append("MERCHANT_NOT_APPROVED")
        explanations.append(
            f"Merchant '{product.merchant_id}' is not in the approved merchant list."
        )

    remaining = policy.total_budget_cents - policy.successful_spend_cents
    if product.price_cents > remaining:
        reasons.append("TOTAL_BUDGET_EXCEEDED")
        explanations.append(
            f"Product costs {_fmt(product.price_cents)} but only "
            f"{_fmt(remaining)} remains in the total budget."
        )

    if reasons:
        return PolicyResult(decision="BLOCKED", reasons=reasons, explanations=explanations)
    return PolicyResult(decision="ALLOWED", reasons=[], explanations=[])


def _fmt(cents: int) -> str:
    """Format cents as a dollar string for human-readable explanations."""
    return f"${cents / 100:.2f}"
