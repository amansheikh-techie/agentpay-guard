"""
routers/agent.py — AI purchase proposal endpoint.

Endpoint:
  POST /api/agent/propose

Trust Boundaries:
  1. The AI model only proposes a product_id.
  2. The backend looks up authoritative price and merchant from SQLite.
  3. The deterministic policy engine evaluates the proposal against spending rules.
  4. The result (ALLOWED or BLOCKED) and explanations are recorded in proposals and audit_events.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Policy, Product, Proposal
from app.schemas import ProposeRequest, ProposalRead
from app.services import ai_service, audit_service
from app.services.policy_engine import (
    PolicySnapshot,
    ProductSnapshot,
    PolicyResult,
    evaluate_proposal,
)

router = APIRouter()


@router.post("/propose", response_model=ProposalRead, status_code=status.HTTP_201_CREATED)
def propose_purchase(
    payload: ProposeRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts natural-language shopping request, generates an AI recommendation,
    independently evaluates spending policy, and records the proposal.
    """
    # 1. Fetch current active catalogue
    products = db.query(Product).filter(Product.active == True).all()
    if not products:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalogue is currently unavailable.",
        )

    catalogue_data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price_cents": p.price_cents,
            "currency": p.currency,
            "merchant_id": p.merchant_id,
            "merchant_name": p.merchant_name,
            "features": p.features,
        }
        for p in products
    ]

    # 2. Call AI service (or deterministic fallback)
    ai_result = ai_service.generate_recommendation(payload.user_request, catalogue_data)
    rec = ai_result.recommendation

    # 3. Look up authoritative product in the database
    product = db.query(Product).filter(Product.id == rec.product_id).first()

    # 4. Fetch authoritative policy
    policy = db.query(Policy).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spending policy is not configured.",
        )

    # 5. Evaluate policy deterministically
    if not product:
        decision = PolicyResult(
            decision="BLOCKED",
            reasons=["UNKNOWN_PRODUCT"],
            explanations=[f"Recommended product ID '{rec.product_id}' is not in the authoritative catalogue."],
        )
    else:
        policy_snap = PolicySnapshot(
            total_budget_cents=policy.total_budget_cents,
            max_per_order_cents=policy.max_per_order_cents,
            currency=policy.currency,
            approved_merchant_ids=policy.approved_merchant_ids,
            require_approval=policy.require_approval,
            successful_spend_cents=policy.successful_spend_cents,
        )
        product_snap = ProductSnapshot(
            id=product.id,
            price_cents=product.price_cents,
            currency=product.currency,
            merchant_id=product.merchant_id,
        )
        decision = evaluate_proposal(policy_snap, product_snap)

    # 6. Save Proposal
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    proposal = Proposal(
        id=proposal_id,
        user_request=payload.user_request,
        selected_product_id=product.id if product else None,
        rationale=rec.rationale,
        status="pending",
        policy_decision=decision.decision,
        ai_mode=ai_result.ai_mode,
    )
    proposal.decision_reasons = decision.reasons
    proposal.decision_explanations = decision.explanations

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    # 7. Immutable audit logging
    audit_service.log(
        db=db,
        event_type="PROPOSAL_CREATED",
        details={
            "user_request": payload.user_request,
            "product_id": product.id if product else None,
            "product_name": product.name if product else None,
            "price_cents": product.price_cents if product else None,
            "policy_decision": decision.decision,
            "reasons": decision.reasons,
            "explanations": decision.explanations,
            "ai_mode": ai_result.ai_mode,
        },
        proposal_id=proposal_id,
    )

    return proposal
