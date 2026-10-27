"""
routers/policy.py — GET /api/policy  and  PUT /api/policy
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Policy, Product
from app.schemas import PolicyRead, PolicyUpdate
from app.services import audit_service

router = APIRouter()


def _get_policy(db: Session) -> Policy:
    policy = db.query(Policy).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found. Run the seed first.")
    return policy


@router.get("/policy", response_model=PolicyRead, tags=["policy"])
def get_policy(db: Session = Depends(get_db)):
    """Return current spending policy and budget state."""
    policy = _get_policy(db)
    return PolicyRead.model_validate(policy)


@router.put("/policy", response_model=PolicyRead, tags=["policy"])
def update_policy(body: PolicyUpdate, db: Session = Depends(get_db)):
    """
    Update spending policy.
    Validates that approved_merchant_ids exist in the catalogue.
    """
    policy = _get_policy(db)

    # Validate merchant IDs exist in catalogue
    known_merchants = {p.merchant_id for p in db.query(Product.merchant_id).all()}
    unknown = [m for m in body.approved_merchant_ids if m not in known_merchants]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown merchant IDs (not in catalogue): {unknown}",
        )

    policy.total_budget_cents = body.total_budget_cents
    policy.max_per_order_cents = body.max_per_order_cents
    policy.currency = body.currency
    policy.approved_merchant_ids = body.approved_merchant_ids
    policy.require_approval = body.require_approval
    db.commit()
    db.refresh(policy)

    audit_service.log(
        db,
        event_type="POLICY_UPDATED",
        details={
            "total_budget_cents": body.total_budget_cents,
            "max_per_order_cents": body.max_per_order_cents,
            "approved_merchant_ids": body.approved_merchant_ids,
            "require_approval": body.require_approval,
        },
    )

    return PolicyRead.model_validate(policy)
