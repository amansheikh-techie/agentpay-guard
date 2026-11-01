"""
routers/agent.py — AI purchase proposal endpoint.

Endpoint:
  POST /api/agent/propose

Trust Boundaries:
  1. The AI model only proposes product IDs and short text.
  2. The backend looks up authoritative price and merchant from SQLite.
  3. The deterministic policy engine evaluates all proposals against spending rules.
  4. Any candidate ID not in the authoritative catalogue is discarded.
  5. The result (ALLOWED or BLOCKED) and explanations are recorded in proposals and audit_events.
"""
import re
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Policy, Product, Proposal
from app.schemas import ProposeRequest, ProposalRead, ProductRead, ExtractedRequirements
from app.services import ai_service, audit_service
from app.services.policy_engine import (
    PolicySnapshot,
    ProductSnapshot,
    PolicyResult,
    evaluate_proposal,
)
from app.routers.payments import daily_spent_cents, monthly_spent_cents, reserved_cents

router = APIRouter()


def _keyword_extract_requirements(text: str) -> ExtractedRequirements:
    cat = None
    tl = text.lower()
    if any(w in tl for w in ["mouse", "mice", "keyboard", "hub", "webcam"]):
        cat = "peripherals"
    elif any(w in tl for w in ["headset", "audio", "mic", "earphone", "headphone"]):
        cat = "audio"
    elif any(w in tl for w in ["lamp", "stand", "notebook", "pen", "desk", "organiser", "organizer", "office"]):
        cat = "office"
    elif "gadget" in tl:
        cat = "gadgets"

    max_p = None
    price_match = re.search(r"\$(\d+)(?:\.(\d{2}))?", text)
    if price_match:
        dollars = int(price_match.group(1))
        cents = int(price_match.group(2) or 0)
        max_p = dollars * 100 + cents
    else:
        under_match = re.search(r"under\s+(\d+)", tl)
        if under_match:
            max_p = int(under_match.group(1)) * 100

    features = []
    if "wireless" in tl:
        features.append("Wireless")
    if "ergonomic" in tl:
        features.append("Ergonomic")
    if "noise" in tl or "cancelling" in tl:
        features.append("Noise cancelling")
    if "usb" in tl:
        features.append("USB-C / USB")

    return ExtractedRequirements(category=cat, max_price_cents=max_p, features=features)


def _extract_requirements(
    text: str,
    valid_categories: Optional[list[str]] = None,
    ai_mode: str = "fallback",
) -> ExtractedRequirements:
    if ai_mode == "live" and valid_categories:
        ai_extracted = ai_service.extract_requirements_from_ai(text, valid_categories)
        if ai_extracted:
            return ExtractedRequirements(
                category=ai_extracted.get("category"),
                max_price_cents=ai_extracted.get("max_price_cents"),
                features=ai_extracted.get("features", []),
            )
    return _keyword_extract_requirements(text)


@router.post("/propose", response_model=ProposalRead, status_code=status.HTTP_201_CREATED)
def propose_purchase(
    payload: ProposeRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts natural-language shopping request, generates an AI recommendation,
    independently evaluates spending policy, discovers safe alternatives if blocked,
    and records the proposal(s).
    """
    # 1. Fetch current active catalogue
    products = db.query(Product).filter(Product.active == True).all()
    if not products:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalogue is currently unavailable.",
        )

    product_map = {p.id: p for p in products}

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

    # 3. Look up authoritative primary product in the database
    primary_product = product_map.get(rec.product_id)

    # 4. Fetch authoritative policy
    policy = db.query(Policy).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spending policy is not configured.",
        )

    valid_cats = list({p.category for p in products if p.category}) or ["peripherals", "office", "audio", "gadgets"]
    extracted_reqs = _extract_requirements(
        payload.user_request,
        valid_categories=valid_cats,
        ai_mode=ai_result.ai_mode,
    )

    effective_spend_cents = policy.successful_spend_cents + reserved_cents(db)
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

    # 5. Evaluate primary proposal deterministically
    if not primary_product:
        primary_decision = PolicyResult(
            decision="BLOCKED",
            reasons=["UNKNOWN_PRODUCT"],
            explanations=[f"Recommended product ID '{rec.product_id}' is not in the authoritative catalogue."],
        )
    else:
        primary_snap = ProductSnapshot(
            id=primary_product.id,
            price_cents=primary_product.price_cents,
            currency=primary_product.currency,
            merchant_id=primary_product.merchant_id,
            category=primary_product.category,
        )
        primary_decision = evaluate_proposal(policy_snap, primary_snap)

    # 6. Save Primary Proposal
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    primary_proposal = Proposal(
        id=proposal_id,
        user_request=payload.user_request,
        selected_product_id=primary_product.id if primary_product else None,
        rationale=rec.rationale,
        status="pending",
        policy_decision=primary_decision.decision,
        ai_mode=ai_result.ai_mode,
    )
    primary_proposal.decision_reasons = primary_decision.reasons
    primary_proposal.decision_explanations = primary_decision.explanations

    db.add(primary_proposal)
    db.commit()
    db.refresh(primary_proposal)

    # 7. Immutable audit logging for primary proposal
    audit_service.log(
        db=db,
        event_type="PROPOSAL_CREATED",
        details={
            "user_request": payload.user_request,
            "product_id": primary_product.id if primary_product else None,
            "product_name": primary_product.name if primary_product else None,
            "price_cents": primary_product.price_cents if primary_product else None,
            "policy_decision": primary_decision.decision,
            "reasons": primary_decision.reasons,
            "explanations": primary_decision.explanations,
            "ai_mode": ai_result.ai_mode,
        },
        proposal_id=proposal_id,
    )

    # 8. Smart Alternatives: if blocked, evaluate candidates and catalogue for up to 2 ALLOWED alternatives
    alternatives_read: list[ProposalRead] = []
    block_explanation = None

    if primary_decision.decision == "BLOCKED":
        block_explanation = ai_service.generate_block_explanation(
            user_request=payload.user_request,
            product_name=primary_product.name if primary_product else rec.product_id,
            reasons=primary_decision.reasons,
            explanations=primary_decision.explanations,
            ai_mode=ai_result.ai_mode,
        )

        # Collect candidate product IDs to inspect: first AI candidates, then catalogue fallback
        candidate_queue: list[tuple[str, str]] = []  # (product_id, reason)
        seen_cand_ids = {primary_product.id} if primary_product else set()

        # From AI candidates
        for cand in rec.candidates:
            if cand.product_id in product_map and cand.product_id not in seen_cand_ids:
                candidate_queue.append((cand.product_id, cand.reason or "Suggested alternative"))
                seen_cand_ids.add(cand.product_id)

        # Fill queue with remaining catalogue products (sorted by price) if needed
        for p in sorted(products, key=lambda x: x.price_cents):
            if p.id not in seen_cand_ids:
                candidate_queue.append((p.id, f"In-policy catalogue alternative ({p.name})"))
                seen_cand_ids.add(p.id)

        allowed_alternatives: list[tuple[Product, str]] = []
        for cand_id, cand_reason in candidate_queue:
            cand_prod = product_map.get(cand_id)
            if not cand_prod:
                continue

            cand_snap = ProductSnapshot(
                id=cand_prod.id,
                price_cents=cand_prod.price_cents,
                currency=cand_prod.currency,
                merchant_id=cand_prod.merchant_id,
                category=cand_prod.category,
            )
            cand_decision = evaluate_proposal(policy_snap, cand_snap)
            if cand_decision.decision == "ALLOWED":
                allowed_alternatives.append((cand_prod, cand_reason))
                if len(allowed_alternatives) >= 2:
                    break

        # Persist each alternative as its own Proposal row so it can be approved
        alt_ids = []
        alt_product_ids = []
        for idx, (alt_prod, alt_reason) in enumerate(allowed_alternatives):
            alt_id = f"prop_{uuid.uuid4().hex[:12]}"
            alt_rationale = (
                f"[Alternative Proposal] {alt_reason}. "
                f"Evaluated and verified compliant with spending policy."
            )
            alt_proposal = Proposal(
                id=alt_id,
                user_request=payload.user_request,
                selected_product_id=alt_prod.id,
                rationale=alt_rationale,
                status="pending",
                policy_decision="ALLOWED",
                ai_mode=ai_result.ai_mode,
            )
            alt_proposal.decision_reasons = []
            alt_proposal.decision_explanations = []
            db.add(alt_proposal)
            db.commit()
            db.refresh(alt_proposal)

            alt_ids.append(alt_id)
            alt_product_ids.append(alt_prod.id)

            price_diff = (
                alt_prod.price_cents - primary_product.price_cents
                if primary_product
                else 0
            )

            alternatives_read.append(
                ProposalRead(
                    id=alt_id,
                    user_request=payload.user_request,
                    selected_product_id=alt_prod.id,
                    product=ProductRead.model_validate(alt_prod),
                    rationale=alt_rationale,
                    status=alt_proposal.status,
                    policy_decision="ALLOWED",
                    decision_reasons=[],
                    decision_explanations=[],
                    ai_mode=ai_result.ai_mode,
                    block_explanation=None,
                    alternatives=[],
                    rank=idx + 2,
                    matched_requirements=[f"Category: {alt_prod.category}", f"Sold by {alt_prod.merchant_name}"],
                    unmet_requirements=[],
                    price_difference_cents=price_diff,
                    candidates=[],
                    created_at=alt_proposal.created_at,
                )
            )

        if allowed_alternatives:
            audit_service.log(
                db=db,
                event_type="ALTERNATIVES_SUGGESTED",
                details={
                    "primary_proposal_id": proposal_id,
                    "alternative_proposal_ids": alt_ids,
                    "alternative_product_ids": alt_product_ids,
                },
                proposal_id=proposal_id,
            )

    return ProposalRead(
        id=primary_proposal.id,
        user_request=primary_proposal.user_request,
        selected_product_id=primary_proposal.selected_product_id,
        product=ProductRead.model_validate(primary_product) if primary_product else None,
        rationale=primary_proposal.rationale,
        status=primary_proposal.status,
        policy_decision=primary_proposal.policy_decision,
        decision_reasons=primary_proposal.decision_reasons,
        decision_explanations=primary_proposal.decision_explanations,
        ai_mode=primary_proposal.ai_mode,
        block_explanation=block_explanation,
        alternatives=alternatives_read,
        extracted_requirements=extracted_reqs,
        rank=1,
        matched_requirements=rec.matched_requirements,
        unmet_requirements=rec.unmet_requirements,
        price_difference_cents=0,
        candidates=alternatives_read,
        created_at=primary_proposal.created_at,
    )
