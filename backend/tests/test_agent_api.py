"""
tests/test_agent_api.py — Integration tests for POST /api/agent/propose.

Validates that:
1. Valid shopping request returns proposal with policy evaluation.
2. An allowed proposal yields ALLOWED verdict with authoritative catalogue price.
3. Over-limit product recommendations are blocked with MAX_ORDER_AMOUNT_EXCEEDED.
4. Recommendations from unapproved merchants are blocked with MERCHANT_NOT_APPROVED.
5. In the absence of an LLM API key, fallback mode is clearly indicated.
6. Proposals are audited in the audit log.
7. Input validation rejects empty/too-short requests.
"""
import pytest


def test_propose_allowed_product(client):
    """Scenario A: Wireless mouse under $35 from approved merchant (TechCore) is ALLOWED."""
    res = client.post("/api/agent/propose", json={
        "user_request": "Find a wireless mouse for work, under $35, from an approved merchant."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["id"].startswith("prop_")
    assert data["policy_decision"] == "ALLOWED"
    assert data["decision_reasons"] == []
    assert data["product"] is not None
    assert data["product"]["id"] == "tc-wireless-mouse"
    assert data["product"]["price_cents"] == 2999  # $29.99
    assert data["ai_mode"] in ("live", "fallback")


def test_propose_blocked_over_order_cap(client):
    """Scenario B: Mechanical keyboard ($79.99) exceeds default $40 per-order cap -> BLOCKED."""
    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in data["decision_reasons"]
    assert any("per-order cap" in exp for exp in data["decision_explanations"])
    assert data["product"]["price_cents"] == 7999  # $79.99


def test_propose_blocked_unapproved_merchant(client):
    """Scenario C: Product from ShadowTech (not in approved list) -> BLOCKED."""
    res = client.post("/api/agent/propose", json={
        "user_request": "I want to buy a shadowtech gadget for my desk."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "MERCHANT_NOT_APPROVED" in data["decision_reasons"]
    assert any("approved merchant list" in exp for exp in data["decision_explanations"])


def test_propose_fallback_mode_label(client):
    """When no LLM API key is configured, fallback mode is clearly labelled."""
    res = client.post("/api/agent/propose", json={
        "user_request": "Recommend a good desk lamp with USB charging."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ai_mode"] == "fallback"
    assert "[Demo Fallback Mode" in data["rationale"]


def test_propose_records_audit_event(client):
    """Creating a proposal writes an audit event with details."""
    res = client.post("/api/agent/propose", json={
        "user_request": "Find a wireless mouse under $35"
    })
    assert res.status_code == 201
    prop_id = res.json()["id"]

    audit_res = client.get("/api/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()
    proposal_events = [e for e in events if e.get("proposal_id") == prop_id]
    assert len(proposal_events) >= 1
    assert proposal_events[0]["event_type"] == "PROPOSAL_CREATED"


def test_propose_rejects_empty_request(client):
    """Validation rejects empty or whitespace-only requests."""
    res = client.post("/api/agent/propose", json={"user_request": "   "})
    assert res.status_code == 422


def test_reset_policy_endpoint(client):
    """POST /api/policy/reset restores default policy and clears spend."""
    # First modify policy
    client.put("/api/policy", json={
        "total_budget_cents": 5000,
        "max_per_order_cents": 2000,
        "currency": "USD",
        "approved_merchant_ids": ["techcore"],
        "require_approval": True,
    })

    # Call reset
    reset_res = client.post("/api/policy/reset")
    assert reset_res.status_code == 200
    data = reset_res.json()
    assert data["total_budget_cents"] == 10000
    assert data["max_per_order_cents"] == 4000
    assert data["successful_spend_cents"] == 0
    assert "homeplus" in data["approved_merchant_ids"]
