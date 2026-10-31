"""
routers/summary.py — GET /api/summary

Provides aggregated metrics for budget utilization, status counts,
and merchant breakdowns.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Policy, Payment, Proposal, Product
from app.schemas import SummaryResponse, MerchantSpendSummary
from app.routers.payments import reserved_cents, daily_spent_cents, monthly_spent_cents

router = APIRouter(tags=["summary"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(db: Session = Depends(get_db)):
    """Return dashboard summary numbers."""
    policy = db.query(Policy).first()
    total_budget_cents = policy.total_budget_cents if policy else 10000

    completed_cents = int(
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status == "captured")
        .scalar()
        or 0
    )

    in_flight = reserved_cents(db, window_minutes=30)
    remaining_cents = max(0, total_budget_cents - completed_cents - in_flight)

    daily_spent = daily_spent_cents(db)
    monthly_spent = monthly_spent_cents(db)

    blocked_count = db.query(Proposal).filter(Proposal.policy_decision == "BLOCKED").count()
    completed_count = db.query(Payment).filter(Payment.status == "captured").count()
    failed_count = db.query(Payment).filter(Payment.status.in_(["cancelled", "failed"])).count()

    # Merchant spend summary
    # Join Payment -> Proposal -> Product
    merchant_rows = (
        db.query(
            Product.merchant_id,
            Product.merchant_name,
            func.coalesce(func.sum(Payment.amount_cents), 0).label("total_cents"),
            func.count(Payment.id).label("order_count"),
        )
        .join(Proposal, Proposal.selected_product_id == Product.id)
        .join(Payment, Payment.proposal_id == Proposal.id)
        .filter(Payment.status == "captured")
        .group_by(Product.merchant_id, Product.merchant_name)
        .all()
    )

    by_merchant = [
        MerchantSpendSummary(
            merchant_id=row[0],
            merchant_name=row[1],
            total_cents=int(row[2]),
            order_count=int(row[3]),
        )
        for row in merchant_rows
    ]

    return SummaryResponse(
        completed_cents=completed_cents,
        reserved_cents=in_flight,
        remaining_cents=remaining_cents,
        daily_spent_cents=daily_spent,
        monthly_spent_cents=monthly_spent,
        blocked_count=blocked_count,
        completed_count=completed_count,
        failed_count=failed_count,
        by_merchant=by_merchant,
    )
