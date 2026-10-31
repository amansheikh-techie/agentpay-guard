"""
routers/payments.py — PayPal Sandbox Orders v2 endpoints.

Endpoints:
  POST /api/payments/create-order
  POST /api/payments/capture-order
  POST /api/payments/cancel
  GET  /api/payments/{payment_id}

Security Rules:
  1. Orders can ONLY be created for existing ALLOWED proposals.
  2. Requires explicit user approval signal (user_approved=True).
  3. Re-evaluates spending policy immediately before order creation to prevent stale approvals.
  4. Authoritative amount and currency are read exclusively from SQLite, never from client requests.
  5. Captures are verified with PayPal's response before marking payment captured.
  6. Idempotent: repeated capture calls do not duplicate budget deductions.
  7. Cancelled/failed orders never increment successful_spend_cents.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Policy, Product, Proposal, Payment
from app.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    CaptureOrderRequest,
    CancelOrderRequest,
    PaymentRead,
    PaymentListItem,
)
from app.services import paypal_service, audit_service
from app.services.paypal_service import PayPalError
from app.services.policy_engine import (
    PolicySnapshot,
    ProductSnapshot,
    evaluate,
)

router = APIRouter()

IN_FLIGHT_STATUSES = ("pending", "approved", "capturing", "needs_verification")


def reserved_cents(db: Session, window_minutes: int = 30) -> int:
    """
    Compute total cents reserved by in-flight orders created within the last `window_minutes`.
    Counts payments in pending, approved, capturing, or needs_verification statuses.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    total = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(
            Payment.status.in_(IN_FLIGHT_STATUSES),
            Payment.created_at >= cutoff,
        )
        .scalar()
    )
    return int(total or 0)


def daily_spent_cents(db: Session) -> int:
    """Compute total cents captured in the current UTC calendar day."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(
            Payment.status == "captured",
            Payment.created_at >= start_of_day,
        )
        .scalar()
    )
    return int(total or 0)


def monthly_spent_cents(db: Session) -> int:
    """Compute total cents captured in the current UTC calendar month."""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(
            Payment.status == "captured",
            Payment.created_at >= start_of_month,
        )
        .scalar()
    )
    return int(total or 0)


@router.post("/create-order", response_model=CreateOrderResponse, status_code=status.HTTP_201_CREATED)
def create_payment_order(
    payload: CreateOrderRequest,
    db: Session = Depends(get_db),
):
    """
    Creates a PayPal Sandbox order after re-validating spending policy and explicit user approval.
    """
    settings = get_settings()

    # 1. Fetch Proposal
    proposal = db.query(Proposal).filter(Proposal.id == payload.proposal_id).first()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{payload.proposal_id}' was not found.",
        )

    # 2. Strict policy check: Cannot create payment for blocked proposal
    if proposal.policy_decision != "ALLOWED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a payment order for a BLOCKED purchase proposal.",
        )

    # 3. Resolve authoritative product
    product = db.query(Product).filter(Product.id == proposal.selected_product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product associated with proposal no longer exists in catalogue.",
        )

    # 4. Fetch current policy and perform real-time live re-evaluation
    # Incorporates in-flight reserved budget to prevent concurrent overspending
    policy = db.query(Policy).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spending policy is not configured.",
        )

    in_flight_spend = reserved_cents(db, window_minutes=30)
    effective_spend_cents = policy.successful_spend_cents + in_flight_spend

    policy_snap = PolicySnapshot(
        total_budget_cents=policy.total_budget_cents,
        max_per_order_cents=policy.max_per_order_cents,
        daily_limit_cents=policy.daily_limit_cents,
        monthly_limit_cents=policy.monthly_limit_cents,
        currency=policy.currency,
        approved_merchant_ids=policy.approved_merchant_ids,
        blocked_categories=policy.blocked_categories,
        require_approval=policy.require_approval,
        agent_enabled=policy.agent_enabled,
        successful_spend_cents=effective_spend_cents,
        daily_spend_cents=daily_spent_cents(db),
        monthly_spend_cents=monthly_spent_cents(db),
    )
    product_snap = ProductSnapshot(
        id=product.id,
        price_cents=product.price_cents,
        currency=product.currency,
        merchant_id=product.merchant_id,
        category=product.category,
    )

    recheck_result = evaluate(policy_snap, product_snap, human_approved=payload.user_approved)
    if not recheck_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Live policy re-evaluation blocked checkout: {', '.join(recheck_result.explanations)}",
        )

    # 4b. Verify currency consistency
    if product.currency.upper() != settings.paypal_currency.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product currency '{product.currency}' does not match configured PayPal currency '{settings.paypal_currency}'.",
        )

    # 5. Check PayPal configuration
    if not settings.paypal_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "PayPal Sandbox credentials are not configured in backend/.env. "
                "Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to enable live Sandbox checkout."
            ),
        )

    # 6. Generate payment ID and create PayPal Sandbox order
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"
    return_url = f"{settings.frontend_origin}?payment_status=approved&payment_id={payment_id}"
    cancel_url = f"{settings.frontend_origin}?payment_status=cancelled&payment_id={payment_id}"

    try:
        order_data = paypal_service.create_order(
            amount_cents=product.price_cents,
            currency=product.currency,
            reference_id=payment_id,
            description=product.name,
            return_url=return_url,
            cancel_url=cancel_url,
            request_id=payment_id,
        )
    except PayPalError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayPal Sandbox error: {err.message}",
        )

    paypal_order_id = order_data["id"]
    approve_url = next(
        (link["href"] for link in order_data.get("links", []) if link.get("rel") == "approve"),
        "",
    )

    # 7. Record Payment
    binding = payload.approval_binding or {
        "product_id": product.id,
        "price_cents": product.price_cents,
        "merchant_id": product.merchant_id,
        "policy_version": policy.policy_version,
    }
    payment = Payment(
        id=payment_id,
        proposal_id=proposal.id,
        paypal_order_id=paypal_order_id,
        amount_cents=product.price_cents,
        currency=product.currency,
        status="pending",
    )
    payment.approval_binding = binding
    db.add(payment)
    proposal.status = "approved"
    db.commit()

    # 8. Audit log
    audit_service.log(
        db=db,
        event_type="PAYMENT_CREATED",
        details={
            "paypal_order_id": paypal_order_id,
            "amount_cents": product.price_cents,
            "currency": product.currency,
            "product_id": product.id,
            "product_name": product.name,
            "user_approved": True,
        },
        proposal_id=proposal.id,
        payment_id=payment_id,
    )

    return CreateOrderResponse(
        payment_id=payment_id,
        paypal_order_id=paypal_order_id,
        approve_url=approve_url,
        status="pending",
    )


@router.post("/capture-order", response_model=PaymentRead)
def capture_payment_order(
    payload: CaptureOrderRequest,
    db: Session = Depends(get_db),
):
    """
    Captures an approved PayPal order and updates the spending policy budget on verified completion.
    Idempotent: Duplicate calls for an already-captured order do not duplicate budget deductions.
    """
    # 1. Fetch Payment record
    payment = db.query(Payment).filter(Payment.paypal_order_id == payload.paypal_order_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment for PayPal order '{payload.paypal_order_id}' was not found.",
        )

    # 1b. Verify approval binding integrity
    if payment.approval_binding:
        binding = payment.approval_binding
        if binding.get("price_cents") and binding["price_cents"] != payment.amount_cents:
            payment.status = "needs_verification"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Security alert: Purchase amount changed between approval and capture (APPROVAL_MISMATCH).",
            )

    # 2. Idempotency protection: If already captured, return existing state without deducting again
    if payment.status == "captured":
        return payment

    # 2b. Atomic claim: Claim payment by moving status to 'capturing'
    claim_count = (
        db.query(Payment)
        .filter(
            Payment.id == payment.id,
            Payment.status.in_(["pending", "approved"]),
        )
        .update({"status": "capturing"}, synchronize_session="fetch")
    )
    db.commit()

    if claim_count == 0:
        db.refresh(payment)
        if payment.status == "captured":
            return payment
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment order is currently being captured (status: '{payment.status}').",
        )

    # 2c. Recheck remaining budget before calling PayPal
    policy = db.query(Policy).first()
    if not policy:
        payment.status = "pending"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spending policy is not configured.",
        )

    remaining_budget = policy.total_budget_cents - policy.successful_spend_cents
    if payment.amount_cents > remaining_budget:
        payment.status = "pending"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Remaining budget ({remaining_budget} cents) is insufficient for this payment ({payment.amount_cents} cents).",
        )

    # 3. Call PayPal Capture API (includes pre-flight order status check)
    try:
        capture_data = paypal_service.capture_order(
            payload.paypal_order_id,
            request_id=f"cap_{payment.id}",
        )
    except PayPalError as err:
        issue_code = err.details.get("issue", "") if isinstance(err.details, dict) else ""
        if issue_code == "ORDER_NOT_APPROVED":
            # Reset status to 'pending' on ORDER_NOT_APPROVED so the buyer can still approve
            payment.status = "pending"
            db.commit()
            audit_service.log(
                db=db,
                event_type="PAYMENT_AWAITING_APPROVAL",
                details={
                    "error": err.message,
                    "paypal_order_id": payload.paypal_order_id,
                    "issue": issue_code,
                },
                proposal_id=payment.proposal_id,
                payment_id=payment.id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err.message,
            )

        payment.status = "failed"
        db.commit()
        audit_service.log(
            db=db,
            event_type="PAYMENT_FAILED",
            details={"error": err.message, "paypal_order_id": payload.paypal_order_id},
            proposal_id=payment.proposal_id,
            payment_id=payment.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PayPal capture failed: {err.message}",
        )

    # 4. Verify PayPal capture status
    paypal_status = capture_data.get("status")
    if paypal_status != "COMPLETED":
        payment.status = "needs_verification"
        db.commit()
        audit_service.log(
            db=db,
            event_type="PAYMENT_NEEDS_VERIFICATION",
            details={"status": paypal_status, "paypal_order_id": payload.paypal_order_id},
            proposal_id=payment.proposal_id,
            payment_id=payment.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PayPal payment is not completed. Current status: {paypal_status}",
        )

    # 5. Extract capture ID and verify amount
    purchase_units = capture_data.get("purchase_units", [])
    captures = purchase_units[0].get("payments", {}).get("captures", []) if purchase_units else []
    if not captures:
        payment.status = "needs_verification"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No capture details returned from PayPal.",
        )

    capture_record = captures[0]
    capture_id = capture_record.get("id")
    amount_str = capture_record.get("amount", {}).get("value", "0")
    currency = capture_record.get("amount", {}).get("currency_code", "")

    expected_str = f"{payment.amount_cents / 100:.2f}"
    if amount_str != expected_str or currency.upper() != payment.currency.upper():
        payment.status = "needs_verification"
        db.commit()
        audit_service.log(
            db=db,
            event_type="PAYMENT_MISMATCH",
            details={
                "expected_amount": expected_str,
                "captured_amount": amount_str,
                "expected_currency": payment.currency,
                "captured_currency": currency,
            },
            proposal_id=payment.proposal_id,
            payment_id=payment.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captured amount or currency does not match authoritative purchase value.",
        )

    # 6. Verified successful capture: Update payment and policy budget once
    payment.status = "captured"
    payment.paypal_capture_id = capture_id

    # Deduct budget using an atomic SQL UPDATE expression
    db.query(Policy).filter(Policy.id == policy.id).update(
        {Policy.successful_spend_cents: Policy.successful_spend_cents + payment.amount_cents},
        synchronize_session="fetch",
    )

    db.commit()
    db.refresh(payment)
    db.refresh(policy)

    # 7. Immutable audit logging
    audit_service.log(
        db=db,
        event_type="PAYMENT_CAPTURED",
        details={
            "paypal_order_id": payload.paypal_order_id,
            "paypal_capture_id": capture_id,
            "amount_cents": payment.amount_cents,
            "currency": payment.currency,
            "new_successful_spend_cents": policy.successful_spend_cents if policy else 0,
        },
        proposal_id=payment.proposal_id,
        payment_id=payment.id,
    )

    return payment


@router.post("/cancel")
def cancel_payment_order(
    payload: CancelOrderRequest,
    db: Session = Depends(get_db),
):
    """
    Records payment cancellation. Does NOT count towards budget spend.
    """
    payment = db.query(Payment).filter(Payment.paypal_order_id == payload.paypal_order_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment for order '{payload.paypal_order_id}' was not found.",
        )

    payment.status = "cancelled"
    db.commit()

    audit_service.log(
        db=db,
        event_type="PAYMENT_CANCELLED",
        details={"paypal_order_id": payload.paypal_order_id},
        proposal_id=payment.proposal_id,
        payment_id=payment.id,
    )

    return {"status": "cancelled", "payment_id": payment.id}


@router.get("", response_model=list[PaymentListItem])
def list_payments(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return historical transactions, newest first, with optional status filter."""
    query = (
        db.query(
            Payment.id,
            Payment.proposal_id,
            Payment.paypal_order_id,
            Payment.amount_cents,
            Payment.currency,
            Payment.status,
            Payment.paypal_capture_id,
            Product.name.label("product_name"),
            Product.merchant_name.label("merchant_name"),
            Payment.created_at,
            Payment.updated_at,
        )
        .outerjoin(Proposal, Proposal.id == Payment.proposal_id)
        .outerjoin(Product, Product.id == Proposal.selected_product_id)
    )
    if status:
        query = query.filter(Payment.status == status)

    rows = query.order_by(Payment.created_at.desc()).limit(limit).all()
    return [
        PaymentListItem(
            id=r.id,
            proposal_id=r.proposal_id,
            paypal_order_id=r.paypal_order_id,
            amount_cents=r.amount_cents,
            currency=r.currency,
            status=r.status,
            paypal_capture_id=r.paypal_capture_id,
            product_name=r.product_name,
            merchant_name=r.merchant_name,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    """Fetch payment status and capture details."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment '{payment_id}' was not found.",
        )
    return payment
