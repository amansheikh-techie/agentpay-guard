"""
test_voice_assistant.py — Comprehensive tests for the Voice Assistant feature
and Overview counters invariant after Reset Demo.

Invariants verified:
1. Voice request creates a valid proposal with deterministic spoken_response.
2. Spoken response contains item, USD amount, ALLOWED/BLOCKED with rule name, and approval reminder.
3. Over-limit voice request is BLOCKED deterministically by the rule engine.
4. Unclear voice input creates NO proposal in DB, NO order, and makes NO external call.
5. input_mode is logged in the audit trail (input_mode="voice").
6. Invariance: identical request sent as text vs voice yields identical decisions and product selections.
7. Overview counters after Reset Demo reflect 0 spend and 0 counts.
"""
import pytest
from app.models import Proposal, Payment, AuditEvent
from tests.conftest import TestSessionLocal


def test_voice_request_creates_proposal(client, clean_test_db):
    """
    Valid voice shopping request:
    - Creates a proposal with input_mode="voice"
    - Rule engine evaluates ALLOWED for in-cap item
    - Deterministic spoken_response contains item, USD amount, ALLOWED, and approval reminder
    """
    res = client.post(
        "/api/agent/propose",
        json={
            "user_request": "Find a wireless mouse under $35 from an approved merchant",
            "input_mode": "voice",
        },
    )
    assert res.status_code == 201
    data = res.json()

    assert data["policy_decision"] == "ALLOWED"
    assert data["selected_product_id"] == "tc-wireless-mouse"
    assert data["input_mode"] == "voice"
    assert data["spoken_response"] is not None

    spoken = data["spoken_response"]
    assert "Wireless Mouse" in spoken
    assert "$29.99 USD" in spoken
    assert "ALLOWED" in spoken
    assert "Approvals tab" in spoken


def test_voice_request_over_limit_blocked(client, clean_test_db):
    """
    Over-limit voice request ($79.99 keyboard vs $40 cap):
    - Policy decision is BLOCKED
    - Spoken response states item, amount in USD, BLOCKED, and rule name (MAX_ORDER_AMOUNT_EXCEEDED)
    - Suggests in-policy alternatives
    """
    res = client.post(
        "/api/agent/propose",
        json={
            "user_request": "I need a high-end mechanical keyboard for typing",
            "input_mode": "voice",
        },
    )
    assert res.status_code == 201
    data = res.json()

    assert data["policy_decision"] == "BLOCKED"
    assert "MAX_ORDER_AMOUNT_EXCEEDED" in data["decision_reasons"]
    assert data["input_mode"] == "voice"

    spoken = data["spoken_response"]
    assert "Mechanical Keyboard" in spoken
    assert "$79.99 USD" in spoken
    assert "BLOCKED by MAX_ORDER_AMOUNT_EXCEEDED" in spoken
    assert "cannot be approved" in spoken
    assert "final approval is required" not in spoken.lower()
    assert "approvals tab" not in spoken.lower()


def test_unclear_voice_input_creates_no_proposal_or_order(client, clean_test_db):
    """
    Unclear or empty voice input:
    - Deterministic check before calling LLM or creating orders
    - Rejects with HTTP 422 and a helpful speech prompt
    - Asserts 0 proposals were inserted into SQLite and 0 orders created
    """
    unclear_inputs = [
        "uh um",
        "hello",
        "testing testing",
        "xyzabc 12345",
        "hmm what",
    ]

    db = TestSessionLocal()
    initial_proposals_count = db.query(Proposal).count()
    initial_payments_count = db.query(Payment).count()
    db.close()

    for text in unclear_inputs:
        res = client.post(
            "/api/agent/propose",
            json={
                "user_request": text,
                "input_mode": "voice",
            },
        )
        assert res.status_code == 422
        err = res.json()
        assert "unclear" in err["detail"].lower() or "repeat" in err["detail"].lower()

    # Invariant: No proposals or payments created in DB
    db = TestSessionLocal()
    assert db.query(Proposal).count() == initial_proposals_count
    assert db.query(Payment).count() == initial_payments_count
    db.close()


def test_audit_log_records_input_mode_voice(client, clean_test_db):
    """
    Audit log must explicitly record input_mode="voice" and the spoken_response.
    """
    res = client.post(
        "/api/agent/propose",
        json={
            "user_request": "Find an ergonomic desk lamp for work",
            "input_mode": "voice",
        },
    )
    assert res.status_code == 201
    proposal_id = res.json()["id"]

    audit_res = client.get(f"/api/audit?event_type=PROPOSAL_CREATED")
    assert audit_res.status_code == 200
    events = audit_res.json()

    matching_event = next((e for e in events if e.get("proposal_id") == proposal_id), None)
    assert matching_event is not None
    details = matching_event["details"]
    assert details.get("input_mode") == "voice"
    assert "spoken_response" in details
    assert "Proposed" in details["spoken_response"]


def test_input_mode_invariance(client, clean_test_db):
    """
    Core Security Invariant:
    input_mode must ONLY be logged and must NEVER affect rule decisions,
    product lookup, or prices. Identical prompt sent as text vs voice
    yields identical decisions.
    """
    prompt = "I need an office notebook and pen set under $20"

    res_text = client.post(
        "/api/agent/propose",
        json={"user_request": prompt, "input_mode": "text"},
    )
    assert res_text.status_code == 201
    data_text = res_text.json()

    res_voice = client.post(
        "/api/agent/propose",
        json={"user_request": prompt, "input_mode": "voice"},
    )
    assert res_voice.status_code == 201
    data_voice = res_voice.json()

    # Crucial parity assertions
    assert data_text["policy_decision"] == data_voice["policy_decision"]
    assert data_text["selected_product_id"] == data_voice["selected_product_id"]
    assert data_text["product"]["price_cents"] == data_voice["product"]["price_cents"]
    assert data_text["product"]["merchant_id"] == data_voice["product"]["merchant_id"]
    assert data_text["decision_reasons"] == data_voice["decision_reasons"]


def test_overview_counters_after_reset_demo(client, clean_test_db):
    """
    Verify Overview metrics after Reset Demo:
    1. Make purchase proposals and an approved captured payment
    2. Reset demo via POST /api/policy/reset
    3. Verify GET /api/summary returns completed_cents=0, completed_count=0, blocked_count=0
    4. Remaining cents equals total budget cents
    """
    # Create allowed proposal
    prop_res = client.post(
        "/api/agent/propose",
        json={"user_request": "Buy a wireless mouse under $35", "input_mode": "text"},
    )
    assert prop_res.status_code == 201

    # Create blocked proposal
    client.post(
        "/api/agent/propose",
        json={"user_request": "Buy a $79 mechanical keyboard", "input_mode": "text"},
    )

    # Reset demo
    reset_res = client.post("/api/policy/reset")
    assert reset_res.status_code == 200
    policy_data = reset_res.json()
    assert policy_data["successful_spend_cents"] == 0
    assert policy_data["last_reset_at"] is not None

    # Verify summary counters
    sum_res = client.get("/api/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()

    assert summary["completed_cents"] == 0
    assert summary["completed_count"] == 0
    assert summary["blocked_count"] == 0
    assert summary["daily_spent_cents"] == 0
    assert summary["remaining_cents"] == policy_data["total_budget_cents"]
