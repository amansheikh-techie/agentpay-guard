"""
routers/policy.py — GET /api/policy  and  PUT /api/policy
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Policy, Product
from app.schemas import PolicyRead, PolicyUpdate
from app.security import require_admin
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


@router.put("/policy", response_model=PolicyRead, tags=["policy"], dependencies=[Depends(require_admin)])
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
    if body.daily_limit_cents is not None:
        policy.daily_limit_cents = body.daily_limit_cents
    if body.monthly_limit_cents is not None:
        policy.monthly_limit_cents = body.monthly_limit_cents
    policy.currency = body.currency
    policy.approved_merchant_ids = body.approved_merchant_ids
    if body.blocked_categories is not None:
        policy.blocked_categories = body.blocked_categories
    policy.require_approval = body.require_approval
    if body.agent_enabled is not None:
        policy.agent_enabled = body.agent_enabled
    policy.policy_version = (policy.policy_version or 1) + 1

    db.commit()
    db.refresh(policy)

    audit_service.log(
        db,
        event_type="POLICY_UPDATED",
        details={
            "total_budget_cents": body.total_budget_cents,
            "max_per_order_cents": body.max_per_order_cents,
            "daily_limit_cents": policy.daily_limit_cents,
            "monthly_limit_cents": policy.monthly_limit_cents,
            "approved_merchant_ids": body.approved_merchant_ids,
            "blocked_categories": policy.blocked_categories,
            "require_approval": body.require_approval,
            "agent_enabled": policy.agent_enabled,
            "policy_version": policy.policy_version,
        },
    )

    return PolicyRead.model_validate(policy)


@router.post("/policy/reset", response_model=PolicyRead, tags=["policy"], dependencies=[Depends(require_admin)])
def reset_policy(db: Session = Depends(get_db)):
    """
    Reset demo policy and budget counters to initial state for repeat demo runs.
    """
    from app.seed import DEFAULT_POLICY
    now_utc = datetime.now(timezone.utc)
    policy = _get_policy(db)
    policy.total_budget_cents = DEFAULT_POLICY["total_budget_cents"]
    policy.max_per_order_cents = DEFAULT_POLICY["max_per_order_cents"]
    policy.daily_limit_cents = DEFAULT_POLICY.get("daily_limit_cents", 0)
    policy.monthly_limit_cents = DEFAULT_POLICY.get("monthly_limit_cents", 0)
    policy.currency = DEFAULT_POLICY["currency"]
    policy.approved_merchant_ids = DEFAULT_POLICY["approved_merchant_ids"]
    policy.blocked_categories = DEFAULT_POLICY.get("blocked_categories", [])
    policy.require_approval = DEFAULT_POLICY["require_approval"]
    policy.agent_enabled = DEFAULT_POLICY.get("agent_enabled", True)
    policy.policy_version = 1
    policy.successful_spend_cents = 0
    policy.last_reset_at = now_utc
    db.commit()
    db.refresh(policy)

    audit_service.log(
        db,
        event_type="DEMO_RESET",
        details={
            "action": "Reset spending policy and budget counters to pristine demo defaults",
            "total_budget_cents": policy.total_budget_cents,
            "max_per_order_cents": policy.max_per_order_cents,
            "policy_version": policy.policy_version,
            "last_reset_at": now_utc.isoformat(),
        },
    )

    return PolicyRead.model_validate(policy)
