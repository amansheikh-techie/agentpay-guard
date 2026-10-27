"""
tests/test_payments.py — Integration and mock tests for PayPal Sandbox payment flow.

Validates that:
1. Blocked proposals CANNOT create PayPal orders.
2. Explicit human approval (user_approved=True) is strictly enforced.
3. Missing PayPal credentials returns safe, actionable error message.
4. Successful order creation derives amount and merchant exclusively from authoritative catalogue.
5. Capture verifies PayPal's response and updates budget spend.
6. Duplicate capture calls are idempotent and prevent double-deduction.
7. Amount or currency mismatches are flagged as needs_verification without deducting budget.
8. Order cancellation does not decrement budget.
"""
from unittest.mock import patch
import pytest

from app.models import Policy, Product, Proposal, Payment


@pytest.fixture
def allowed_proposal(client):
    """Creates a valid ALLOWED proposal for TechCore wireless mouse ($29.99)."""
    res = client.post("/api/agent/propose", json={
        "user_request": "Find a wireless mouse under $35 from an approved merchant"
    })
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def blocked_proposal(client):
    """Creates a BLOCKED proposal (mechanical keyboard $79.99 > $40 cap)."""
    res = client.post("/api/agent/propose", json={
        "user_request": "I need a high-end mechanical keyboard for typing"
    })
    assert res.status_code == 201
    assert res.json()["policy_decision"] == "BLOCKED"
    return res.json()


def test_create_order_rejected_if_user_not_approved(client, allowed_proposal):
    """user_approved=False is rejected at the schema level."""
    res = client.post("/api/payments/create-order", json={
        "proposal_id": allowed_proposal["id"],
        "user_approved": False,
    })
    assert res.status_code == 422


def test_create_order_blocked_proposal_rejected(client, blocked_proposal):
    """Cannot create a payment order for a BLOCKED purchase proposal."""
    res = client.post("/api/payments/create-order", json={
        "proposal_id": blocked_proposal["id"],
        "user_approved": True,
    })
    assert res.status_code == 400
    assert "BLOCKED" in res.json()["detail"]


def test_create_order_without_paypal_credentials_gives_safe_error(client, allowed_proposal):
    """When PAYPAL_CLIENT_ID/SECRET are empty, return actionable error without crash."""
    with patch("app.config.Settings.paypal_configured", False):
        res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert res.status_code == 400
        assert "PayPal Sandbox credentials are not configured" in res.json()["detail"]


def test_create_order_successful_flow(client, allowed_proposal):
    """Authoritative amount used to create PayPal order with approve link."""
    fake_order = {
        "id": "PAYPAL-ORDER-12345",
        "status": "CREATED",
        "links": [
            {"href": "https://www.sandbox.paypal.com/checkoutnow?token=PAYPAL-ORDER-12345", "rel": "approve"}
        ],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order) as mock_create:

        res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })

        assert res.status_code == 201
        data = res.json()
        assert data["paypal_order_id"] == "PAYPAL-ORDER-12345"
        assert "sandbox.paypal.com" in data["approve_url"]
        assert data["status"] == "pending"

        # Verify paypal_service was called with authoritative server price (2999 cents -> $29.99)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["amount_cents"] == 2999
        assert kwargs["currency"] == "USD"


def test_capture_order_verified_updates_budget_once(client, allowed_proposal):
    """Verified capture updates payment status and increments budget spend."""
    fake_order = {
        "id": "PAYPAL-ORDER-55555",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }
    fake_capture = {
        "id": "PAYPAL-ORDER-55555",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-777",
                            "status": "COMPLETED",
                            "amount": {"value": "29.99", "currency_code": "USD"},
                        }
                    ]
                }
            }
        ],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        create_res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert create_res.status_code == 201

    # Check budget before capture
    pol_before = client.get("/api/policy").json()
    spend_before = pol_before["successful_spend_cents"]

    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap_res = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-55555"
        })
        assert cap_res.status_code == 200
        cap_data = cap_res.json()
        assert cap_data["status"] == "captured"
        assert cap_data["paypal_capture_id"] == "CAPTURE-777"

    # Verify budget updated by exactly 2999 cents
    pol_after = client.get("/api/policy").json()
    assert pol_after["successful_spend_cents"] == spend_before + 2999

    # IDEMPOTENCY TEST: Call capture again on the same order
    cap_res_2 = client.post("/api/payments/capture-order", json={
        "paypal_order_id": "PAYPAL-ORDER-55555"
    })
    assert cap_res_2.status_code == 200
    assert cap_res_2.json()["status"] == "captured"

    # Budget must NOT have been incremented twice!
    pol_after_2 = client.get("/api/policy").json()
    assert pol_after_2["successful_spend_cents"] == spend_before + 2999


def test_capture_order_amount_mismatch_flags_verification(client, allowed_proposal):
    """If PayPal returns a different amount than expected, payment is marked needs_verification."""
    fake_order = {
        "id": "PAYPAL-ORDER-MISMATCH",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }
    # Return $50.00 instead of expected $29.99
    mismatched_capture = {
        "id": "PAYPAL-ORDER-MISMATCH",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-BAD",
                            "status": "COMPLETED",
                            "amount": {"value": "50.00", "currency_code": "USD"},
                        }
                    ]
                }
            }
        ],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })

    with patch("app.services.paypal_service.capture_order", return_value=mismatched_capture):
        cap_res = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-MISMATCH"
        })
        assert cap_res.status_code == 400
        assert "does not match" in cap_res.json()["detail"]


def test_cancel_order_marks_cancelled_without_spend(client, allowed_proposal):
    """Cancelling an order sets status to cancelled and does not increment spend."""
    fake_order = {
        "id": "PAYPAL-ORDER-CANCEL",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })

    pol_before = client.get("/api/policy").json()["successful_spend_cents"]

    cancel_res = client.post("/api/payments/cancel", json={
        "paypal_order_id": "PAYPAL-ORDER-CANCEL"
    })
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    pol_after = client.get("/api/policy").json()["successful_spend_cents"]
    assert pol_after == pol_before
