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

        product_cols = {c["name"] for c in insp.get_columns("products")}
        assert "category" in product_cols

        payment_cols = {c["name"] for c in insp.get_columns("payments")}
        assert "approval_binding" in payment_cols

        pol = conn.execute(text("SELECT total_budget_cents, daily_limit_cents, agent_enabled, policy_version FROM policies WHERE id='policy_default'")).fetchone()
        assert pol[0] == 10000
        assert pol[1] == 0
        assert pol[2] == 1
        assert pol[3] == 1

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

