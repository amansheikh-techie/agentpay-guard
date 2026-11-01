"""
tests/test_v2_features.py — Tests for AgentPay Guard 2.0 endpoints and policy rules.
"""
from unittest.mock import patch
import pytest

from app.models import Policy, Product, Proposal, Payment


def test_agent_disabled_blocks_proposal(client, clean_test_db):
    """When agent_enabled is False, proposals are BLOCKED with AGENT_DISABLED."""
    # Update policy to disable agent
    res = client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 4000,
        "approved_merchant_ids": ["techcore"],
        "agent_enabled": False,
    })
    assert res.status_code == 200
    assert res.json()["agent_enabled"] is False

    # Propose purchase
    res = client.post("/api/agent/propose", json={
        "user_request": "Find a wireless mouse under $35 from TechCore"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "AGENT_DISABLED" in data["decision_reasons"]


def test_category_blocked_blocks_proposal(client, clean_test_db):
    """When a category is blocked, proposals in that category are BLOCKED."""
    # Block 'peripherals' category
    res = client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 4000,
        "approved_merchant_ids": ["techcore", "homeplus"],
        "blocked_categories": ["peripherals"],
    })
    assert res.status_code == 200

    # Request wireless mouse (which is in peripherals category)
    res = client.post("/api/agent/propose", json={
        "user_request": "Buy a wireless mouse"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "CATEGORY_BLOCKED" in data["decision_reasons"]


def test_daily_limit_blocks_proposal(client, clean_test_db):
    """When daily limit is set, purchases exceeding it are BLOCKED."""
    # Set daily limit to $20.00 (2000 cents), but product is $29.99
    res = client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 4000,
        "daily_limit_cents": 2000,
        "approved_merchant_ids": ["techcore"],
    })
    assert res.status_code == 200

    res = client.post("/api/agent/propose", json={
        "user_request": "Buy a wireless mouse"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["policy_decision"] == "BLOCKED"
    assert "DAILY_LIMIT_EXCEEDED" in data["decision_reasons"]


def test_get_summary_endpoint(client, clean_test_db):
    """GET /api/summary returns correct aggregations."""
    res = client.get("/api/summary")
    assert res.status_code == 200
    data = res.json()
    assert "completed_cents" in data
    assert "reserved_cents" in data
    assert "remaining_cents" in data
    assert "daily_spent_cents" in data
    assert "monthly_spent_cents" in data
    assert "blocked_count" in data
    assert "completed_count" in data
    assert "failed_count" in data
    assert "by_merchant" in data
    assert isinstance(data["by_merchant"], list)


def test_get_payments_list_endpoint(client, clean_test_db):
    """GET /api/payments returns payment list and supports status filtering."""
    res = client.get("/api/payments")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_filtered = client.get("/api/payments?status=captured")
    assert res_filtered.status_code == 200
    assert isinstance(res_filtered.json(), list)


def test_get_audit_with_event_type_filter(client, clean_test_db):
    """GET /api/audit?event_type=... filters audit logs."""
    # Create an audit event via policy update
    client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 4000,
        "approved_merchant_ids": ["techcore"],
    })

    res = client.get("/api/audit?event_type=POLICY_UPDATED")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1
    assert all(e["event_type"] == "POLICY_UPDATED" for e in events)


def test_approval_binding_mismatch_blocks_capture(client, clean_test_db):
    """If amount in approval binding doesn't match payment amount, capture fails with 409."""
    # Create proposal and payment with tampered price in binding
    proposal_res = client.post("/api/agent/propose", json={
        "user_request": "Buy a wireless mouse under $35"
    })
    assert proposal_res.status_code == 201
    prop_id = proposal_res.json()["id"]

    with patch("app.services.paypal_service.create_order") as mock_create:
        mock_create.return_value = {
            "id": "PAYPAL_ORDER_BINDING_TEST",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/checkout"}],
        }
        order_res = client.post("/api/payments/create-order", json={
            "proposal_id": prop_id,
            "user_approved": True,
            "approval_binding": {
                "product_id": "tc-wireless-mouse",
                "price_cents": 1000,  # tampered: actual product is 2999
            }
        })
        assert order_res.status_code == 201
        paypal_order_id = order_res.json()["paypal_order_id"]

    # Attempt capture -> should detect tampering and raise 409
    cap_res = client.post("/api/payments/capture-order", json={
        "paypal_order_id": paypal_order_id,
    })
    assert cap_res.status_code == 409
    assert "APPROVAL_MISMATCH" in cap_res.json()["detail"]

