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


def test_blocked_over_cap_returns_allowed_alternatives(client):
    """
    Test 6: Blocked over-cap request returns up to 2 ALLOWED alternatives,
    each costing <= the per-order cap ($40.00) and from an approved merchant.
    """
    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in data["decision_reasons"]
    assert data["block_explanation"] is not None

    alternatives = data.get("alternatives", [])
    assert len(alternatives) > 0
    assert len(alternatives) <= 2

    # Fetch policy to check approved merchants & cap
    policy = client.get("/api/policy").json()
    approved_merchants = set(policy["approved_merchant_ids"])
    cap_cents = policy["max_per_order_cents"]

    for alt in alternatives:
        assert alt["policy_decision"] == "ALLOWED"
        assert alt["product"] is not None
        assert alt["product"]["price_cents"] <= cap_cents
        assert alt["product"]["merchant_id"] in approved_merchants


def test_alternatives_never_include_unapproved_merchants(client):
    """
    Test 7: Alternatives never include unapproved-merchant products (e.g. shadowtech).
    """
    res = client.post("/api/agent/propose", json={
        "user_request": "I want to buy a shadowtech gadget for my desk."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"

    policy = client.get("/api/policy").json()
    approved_merchants = set(policy["approved_merchant_ids"])

    for alt in data.get("alternatives", []):
        assert alt["product"]["merchant_id"] in approved_merchants
        assert alt["product"]["merchant_id"] != "shadowtech"


def test_ai_returned_unknown_product_id_is_ignored(client):
    """
    Test 8: An AI-returned product ID that does not exist is ignored and discarded.
    """
    from unittest.mock import patch
    from app.services.ai_service import AIProposalResult, AIRecommendation, AICandidate

    fake_result = AIProposalResult(
        recommendation=AIRecommendation(
            product_id="non-existent-ghost-item",
            rationale="Ghost item rationale",
            candidates=[
                AICandidate(product_id="non-existent-ghost-item", reason="Unknown"),
                AICandidate(product_id="another-ghost-item", reason="Also fake"),
                AICandidate(product_id="tc-wireless-mouse", reason="Real alternative"),
            ],
        ),
        ai_mode="live",
    )

    with patch("app.services.ai_service.generate_recommendation", return_value=fake_result):
        res = client.post("/api/agent/propose", json={
            "user_request": "Looking for something exotic."
        })
        assert res.status_code == 201
        data = res.json()
        # Primary was unknown product -> BLOCKED
        assert data["policy_decision"] == "BLOCKED"
        assert "UNKNOWN_PRODUCT" in data["decision_reasons"]

        # Alternatives must NOT contain the ghost IDs
        alt_ids = [alt["selected_product_id"] for alt in data.get("alternatives", [])]
        assert "non-existent-ghost-item" not in alt_ids
        assert "another-ghost-item" not in alt_ids
        # If any alternative is returned, it must be valid and ALLOWED
        for alt in data.get("alternatives", []):
            assert alt["policy_decision"] == "ALLOWED"


def test_alternative_can_proceed_to_create_order_while_primary_cannot(client):
    """
    Test 9: The alternative proposal has its own ID and can proceed to create-order,
    while the blocked primary proposal cannot.
    """
    from unittest.mock import patch

    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing."
    })
    assert res.status_code == 201
    data = res.json()
    primary_id = data["id"]
    assert data["policy_decision"] == "BLOCKED"
    alternatives = data.get("alternatives", [])
    assert len(alternatives) > 0
    alt_id = alternatives[0]["id"]
    assert alternatives[0]["policy_decision"] == "ALLOWED"

    # Primary proposal MUST be rejected at create-order
    with patch("app.config.Settings.paypal_configured", True):
        primary_order_res = client.post("/api/payments/create-order", json={
            "proposal_id": primary_id,
            "user_approved": True,
        })
        assert primary_order_res.status_code == 400
        assert "BLOCKED" in primary_order_res.json()["detail"]

    # Alternative proposal MUST succeed at create-order
    fake_order = {
        "id": "PAYPAL-ALT-ORDER-123",
        "status": "CREATED",
        "links": [{"href": "https://sandbox.paypal.com/checkoutnow?token=123", "rel": "approve"}],
    }
    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        alt_order_res = client.post("/api/payments/create-order", json={
            "proposal_id": alt_id,
            "user_approved": True,
        })
        assert alt_order_res.status_code == 201
        assert alt_order_res.json()["paypal_order_id"] == "PAYPAL-ALT-ORDER-123"


def test_fallback_mode_returns_alternatives_without_ai_key(client):
    """
    Test 10: Fallback mode returns alternatives without any AI key configured.
    """
    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing."
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ai_mode"] == "fallback"
    assert data["policy_decision"] == "BLOCKED"
    assert len(data.get("alternatives", [])) > 0
    assert data["block_explanation"] is not None


def test_alternatives_suggested_audit_event_recorded(client):
    """
    Test 11: An ALTERNATIVES_SUGGESTED audit event is recorded when alternatives are returned.
    """
    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing."
    })
    assert res.status_code == 201
    primary_id = res.json()["id"]

    audit_res = client.get("/api/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()

    alt_events = [e for e in events if e.get("event_type") == "ALTERNATIVES_SUGGESTED"]
    assert len(alt_events) >= 1
    matched = [e for e in alt_events if e.get("proposal_id") == primary_id]
    assert len(matched) == 1
    details = matched[0]["details"]
    assert details["primary_proposal_id"] == primary_id
    assert len(details["alternative_proposal_ids"]) > 0
    assert len(details["alternative_product_ids"]) > 0
