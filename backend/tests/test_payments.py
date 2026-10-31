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


def test_capture_order_not_approved_keeps_pending(client, allowed_proposal):
    """When the buyer hasn't approved the order yet, capture returns a clear error
    and the payment stays 'pending' (not 'failed') so the user can retry."""
    from app.services.paypal_service import PayPalError

    fake_order = {
        "id": "PAYPAL-ORDER-NOTAPPROVED",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        create_res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert create_res.status_code == 201

    # Simulate ORDER_NOT_APPROVED: get_order_details returns CREATED status
    fake_order_details = {"id": "PAYPAL-ORDER-NOTAPPROVED", "status": "CREATED"}

    with patch("app.services.paypal_service.get_order_details", return_value=fake_order_details):
        cap_res = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-NOTAPPROVED"
        })
        assert cap_res.status_code == 400
        detail = cap_res.json()["detail"]
        assert "CREATED" in detail or "approval" in detail.lower()

    # Payment must still be "pending", not "failed" — verify via API.
    # The capture endpoint returns 400 but does NOT change status to "failed"
    # for ORDER_NOT_APPROVED, so re-capturing after approval will still work.
    # We verify this indirectly: a second capture attempt with a still-CREATED
    # status should return 400 (not 404 "Payment not found"), confirming the
    # payment record still exists with a capturable status.
    with patch("app.services.paypal_service.get_order_details", return_value=fake_order_details):
        cap_res_2 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-NOTAPPROVED"
        })
        # Should still be 400 (not 404), meaning payment is still pending
        assert cap_res_2.status_code == 400
        assert "CREATED" in cap_res_2.json()["detail"] or "approval" in cap_res_2.json()["detail"].lower()


def test_three_pending_orders_cannot_exceed_budget(client, allowed_proposal):
    """
    Budget reservation: multiple in-flight orders are counted against the budget.
    With $100 budget and $29.99 item, 3 orders = $89.97 (allowed).
    A 4th order would take spend to $119.96 > $100 budget and must be blocked.
    """
    fake_order_1 = {"id": "ORDER-1", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_2 = {"id": "ORDER-2", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_3 = {"id": "ORDER-3", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_4 = {"id": "ORDER-4", "links": [{"href": "https://approve.url", "rel": "approve"}]}

    with patch("app.config.Settings.paypal_configured", True):
        # Order 1 ($29.99): $29.99 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_1):
            res1 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res1.status_code == 201

        # Order 2 ($29.99): $59.98 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_2):
            res2 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res2.status_code == 201

        # Order 3 ($29.99): $89.97 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_3):
            res3 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res3.status_code == 201

        # Order 4 ($29.99): would be $119.96 > $100 budget -> MUST BE BLOCKED
        with patch("app.services.paypal_service.create_order", return_value=fake_order_4):
            res4 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res4.status_code == 400
            assert "remains in the total budget" in res4.json()["detail"]


def test_capture_claim_is_atomic_409_when_capturing(client, allowed_proposal):
    """
    Atomic capture claim: when a payment is already in 'capturing' state,
    a concurrent capture attempt fails with 409 Conflict.
    """
    from tests.conftest import TestSessionLocal
    from app.models import Payment

    fake_order = {
        "id": "PAYPAL-ORDER-CLAIM-ATOMIC",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        create_res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert create_res.status_code == 201

    # Simulate another worker having claimed the payment into 'capturing' state
    db = TestSessionLocal()
    try:
        p = db.query(Payment).filter(Payment.paypal_order_id == "PAYPAL-ORDER-CLAIM-ATOMIC").first()
        assert p is not None
        p.status = "capturing"
        db.commit()
    finally:
        db.close()

    # Attempt capture while in 'capturing' status
    cap_res = client.post("/api/payments/capture-order", json={
        "paypal_order_id": "PAYPAL-ORDER-CLAIM-ATOMIC"
    })
    assert cap_res.status_code == 409
    assert "currently being captured" in cap_res.json()["detail"]


def test_double_capture_deducts_once(client, allowed_proposal):
    """
    Double capture: repeated capture calls on an already-captured payment
    return the payment record without deducting from the budget a second time.
    """
    fake_order = {
        "id": "PAYPAL-ORDER-DOUBLE-CAP",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }
    fake_capture = {
        "id": "PAYPAL-ORDER-DOUBLE-CAP",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-DOUBLE-1",
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

    spend_before = client.get("/api/policy").json()["successful_spend_cents"]

    # First capture
    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap1 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-DOUBLE-CAP"
        })
        assert cap1.status_code == 200
        assert cap1.json()["status"] == "captured"

    spend_after_first = client.get("/api/policy").json()["successful_spend_cents"]
    assert spend_after_first == spend_before + 2999

    # Second capture (should be idempotent)
    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap2 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-DOUBLE-CAP"
        })
        assert cap2.status_code == 200
        assert cap2.json()["status"] == "captured"

    spend_after_second = client.get("/api/policy").json()["successful_spend_cents"]
    assert spend_after_second == spend_after_first


def test_policy_endpoints_require_admin_token_outside_development(client):
    """
    Security check: Outside of development (e.g. production/staging),
    PUT /api/policy and POST /api/policy/reset require a valid X-Admin-Token header.
    """
    from app.config import Settings

    prod_settings = Settings(
        app_env="production",
        admin_token="supersecretadmintoken123",
        paypal_client_id="id",
        paypal_client_secret="secret",
    )

    policy_payload = {
        "total_budget_cents": 8000,
        "max_per_order_cents": 3000,
        "currency": "USD",
        "approved_merchant_ids": ["techcore"],
        "require_approval": True,
    }

    with patch("app.security.get_settings", return_value=prod_settings):
        # 1. PUT /api/policy without token -> 401
        res1 = client.put("/api/policy", json=policy_payload)
        assert res1.status_code == 401
        assert "Invalid or missing X-Admin-Token" in res1.json()["detail"]

        # 2. PUT /api/policy with wrong token -> 401
        res2 = client.put(
            "/api/policy",
            json=policy_payload,
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert res2.status_code == 401

        # 3. PUT /api/policy with correct token -> 200
        res3 = client.put(
            "/api/policy",
            json=policy_payload,
            headers={"X-Admin-Token": "supersecretadmintoken123"},
        )
        assert res3.status_code == 200
        assert res3.json()["total_budget_cents"] == 8000

        # 4. POST /api/policy/reset without token -> 401
        res4 = client.post("/api/policy/reset")
        assert res4.status_code == 401

        # 5. POST /api/policy/reset with correct token -> 200
        res5 = client.post(
            "/api/policy/reset",
            headers={"X-Admin-Token": "supersecretadmintoken123"},
        )
        assert res5.status_code == 200
        assert res5.json()["total_budget_cents"] == 10000


def test_create_order_rejects_currency_mismatch_with_config(client, allowed_proposal):
    """If configured PayPal currency does not match product currency, create-order is rejected."""
    from app.config import Settings
    with patch("app.routers.payments.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            paypal_client_id="dummy-id",
            paypal_client_secret="dummy-secret",
            paypal_currency="EUR",
        )
        res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert res.status_code == 400
        assert "does not match configured PayPal currency" in res.json()["detail"]


def test_capture_order_rejects_currency_mismatch_from_paypal(client, allowed_proposal):
    """If PayPal capture returns a different currency, capture is rejected and budget is NOT touched."""
    fake_order = {
        "id": "PAYPAL-CURRENCY-MISMATCH",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }
    # Return EUR instead of USD
    eur_capture = {
        "id": "PAYPAL-CURRENCY-MISMATCH",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-EUR",
                            "status": "COMPLETED",
                            "amount": {"value": "29.99", "currency_code": "EUR"},
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

    pol_before = client.get("/api/policy").json()["successful_spend_cents"]

    with patch("app.services.paypal_service.capture_order", return_value=eur_capture):
        cap_res = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-CURRENCY-MISMATCH"
        })
        assert cap_res.status_code == 400
        assert "does not match authoritative purchase value" in cap_res.json()["detail"]

    # Budget must NOT be decremented
    pol_after = client.get("/api/policy").json()["successful_spend_cents"]
    assert pol_after == pol_before


def test_capture_order_not_approved_keeps_pending(client, allowed_proposal):
    """When the buyer hasn't approved the order yet, capture returns a clear error
    and the payment stays 'pending' (not 'failed') so the user can retry."""
    from app.services.paypal_service import PayPalError

    fake_order = {
        "id": "PAYPAL-ORDER-NOTAPPROVED",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        create_res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert create_res.status_code == 201

    # Simulate ORDER_NOT_APPROVED: get_order_details returns CREATED status
    fake_order_details = {"id": "PAYPAL-ORDER-NOTAPPROVED", "status": "CREATED"}

    with patch("app.services.paypal_service.get_order_details", return_value=fake_order_details):
        cap_res = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-NOTAPPROVED"
        })
        assert cap_res.status_code == 400
        detail = cap_res.json()["detail"]
        assert "CREATED" in detail or "approval" in detail.lower()

    # Payment must still be "pending", not "failed" — verify via API.
    # The capture endpoint returns 400 but does NOT change status to "failed"
    # for ORDER_NOT_APPROVED, so re-capturing after approval will still work.
    # We verify this indirectly: a second capture attempt with a still-CREATED
    # status should return 400 (not 404 "Payment not found"), confirming the
    # payment record still exists with a capturable status.
    with patch("app.services.paypal_service.get_order_details", return_value=fake_order_details):
        cap_res_2 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-NOTAPPROVED"
        })
        # Should still be 400 (not 404), meaning payment is still pending
        assert cap_res_2.status_code == 400
        assert "CREATED" in cap_res_2.json()["detail"] or "approval" in cap_res_2.json()["detail"].lower()


def test_three_pending_orders_cannot_exceed_budget(client, allowed_proposal):
    """
    Budget reservation: multiple in-flight orders are counted against the budget.
    With $100 budget and $29.99 item, 3 orders = $89.97 (allowed).
    A 4th order would take spend to $119.96 > $100 budget and must be blocked.
    """
    fake_order_1 = {"id": "ORDER-1", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_2 = {"id": "ORDER-2", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_3 = {"id": "ORDER-3", "links": [{"href": "https://approve.url", "rel": "approve"}]}
    fake_order_4 = {"id": "ORDER-4", "links": [{"href": "https://approve.url", "rel": "approve"}]}

    with patch("app.config.Settings.paypal_configured", True):
        # Order 1 ($29.99): $29.99 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_1):
            res1 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res1.status_code == 201

        # Order 2 ($29.99): $59.98 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_2):
            res2 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res2.status_code == 201

        # Order 3 ($29.99): $89.97 / $100 -> OK
        with patch("app.services.paypal_service.create_order", return_value=fake_order_3):
            res3 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res3.status_code == 201

        # Order 4 ($29.99): would be $119.96 > $100 budget -> MUST BE BLOCKED
        with patch("app.services.paypal_service.create_order", return_value=fake_order_4):
            res4 = client.post("/api/payments/create-order", json={
                "proposal_id": allowed_proposal["id"],
                "user_approved": True,
            })
            assert res4.status_code == 400
            assert "remains in the total budget" in res4.json()["detail"]


def test_capture_claim_is_atomic_409_when_capturing(client, allowed_proposal):
    """
    Atomic capture claim: when a payment is already in 'capturing' state,
    a concurrent capture attempt fails with 409 Conflict.
    """
    from tests.conftest import TestSessionLocal
    from app.models import Payment

    fake_order = {
        "id": "PAYPAL-ORDER-CLAIM-ATOMIC",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }

    with patch("app.config.Settings.paypal_configured", True), \
         patch("app.services.paypal_service.create_order", return_value=fake_order):
        create_res = client.post("/api/payments/create-order", json={
            "proposal_id": allowed_proposal["id"],
            "user_approved": True,
        })
        assert create_res.status_code == 201

    # Simulate another worker having claimed the payment into 'capturing' state
    db = TestSessionLocal()
    try:
        p = db.query(Payment).filter(Payment.paypal_order_id == "PAYPAL-ORDER-CLAIM-ATOMIC").first()
        assert p is not None
        p.status = "capturing"
        db.commit()
    finally:
        db.close()

    # Attempt capture while in 'capturing' status
    cap_res = client.post("/api/payments/capture-order", json={
        "paypal_order_id": "PAYPAL-ORDER-CLAIM-ATOMIC"
    })
    assert cap_res.status_code == 409
    assert "currently being captured" in cap_res.json()["detail"]


def test_double_capture_deducts_once(client, allowed_proposal):
    """
    Double capture: repeated capture calls on an already-captured payment
    return the payment record without deducting from the budget a second time.
    """
    fake_order = {
        "id": "PAYPAL-ORDER-DOUBLE-CAP",
        "links": [{"href": "https://approve.url", "rel": "approve"}],
    }
    fake_capture = {
        "id": "PAYPAL-ORDER-DOUBLE-CAP",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-DOUBLE-1",
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

    spend_before = client.get("/api/policy").json()["successful_spend_cents"]

    # First capture
    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap1 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-DOUBLE-CAP"
        })
        assert cap1.status_code == 200
        assert cap1.json()["status"] == "captured"

    spend_after_first = client.get("/api/policy").json()["successful_spend_cents"]
    assert spend_after_first == spend_before + 2999

    # Second capture (should be idempotent)
    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap2 = client.post("/api/payments/capture-order", json={
            "paypal_order_id": "PAYPAL-ORDER-DOUBLE-CAP"
        })
        assert cap2.status_code == 200
        assert cap2.json()["status"] == "captured"

    spend_after_second = client.get("/api/policy").json()["successful_spend_cents"]
    assert spend_after_second == spend_after_first


def test_policy_endpoints_require_admin_token_outside_development(client):
    """
    Security check: Outside of development (e.g. production/staging),
    PUT /api/policy and POST /api/policy/reset require a valid X-Admin-Token header.
    """
    from app.config import Settings

    prod_settings = Settings(
        app_env="production",
        admin_token="supersecretadmintoken123",
        paypal_client_id="id",
        paypal_client_secret="secret",
    )

    policy_payload = {
        "total_budget_cents": 8000,
        "max_per_order_cents": 3000,
        "currency": "USD",
        "approved_merchant_ids": ["techcore"],
        "require_approval": True,
    }

    with patch("app.security.get_settings", return_value=prod_settings):
        # 1. PUT /api/policy without token -> 401
        res1 = client.put("/api/policy", json=policy_payload)
        assert res1.status_code == 401
        assert "Invalid or missing X-Admin-Token" in res1.json()["detail"]

        # 2. PUT /api/policy with wrong token -> 401
        res2 = client.put(
            "/api/policy",
            json=policy_payload,
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert res2.status_code == 401

        # 3. PUT /api/policy with correct token -> 200
        res3 = client.put(
            "/api/policy",
            json=policy_payload,
            headers={"X-Admin-Token": "supersecretadmintoken123"},
        )
        assert res3.status_code == 200
        assert res3.json()["total_budget_cents"] == 8000

        # 4. POST /api/policy/reset without token -> 401
        res4 = client.post("/api/policy/reset")
        assert res4.status_code == 401

        # 5. POST /api/policy/reset with correct token -> 200
        res5 = client.post(
            "/api/policy/reset",
            headers={"X-Admin-Token": "supersecretadmintoken123"},
        )
        assert res5.status_code == 200
        assert res5.json()["total_budget_cents"] == 10000
