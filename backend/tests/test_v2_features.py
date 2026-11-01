"""
tests/test_v2_features.py — Tests for AgentPay Guard 2.0 endpoints and policy rules.
"""
from unittest.mock import patch
import pytest

from app.models import Policy, Product, Proposal, Payment
from tests.conftest import TestSessionLocal


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
    assert "APPROVAL_MISMATCH" in str(cap_res.json()["detail"])


def test_approval_mismatch_price_merchant_currency(client, clean_test_db):
    """
    Capture rejects with 409 APPROVAL_MISMATCH when product price, merchant,
    or currency changed after order creation, with the payment status unchanged
    and PayPal not called.
    """
    db = TestSessionLocal()
    try:
        # 1. Price changed after order creation
        prop_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
        prop_id = prop_res.json()["id"]

        with patch("app.services.paypal_service.create_order") as mock_create:
            mock_create.return_value = {
                "id": "PAYPAL_PRICE_CHANGE",
                "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
            }
            order_res = client.post("/api/payments/create-order", json={"proposal_id": prop_id, "user_approved": True})
            paypal_order_id = order_res.json()["paypal_order_id"]

        prod = db.query(Product).filter(Product.id == "tc-wireless-mouse").first()
        orig_price = prod.price_cents
        prod.price_cents = 3999
        db.commit()

        with patch("app.services.paypal_service.capture_order") as mock_capture:
            cap_res = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id})
            assert cap_res.status_code == 409
            data = cap_res.json()
            assert data["detail"]["code"] == "APPROVAL_MISMATCH"
            mock_capture.assert_not_called()

            # Verify payment status in DB is unchanged (still pending)
            pay = db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id).first()
            assert pay.status == "pending"

        # Restore product price
        prod.price_cents = orig_price
        db.commit()

        # 2. Merchant changed after order creation
        with patch("app.services.paypal_service.create_order") as mock_create:
            mock_create.return_value = {
                "id": "PAYPAL_MERCHANT_CHANGE",
                "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
            }
            order_res2 = client.post("/api/payments/create-order", json={"proposal_id": prop_id, "user_approved": True})
            paypal_order_id2 = order_res2.json()["paypal_order_id"]

        orig_merchant = prod.merchant_id
        prod.merchant_id = "unapproved_merchant_id"
        db.commit()

        with patch("app.services.paypal_service.capture_order") as mock_capture:
            cap_res2 = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id2})
            assert cap_res2.status_code == 409
            assert cap_res2.json()["detail"]["code"] == "APPROVAL_MISMATCH"
            mock_capture.assert_not_called()

            pay2 = db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id2).first()
            assert pay2.status == "pending"

        prod.merchant_id = orig_merchant
        db.commit()

        # 3. Currency changed after order creation
        with patch("app.services.paypal_service.create_order") as mock_create:
            mock_create.return_value = {
                "id": "PAYPAL_CURRENCY_CHANGE",
                "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
            }
            order_res3 = client.post("/api/payments/create-order", json={"proposal_id": prop_id, "user_approved": True})
            paypal_order_id3 = order_res3.json()["paypal_order_id"]

        pay3 = db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id3).first()
        pay3.currency = "EUR"
        db.commit()

        with patch("app.services.paypal_service.capture_order") as mock_capture:
            cap_res3 = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id3})
            assert cap_res3.status_code == 409
            assert cap_res3.json()["detail"]["code"] == "APPROVAL_MISMATCH"
            mock_capture.assert_not_called()

            pay3_ref = db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id3).first()
            assert pay3_ref.status == "pending"
    finally:
        db.close()


def test_capture_succeeds_for_empty_binding(client, clean_test_db):
    """Capture still succeeds for a payment whose approval_binding is empty."""
    db = TestSessionLocal()
    try:
        prop_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
        prop_id = prop_res.json()["id"]

        with patch("app.services.paypal_service.create_order") as mock_create:
            mock_create.return_value = {
                "id": "PAYPAL_EMPTY_BINDING",
                "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
            }
            order_res = client.post("/api/payments/create-order", json={"proposal_id": prop_id, "user_approved": True})
            paypal_order_id = order_res.json()["paypal_order_id"]

        # Emulate old payment with empty approval_binding
        pay = db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id).first()
        pay._approval_binding = "{}"
        db.commit()

        fake_capture = {
            "id": paypal_order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "CAPTURE-EMPTY-BIND",
                                "status": "COMPLETED",
                                "amount": {"value": "29.99", "currency_code": "USD"},
                            }
                        ]
                    }
                }
            ],
        }

        with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
            cap_res = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id})
            assert cap_res.status_code == 200
            assert cap_res.json()["status"] == "captured"
    finally:
        db.close()


def test_capture_after_policy_edit(client, clean_test_db):
    """
    Normal create-order then capture still succeeds after a policy edit that keeps
    the purchase allowed; it is rejected if the edit makes it blocked.
    """
    # 1. Policy edit keeps allowed -> capture succeeds
    prop_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    prop_id = prop_res.json()["id"]

    with patch("app.services.paypal_service.create_order") as mock_create:
        mock_create.return_value = {
            "id": "PAYPAL_POLICY_ALLOW",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
        }
        order_res = client.post("/api/payments/create-order", json={"proposal_id": prop_id, "user_approved": True})
        paypal_order_id = order_res.json()["paypal_order_id"]

    # Raise budget -> policy version increments, but mouse is still allowed
    edit_res = client.put("/api/policy", json={
        "total_budget_cents": 20000,
        "max_per_order_cents": 5000,
        "approved_merchant_ids": ["techcore"],
    })
    assert edit_res.status_code == 200

    fake_capture = {
        "id": paypal_order_id,
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-ALLOW",
                            "status": "COMPLETED",
                            "amount": {"value": "29.99", "currency_code": "USD"},
                        }
                    ]
                }
            }
        ],
    }
    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap_res = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id})
        assert cap_res.status_code == 200
        assert cap_res.json()["status"] == "captured"

    # 2. Policy edit makes purchase blocked -> capture is rejected
    prop_res2 = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    prop_id2 = prop_res2.json()["id"]

    with patch("app.services.paypal_service.create_order") as mock_create:
        mock_create.return_value = {
            "id": "PAYPAL_POLICY_BLOCK",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
        }
        order_res2 = client.post("/api/payments/create-order", json={"proposal_id": prop_id2, "user_approved": True})
        paypal_order_id2 = order_res2.json()["paypal_order_id"]

    # Lower cap to $15.00 -> $29.99 mouse is now BLOCKED
    edit_res2 = client.put("/api/policy", json={
        "total_budget_cents": 20000,
        "max_per_order_cents": 1500,
        "approved_merchant_ids": ["techcore"],
    })
    assert edit_res2.status_code == 200

    with patch("app.services.paypal_service.capture_order") as mock_capture:
        cap_res2 = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id2})
        assert cap_res2.status_code == 409
        assert cap_res2.json()["detail"]["code"] == "APPROVAL_MISMATCH"
        mock_capture.assert_not_called()


def test_monthly_limit_and_pending_reservations(client, clean_test_db):
    """
    Monthly limit blocks a proposal; daily and monthly limits count pending reserved orders
    (two pending orders cannot both pass a daily limit).
    """
    # 1. Monthly limit blocks proposal
    client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 5000,
        "monthly_limit_cents": 2000,
        "approved_merchant_ids": ["techcore"],
    })

    prop_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    assert prop_res.status_code == 201
    assert prop_res.json()["policy_decision"] == "BLOCKED"
    assert "MONTHLY_LIMIT_EXCEEDED" in prop_res.json()["decision_reasons"]

    # 2. Daily limit counts pending reserved orders
    client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 5000,
        "daily_limit_cents": 5000,  # $50.00 daily limit
        "monthly_limit_cents": 0,
        "approved_merchant_ids": ["techcore"],
    })

    # First proposal for $29.99 mouse is ALLOWED
    prop1 = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    assert prop1.status_code == 201
    assert prop1.json()["policy_decision"] == "ALLOWED"

    # Create order for first proposal -> creates pending order reservation for $29.99
    with patch("app.services.paypal_service.create_order") as mock_create:
        mock_create.return_value = {
            "id": "PAYPAL_DAILY_PENDING_1",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com"}],
        }
        order1 = client.post("/api/payments/create-order", json={"proposal_id": prop1.json()["id"], "user_approved": True})
        assert order1.status_code == 201

    # Second proposal for $29.99 mouse: $29.99 reserved + $29.99 proposed = $59.98 > $50.00
    prop2 = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    assert prop2.status_code == 201
    assert prop2.json()["policy_decision"] == "BLOCKED"
    assert "DAILY_LIMIT_EXCEEDED" in prop2.json()["decision_reasons"]


def test_run_sqlite_migrations_on_old_schema():
    """
    run_sqlite_migrations on a temporary database with the OLD schema adds the columns,
    keeps existing rows, and is safe to run twice.
    """
    from sqlalchemy import create_engine, text, inspect
    from app.database import run_sqlite_migrations

    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE policies (
                id VARCHAR(64) PRIMARY KEY,
                total_budget_cents INTEGER NOT NULL,
                max_per_order_cents INTEGER NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                require_approval BOOLEAN NOT NULL DEFAULT 1,
                successful_spend_cents INTEGER NOT NULL DEFAULT 0,
                approved_merchants TEXT NOT NULL DEFAULT '[]'
            );
        """))
        conn.execute(text("""
            INSERT INTO policies (id, total_budget_cents, max_per_order_cents, currency, require_approval, successful_spend_cents)
            VALUES ('policy_default', 10000, 4000, 'USD', 1, 1500);
        """))

        conn.execute(text("""
            CREATE TABLE products (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                price_cents INTEGER NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                merchant_id VARCHAR(64) NOT NULL,
                merchant_name VARCHAR(200) NOT NULL
            );
        """))
        conn.execute(text("""
            INSERT INTO products (id, name, price_cents, currency, merchant_id, merchant_name)
            VALUES ('prod-old', 'Old Product', 2500, 'USD', 'techcore', 'TechCore');
        """))

        conn.execute(text("""
            CREATE TABLE payments (
                id VARCHAR(64) PRIMARY KEY,
                proposal_id VARCHAR(64) NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                status VARCHAR(32) NOT NULL DEFAULT 'pending'
            );
        """))
        conn.execute(text("""
            INSERT INTO payments (id, proposal_id, amount_cents, currency, status)
            VALUES ('pay-old', 'prop-1', 2500, 'USD', 'pending');
        """))

    # First migration run
    run_sqlite_migrations(engine)

    with engine.connect() as conn:
        insp = inspect(conn)
        policy_cols = {c["name"]: c for c in insp.get_columns("policies")}
        assert "daily_limit_cents" in policy_cols
        assert "monthly_limit_cents" in policy_cols
        assert "blocked_categories" in policy_cols
        assert "agent_enabled" in policy_cols
        assert "policy_version" in policy_cols
        assert "last_reset_at" in policy_cols

        product_cols = {c["name"] for c in insp.get_columns("products")}
        assert "category" in product_cols

        payment_cols = {c["name"] for c in insp.get_columns("payments")}
        assert "approval_binding" in payment_cols

        pol = conn.execute(text("SELECT total_budget_cents, daily_limit_cents, agent_enabled, policy_version, last_reset_at FROM policies WHERE id='policy_default'")).fetchone()
        assert pol[0] == 10000
        assert pol[1] == 0
        assert pol[2] == 1
        assert pol[3] == 1
        assert pol[4] is None

        prod = conn.execute(text("SELECT id, category FROM products WHERE id='prod-old'")).fetchone()
        assert prod[0] == 'prod-old'
        assert prod[1] == 'peripherals'

        pay = conn.execute(text("SELECT id, approval_binding FROM payments WHERE id='pay-old'")).fetchone()
        assert pay[0] == 'pay-old'
        assert pay[1] == '{}'

    # Second migration run (confirm idempotency and safe to run twice)
    run_sqlite_migrations(engine)


def test_ai_extraction_validation(monkeypatch):
    """
    AI extraction:
    - valid JSON is used
    - invalid category is discarded
    - invalid JSON falls back to keywords
    """
    from app.services import ai_service
    from app.routers.agent import _extract_requirements

    valid_cats = ["peripherals", "office", "audio", "gadgets"]

    # 1. Valid JSON is used
    monkeypatch.setattr(
        ai_service,
        "extract_requirements_from_ai",
        lambda req, cats: {"category": "audio", "max_price_cents": 4500, "features": ["Bluetooth", "ANC"]},
    )
    res1 = _extract_requirements("Need headphones under $50", valid_categories=valid_cats, ai_mode="live")
    assert res1.category == "audio"
    assert res1.max_price_cents == 4500
    assert res1.features == ["Bluetooth", "ANC"]

    # 2. Invalid category is discarded
    val = ai_service.validate_extracted_requirements(
        {"category": "spaceships", "max_price_cents": 3000, "features": ["Fast"]},
        set(valid_cats),
    )
    assert val["category"] is None
    assert val["max_price_cents"] == 3000
    assert val["features"] == ["Fast"]

    # 3. Invalid JSON falls back to keywords
    monkeypatch.setattr(
        ai_service,
        "extract_requirements_from_ai",
        lambda req, cats: None,
    )
    res3 = _extract_requirements("Looking for a wireless mouse under $30", valid_categories=valid_cats, ai_mode="live")
    assert res3.category == "peripherals"
    assert res3.max_price_cents == 3000
    assert "Wireless" in res3.features


def test_reset_demo_and_summary_invariant(client, clean_test_db):
    """
    Test demo reset behavior and invariant:
    1. Invariant: GET /api/summary completed_cents == policy.successful_spend_cents after capture.
    2. Reset sets last_reset_at, clears successful_spend_cents, preserves payments, proposals, and audit events.
    3. Invariant: GET /api/summary completed_cents == policy.successful_spend_cents (both 0) after reset.
    4. Daily limit no longer counts pre-reset payments.
    5. Audit trail still contains earlier events.
    6. New purchase after reset works normally.
    """
    # 1. Create a proposal and capture an order ($29.99 = 2999 cents)
    prop_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    assert prop_res.status_code == 201
    prop_id = prop_res.json()["id"]

    with patch("app.services.paypal_service.create_order") as mock_create:
        mock_create.return_value = {
            "id": "PAYPAL_RESET_TEST_1",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/checkout"}],
        }
        order_res = client.post("/api/payments/create-order", json={
            "proposal_id": prop_id,
            "user_approved": True,
            "approval_binding": {
                "product_id": "tc-wireless-mouse",
                "price_cents": 2999,
                "merchant_id": "techcore",
                "currency": "USD",
                "policy_version": 1,
            }
        })
        assert order_res.status_code == 201
        paypal_order_id = order_res.json()["paypal_order_id"]

    fake_capture = {
        "id": paypal_order_id,
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-RESET-1",
                            "status": "COMPLETED",
                            "amount": {"value": "29.99", "currency_code": "USD"},
                        }
                    ]
                }
            }
        ],
    }

    with patch("app.services.paypal_service.capture_order", return_value=fake_capture):
        cap_res = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id})
        assert cap_res.status_code == 200

    # Invariant check after capture
    summary_after_cap = client.get("/api/summary").json()
    policy_after_cap = client.get("/api/policy").json()
    assert summary_after_cap["completed_cents"] == policy_after_cap["successful_spend_cents"] == 2999
    assert summary_after_cap["completed_count"] == 1

    # Transactions list shows 1 captured payment
    tx_res = client.get("/api/payments")
    assert len(tx_res.json()) == 1

    # Daily spend counts 2999
    assert summary_after_cap["daily_spent_cents"] == 2999

    # 2. POST /api/policy/reset
    reset_res = client.post("/api/policy/reset")
    assert reset_res.status_code == 200
    reset_policy = reset_res.json()
    assert reset_policy["successful_spend_cents"] == 0
    assert reset_policy["last_reset_at"] is not None

    # Invariant check after reset
    summary_after_reset = client.get("/api/summary").json()
    policy_after_reset = client.get("/api/policy").json()
    assert summary_after_reset["completed_cents"] == policy_after_reset["successful_spend_cents"] == 0
    assert summary_after_reset["completed_count"] == 0
    assert summary_after_reset["daily_spent_cents"] == 0

    # Transactions list filtered by last_reset_at shows 0
    tx_after_reset = client.get("/api/payments")
    assert len(tx_after_reset.json()) == 0

    # Historical Payment and Proposal rows were NOT deleted
    db = TestSessionLocal()
    assert db.query(Payment).count() == 1
    assert db.query(Proposal).count() == 1
    db.close()

    # 3. Audit trail still contains earlier events plus DEMO_RESET
    audit_res = client.get("/api/audit")
    event_types = [e["event_type"] for e in audit_res.json()]
    assert "PAYMENT_CAPTURED" in event_types
    assert "DEMO_RESET" in event_types

    # 4. Daily limit check: set daily limit to $30.00 (3000 cents).
    # Since pre-reset payment is excluded, proposing $29.99 mouse now succeeds (ALLOWED) instead of DAILY_LIMIT_EXCEEDED!
    client.put("/api/policy", json={
        "total_budget_cents": 10000,
        "max_per_order_cents": 4000,
        "daily_limit_cents": 3000,
        "approved_merchant_ids": ["techcore"],
    })
    prop2_res = client.post("/api/agent/propose", json={"user_request": "Buy a wireless mouse"})
    assert prop2_res.status_code == 201
    assert prop2_res.json()["policy_decision"] == "ALLOWED"

    # 5. New purchase after reset works normally
    prop2_id = prop2_res.json()["id"]
    with patch("app.services.paypal_service.create_order") as mock_create2:
        mock_create2.return_value = {
            "id": "PAYPAL_RESET_TEST_2",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/checkout"}],
        }
        order2_res = client.post("/api/payments/create-order", json={
            "proposal_id": prop2_id,
            "user_approved": True,
            "approval_binding": {
                "product_id": "tc-wireless-mouse",
                "price_cents": 2999,
                "merchant_id": "techcore",
                "currency": "USD",
                "policy_version": 2,
            }
        })
        assert order2_res.status_code == 201
        paypal_order_id_2 = order2_res.json()["paypal_order_id"]

    fake_capture2 = {
        "id": paypal_order_id_2,
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-RESET-2",
                            "status": "COMPLETED",
                            "amount": {"value": "29.99", "currency_code": "USD"},
                        }
                    ]
                }
            }
        ],
    }

    with patch("app.services.paypal_service.capture_order", return_value=fake_capture2):
        cap2_res = client.post("/api/payments/capture-order", json={"paypal_order_id": paypal_order_id_2})
        assert cap2_res.status_code == 200

    summary_after_new = client.get("/api/summary").json()
    policy_after_new = client.get("/api/policy").json()
    assert summary_after_new["completed_cents"] == policy_after_new["successful_spend_cents"] == 2999
    assert summary_after_new["completed_count"] == 1


# ==============================================================================
# AI Provider Adapter Tests (Gemini, OpenAI, Fallback, Validation)
# ==============================================================================

def test_gemini_provider_uses_gemini_base_url():
    """Verify AI adapter uses Gemini base URL and default model when ai_provider is 'gemini'."""
    from app.config import Settings
    from app.services.ai_service import generate_recommendation
    import json
    from unittest.mock import MagicMock

    gemini_settings = Settings(
        ai_provider="gemini",
        ai_api_key="test-gemini-key",
        ai_base_url="",
        ai_model="",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless", "usb"]},
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "product_id": "tc-wireless-mouse",
                        "rationale": "High quality wireless mouse",
                        "matched_requirements": ["wireless"],
                        "unmet_requirements": [],
                        "confidence_note": "Great match",
                        "candidates": [{"product_id": "tc-wireless-mouse", "reason": "Exact fit"}]
                    })
                }
            }
        ]
    }

    with patch("app.services.ai_service.get_settings", return_value=gemini_settings), \
         patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = generate_recommendation("Buy a wireless mouse", catalogue)

        assert mock_post.called
        call_url = mock_post.call_args[0][0]
        call_headers = mock_post.call_args[1]["headers"]
        call_json = mock_post.call_args[1]["json"]

        # 1. Base URL is the Google Gemini OpenAI-compatible completions endpoint
        assert call_url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        assert call_headers["Authorization"] == "Bearer test-gemini-key"
        assert call_json["model"] == "gemini-2.5-flash"
        assert result.ai_mode == "live"
        assert result.recommendation.product_id == "tc-wireless-mouse"


def test_openai_provider_keeps_openai_base_url():
    """Verify AI adapter uses OpenAI v1 base URL and default model when ai_provider is 'openai'."""
    from app.config import Settings
    from app.services.ai_service import generate_recommendation
    import json
    from unittest.mock import MagicMock

    openai_settings = Settings(
        ai_provider="openai",
        ai_api_key="test-openai-key",
        ai_base_url="",
        ai_model="",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "product_id": "tc-wireless-mouse",
                        "rationale": "High quality mouse",
                        "matched_requirements": ["wireless"],
                        "unmet_requirements": [],
                        "confidence_note": "Great match",
                        "candidates": [{"product_id": "tc-wireless-mouse", "reason": "Best match"}]
                    })
                }
            }
        ]
    }

    with patch("app.services.ai_service.get_settings", return_value=openai_settings), \
         patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = generate_recommendation("Buy a wireless mouse", catalogue)

        assert mock_post.called
        call_url = mock_post.call_args[0][0]
        call_headers = mock_post.call_args[1]["headers"]
        call_json = mock_post.call_args[1]["json"]

        # Base URL is OpenAI's v1 completions endpoint
        assert call_url == "https://api.openai.com/v1/chat/completions"
        assert call_headers["Authorization"] == "Bearer test-openai-key"
        assert call_json["model"] == "gpt-4o-mini"
        assert result.ai_mode == "live"
        assert result.recommendation.product_id == "tc-wireless-mouse"


def test_endpoint_rejecting_response_format_falls_back_cleanly():
    """
    If endpoint rejects response_format (HTTP 400),
    adapter retries without response_format and successfully parses response
    (including markdown code fences).
    """
    from app.config import Settings
    from app.services.ai_service import generate_recommendation
    import json
    from unittest.mock import MagicMock

    settings = Settings(
        ai_provider="gemini",
        ai_api_key="test-key",
        ai_base_url="",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    # First call fails with 400 (rejected response_format)
    resp_400 = MagicMock()
    resp_400.status_code = 400

    # Second call succeeds and returns markdown-fenced JSON
    resp_200 = MagicMock()
    resp_200.status_code = 200
    markdown_content = "```json\n" + json.dumps({
        "product_id": "tc-wireless-mouse",
        "rationale": "Markdown formatted JSON match",
        "matched_requirements": ["wireless"],
        "unmet_requirements": [],
        "confidence_note": "Clean retry",
        "candidates": [{"product_id": "tc-wireless-mouse", "reason": "Matched"}]
    }) + "\n```"
    resp_200.json.return_value = {
        "choices": [{"message": {"content": markdown_content}}]
    }

    with patch("app.services.ai_service.get_settings", return_value=settings), \
         patch("httpx.Client.post", side_effect=[resp_400, resp_200]) as mock_post:
        result = generate_recommendation("Buy a mouse", catalogue)

        assert mock_post.call_count == 2
        # First call attempted response_format
        assert "response_format" in mock_post.call_args_list[0][1]["json"]
        # Second call stripped response_format
        assert "response_format" not in mock_post.call_args_list[1][1]["json"]

        assert result.ai_mode == "live"
        assert result.recommendation.product_id == "tc-wireless-mouse"
        assert result.recommendation.rationale == "Markdown formatted JSON match"


def test_invalid_json_falls_back_to_deterministic_keyword_matching():
    """If the LLM returns invalid JSON or gibberish, it falls back gracefully without raising."""
    from app.config import Settings
    from app.services.ai_service import generate_recommendation
    from unittest.mock import MagicMock

    settings = Settings(
        ai_provider="openai",
        ai_api_key="test-key",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    resp_gibberish = MagicMock()
    resp_gibberish.status_code = 200
    resp_gibberish.json.return_value = {
        "choices": [{"message": {"content": "This is definitely NOT json content {broken"}}]
    }

    with patch("app.services.ai_service.get_settings", return_value=settings), \
         patch("httpx.Client.post", return_value=resp_gibberish):
        result = generate_recommendation("I need a wireless mouse", catalogue)

        # Graceful fallback without raising
        assert result.ai_mode == "fallback"
        assert result.recommendation.product_id == "tc-wireless-mouse"
        assert "Fallback" in result.recommendation.rationale


def test_unknown_product_id_from_model_is_discarded():
    """
    If the model hallucinates an unknown product ID not in the catalogue,
    it is discarded and the system falls back to the deterministic catalogue match.
    """
    from app.config import Settings
    from app.services.ai_service import generate_recommendation
    import json
    from unittest.mock import MagicMock

    settings = Settings(
        ai_provider="gemini",
        ai_api_key="test-key",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    resp_hallucinated = MagicMock()
    resp_hallucinated.status_code = 200
    resp_hallucinated.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "product_id": "unauthorized-gold-watch-9999",
                        "rationale": "You should buy this gold watch",
                        "matched_requirements": [],
                        "unmet_requirements": [],
                        "confidence_note": "Suspicious",
                        "candidates": [{"product_id": "unauthorized-gold-watch-9999", "reason": "Luxury"}]
                    })
                }
            }
        ]
    }

    with patch("app.services.ai_service.get_settings", return_value=settings), \
         patch("httpx.Client.post", return_value=resp_hallucinated):
        result = generate_recommendation("I want a wireless mouse", catalogue)

        # Fallback triggered because product_id not in catalogue
        assert result.ai_mode == "fallback"
        assert result.recommendation.product_id == "tc-wireless-mouse"
        assert "unauthorized-gold-watch-9999" not in [c.product_id for c in result.recommendation.candidates]
        assert "unauthorized-gold-watch-9999" in result.recommendation.rationale



def test_key_with_empty_model_uses_default_model():
    """When a key is set and model is empty, gemini and openai use their respective default models."""
    from app.config import Settings

    s_gemini = Settings(ai_provider="gemini", ai_api_key="test-key", ai_model="")
    assert s_gemini.ai_model == "gemini-2.5-flash"

    s_openai = Settings(ai_provider="openai", ai_api_key="test-key", ai_model="")
    assert s_openai.ai_model == "gpt-4o-mini"


def test_quotes_and_spaces_around_values_are_stripped():
    """Quotes (single/double) and whitespace around AI config values are stripped, and provider lowercased."""
    from app.config import Settings

    s = Settings(
        ai_provider="  'GEMINI'  ",
        ai_api_key='  "test-secret-key-123"  ',
        ai_model=" 'gemini-custom-pro' ",
        ai_base_url="  \"https://custom-gateway.io/v1/\"  ",
    )
    assert s.ai_provider == "gemini"
    assert s.ai_api_key == "test-secret-key-123"
    assert s.ai_model == "gemini-custom-pro"
    assert s.ai_base_url == "https://custom-gateway.io/v1/"


def test_provider_none_with_key_stays_in_fallback_and_logs_warning(caplog):
    """When a key is set but provider is none/unknown, ai_configured is False, warning is logged, and engine falls back."""
    import logging
    from app.config import Settings
    from app.services.ai_service import generate_recommendation

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    with caplog.at_level(logging.WARNING):
        s_none = Settings(ai_provider="none", ai_api_key="some-key")
        assert s_none.ai_configured is False
        assert "AI key is set but AI_PROVIDER is none or unsupported; running in fallback mode." in caplog.text

    with patch("app.services.ai_service.get_settings", return_value=s_none):
        res = generate_recommendation("I need a wireless mouse", catalogue)
        assert res.ai_mode == "fallback"
        assert res.recommendation.product_id == "tc-wireless-mouse"


def test_health_does_not_leak_key_or_sensitive_base_url(client):
    """
    /api/health must report ai_configured and provider name,
    and must never leak the key, its length, or anything from the base URL except the host name.
    """
    from app.config import Settings

    secret_key = "AIzaSyTestGeminiSecretKey_999988887777"
    sensitive_url = "https://sensitive-user:secret-pass@generativelanguage.googleapis.com:8443/v1beta/openai/?token=secret"

    mock_s = Settings(
        ai_provider="gemini",
        ai_api_key=secret_key,
        ai_base_url=sensitive_url,
    )

    with patch("app.routers.health.get_settings", return_value=mock_s):
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        raw_text = res.text

        # 1. Reports ai_configured and provider name
        assert body["ai_configured"] is True
        assert body["ai_provider"] == "gemini"

        # 2. Never leaks key or credentials
        assert secret_key not in raw_text
        assert "secret-pass" not in raw_text
        assert "sensitive-user" not in raw_text
        assert "token=secret" not in raw_text

        # 3. Only the hostname is exposed from the base URL
        assert body.get("ai_host") == "generativelanguage.googleapis.com"

        # 4. Never includes key length
        key_len = len(secret_key)
        for k, v in body.items():
            assert v != key_len, f"Field '{k}' matches secret key length {key_len}"



def test_url_joining_with_and_without_trailing_slash():
    """Build chat completions URL with exactly one slash, regardless of trailing slash in base URL."""
    from app.services.ai_service import _build_chat_url

    url1 = _build_chat_url("https://generativelanguage.googleapis.com/v1beta/openai/")
    url2 = _build_chat_url("https://generativelanguage.googleapis.com/v1beta/openai")
    expected = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    assert url1 == expected
    assert url2 == expected
    assert "//chat" not in url1


def test_models_prefix_stripping():
    """Verify 'models/' prefix is cleanly stripped from model names in config and AI service."""
    from app.config import Settings
    from app.services.ai_service import _clean_model_name

    s = Settings(ai_provider="gemini", ai_api_key="key", ai_model="models/gemini-2.5-flash")
    assert s.ai_model == "gemini-2.5-flash"
    assert _clean_model_name("models/gemini-flash-latest") == "gemini-flash-latest"
    assert _clean_model_name("gpt-4o-mini") == "gpt-4o-mini"


def test_404_logs_sanitized_reason_and_falls_back(caplog):
    """When configured model returns HTTP 404, log 'configured model not found' with sanitized reason and fall back safely."""
    import logging
    from unittest.mock import MagicMock
    import httpx
    from app.config import Settings
    from app.services.ai_service import generate_recommendation

    settings = Settings(
        ai_provider="gemini",
        ai_api_key="AIzaSySecretKey999",
        ai_model="gemini-nonexistent-model",
    )

    catalogue = [
        {"id": "tc-wireless-mouse", "name": "TechCore Wireless Mouse", "description": "Ergonomic mouse",
         "price_cents": 2999, "currency": "USD", "merchant_id": "techcore", "merchant_name": "TechCore",
         "features": ["wireless"]},
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {
        "error": {
            "message": "models/gemini-nonexistent-model is not found for API key AIzaSySecretKey999"
        }
    }
    mock_resp.text = '{"error": {"message": "models/gemini-nonexistent-model is not found"}}'

    http_error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=mock_resp)

    with caplog.at_level(logging.WARNING):
        with patch("app.services.ai_service.get_settings", return_value=settings), \
             patch("httpx.Client.post", side_effect=http_error):
            res = generate_recommendation("Find a mouse", catalogue)

            # 1. Falls back safely
            assert res.ai_mode == "fallback"
            assert res.recommendation.product_id == "tc-wireless-mouse"

            # 2. Logs 'configured model not found'
            assert "configured model not found" in caplog.text

            # 3. Secret key is NOT in log output
            assert "AIzaSySecretKey999" not in caplog.text
            assert "[REDACTED_KEY]" in caplog.text


def test_health_ai_status_reporting(client):
    """Verify /api/health reports ai_status values: 'not configured', 'ok', and sanitized error strings."""
    from app.config import Settings
    from app.services.ai_service import set_ai_status

    # 1. Not configured
    s_unconf = Settings(ai_provider="none", ai_api_key="")
    with patch("app.routers.health.get_settings", return_value=s_unconf):
        res = client.get("/api/health")
        assert res.json()["ai_status"] == "not configured"

    # 2. Ok
    s_conf = Settings(ai_provider="gemini", ai_api_key="valid-key")
    set_ai_status("ok")
    with patch("app.routers.health.get_settings", return_value=s_conf):
        res = client.get("/api/health")
        assert res.json()["ai_status"] == "ok"

    # 3. Error 404
    set_ai_status("error: HTTP 404 (model not found)")
    with patch("app.routers.health.get_settings", return_value=s_conf):
        res = client.get("/api/health")
        assert res.json()["ai_status"] == "error: HTTP 404 (model not found)"
