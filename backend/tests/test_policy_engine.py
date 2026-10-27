"""
tests/test_policy_engine.py — Deterministic unit tests for policy_engine.py

These tests do NOT require a database or running server.
They prove business rules are enforced independently of the AI.
"""
import pytest
from app.services.policy_engine import (
    PolicySnapshot,
    ProductSnapshot,
    evaluate,
    evaluate_proposal,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_policy(**overrides) -> PolicySnapshot:
    defaults = dict(
        total_budget_cents=10000,        # $100.00
        max_per_order_cents=4000,        # $40.00
        currency="USD",
        approved_merchant_ids=["techcore", "homeplus"],
        require_approval=True,
        successful_spend_cents=0,
    )
    defaults.update(overrides)
    return PolicySnapshot(**defaults)


def make_product(**overrides) -> ProductSnapshot:
    defaults = dict(
        id="tc-wireless-mouse",
        price_cents=2999,               # $29.99 — under $40 cap
        currency="USD",
        merchant_id="techcore",         # in approved list
    )
    defaults.update(overrides)
    return ProductSnapshot(**defaults)


# ── Allowed cases ─────────────────────────────────────────────────────────────

def test_eligible_purchase_is_allowed():
    result = evaluate_proposal(make_policy(), make_product())
    assert result.allowed
    assert result.decision == "ALLOWED"
    assert result.reasons == []


def test_price_exactly_at_cap_is_allowed():
    """Price == cap edge case: must be allowed."""
    result = evaluate_proposal(
        make_policy(max_per_order_cents=2999),
        make_product(price_cents=2999),
    )
    assert result.allowed


def test_price_equals_remaining_budget_is_allowed():
    """Spend + price == total_budget: still allowed (not over)."""
    result = evaluate_proposal(
        make_policy(total_budget_cents=2999, successful_spend_cents=0),
        make_product(price_cents=2999),
    )
    assert result.allowed


# ── Per-order cap ─────────────────────────────────────────────────────────────

def test_price_one_cent_over_cap_is_blocked():
    result = evaluate_proposal(
        make_policy(max_per_order_cents=2999),
        make_product(price_cents=3000),
    )
    assert not result.allowed
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in result.reasons


def test_price_over_cap_gives_readable_explanation():
    result = evaluate_proposal(
        make_policy(max_per_order_cents=4000),
        make_product(price_cents=5500),
    )
    assert any("$55.00" in e or "cap" in e.lower() for e in result.explanations)


# ── Merchant allowlist ────────────────────────────────────────────────────────

def test_unapproved_merchant_is_blocked():
    result = evaluate_proposal(
        make_policy(),
        make_product(merchant_id="shadowtech"),
    )
    assert not result.allowed
    assert "MERCHANT_NOT_APPROVED" in result.reasons


def test_approved_merchant_passes():
    for mid in ["techcore", "homeplus"]:
        result = evaluate_proposal(make_policy(), make_product(merchant_id=mid))
        assert result.allowed, f"Expected {mid} to be approved"


# ── Budget exhaustion ─────────────────────────────────────────────────────────

def test_budget_exhausted_is_blocked():
    result = evaluate_proposal(
        make_policy(total_budget_cents=5000, successful_spend_cents=5000),
        make_product(price_cents=100),
    )
    assert not result.allowed
    assert "TOTAL_BUDGET_EXCEEDED" in result.reasons


def test_proposed_price_exceeds_remaining_budget():
    result = evaluate_proposal(
        make_policy(total_budget_cents=10000, successful_spend_cents=8000),
        make_product(price_cents=3000),   # $30 > $20 remaining
    )
    assert not result.allowed
    assert "TOTAL_BUDGET_EXCEEDED" in result.reasons


# ── Invalid data ──────────────────────────────────────────────────────────────

def test_zero_price_is_blocked():
    result = evaluate_proposal(make_policy(), make_product(price_cents=0))
    assert not result.allowed
    assert "NEGATIVE_OR_ZERO_PRICE" in result.reasons


def test_negative_price_is_blocked():
    result = evaluate_proposal(make_policy(), make_product(price_cents=-100))
    assert not result.allowed
    assert "NEGATIVE_OR_ZERO_PRICE" in result.reasons


def test_currency_mismatch_is_blocked():
    result = evaluate_proposal(
        make_policy(currency="USD"),
        make_product(currency="EUR"),
    )
    assert not result.allowed
    assert "INVALID_CURRENCY" in result.reasons


# ── Human approval gate ───────────────────────────────────────────────────────

def test_evaluate_without_approval_blocks_at_order_time():
    """evaluate() (used at create-order time) blocks when require_approval=True and human_approved=False."""
    result = evaluate(
        make_policy(require_approval=True),
        make_product(),
        human_approved=False,
    )
    assert not result.allowed
    assert "REQUIRES_HUMAN_APPROVAL" in result.reasons


def test_evaluate_with_approval_allows():
    result = evaluate(
        make_policy(require_approval=True),
        make_product(),
        human_approved=True,
    )
    assert result.allowed


def test_evaluate_proposal_ignores_approval_gate():
    """evaluate_proposal() should NOT block due to missing approval — that gate is only at order creation."""
    result = evaluate_proposal(
        make_policy(require_approval=True),
        make_product(),
    )
    assert result.allowed  # proposal shown as ALLOWED; user must then click Approve


# ── Multiple violations ───────────────────────────────────────────────────────

def test_multiple_violations_all_reported():
    result = evaluate_proposal(
        make_policy(max_per_order_cents=1000, approved_merchant_ids=["techcore"]),
        make_product(price_cents=5000, merchant_id="shadowtech"),
    )
    assert not result.allowed
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in result.reasons
    assert "MERCHANT_NOT_APPROVED" in result.reasons
