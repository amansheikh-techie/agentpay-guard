"""
schemas.py — Pydantic request/response schemas.

Money fields exposed to the API use integer cents only.
Formatted display strings (e.g. "$30.00") are computed by the frontend.
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ── Policy ────────────────────────────────────────────────────────────────────

class PolicyRead(BaseModel):
    id: int
    total_budget_cents: int
    max_per_order_cents: int
    currency: str
    approved_merchant_ids: list[str]
    require_approval: bool
    successful_spend_cents: int
    remaining_budget_cents: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):  # type: ignore[override]
        instance = super().model_validate(obj, **kwargs)
        # Compute remaining from the ORM property if available
        if hasattr(obj, "remaining_budget_cents"):
            instance.remaining_budget_cents = obj.remaining_budget_cents
        else:
            instance.remaining_budget_cents = (
                instance.total_budget_cents - instance.successful_spend_cents
            )
        return instance



class PolicyUpdate(BaseModel):
    total_budget_cents: int = Field(..., gt=0, description="Must be > 0")
    max_per_order_cents: int = Field(..., gt=0, description="Must be > 0")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    approved_merchant_ids: list[str] = Field(..., min_length=1)
    require_approval: bool = True

    @field_validator("max_per_order_cents")
    @classmethod
    def cap_le_budget(cls, v: int, info) -> int:
        budget = info.data.get("total_budget_cents")
        if budget and v > budget:
            raise ValueError("max_per_order_cents must be ≤ total_budget_cents")
        return v


# ── Product ───────────────────────────────────────────────────────────────────

class ProductRead(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str
    merchant_id: str
    merchant_name: str
    features: list[str]
    active: bool

    model_config = {"from_attributes": True}


# ── Proposal ──────────────────────────────────────────────────────────────────

class ProposeRequest(BaseModel):
    user_request: str = Field(..., max_length=1000)

    @field_validator("user_request")
    @classmethod
    def validate_user_request(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 3:
            raise ValueError("user_request must contain at least 3 non-whitespace characters")
        return stripped


class ProposalRead(BaseModel):
    id: str
    user_request: str
    selected_product_id: Optional[str]
    product: Optional[ProductRead]
    rationale: str
    status: str
    policy_decision: Literal["ALLOWED", "BLOCKED"]
    decision_reasons: list[str]
    decision_explanations: list[str]
    ai_mode: Literal["live", "fallback"]
    block_explanation: Optional[str] = None
    alternatives: list[ProposalRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Payment ───────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    proposal_id: str
    # user_approved must be True — explicit consent signal from frontend
    user_approved: bool = Field(..., description="Must be True — explicit user approval required")

    @field_validator("user_approved")
    @classmethod
    def must_be_approved(cls, v: bool) -> bool:
        if not v:
            raise ValueError("user_approved must be True — no payment without explicit user consent")
        return v


class CreateOrderResponse(BaseModel):
    payment_id: str
    paypal_order_id: str
    approve_url: str
    status: str


class CaptureOrderRequest(BaseModel):
    paypal_order_id: str


class PaymentRead(BaseModel):
    id: str
    proposal_id: str
    paypal_order_id: Optional[str]
    amount_cents: int
    currency: str
    status: str
    paypal_capture_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CancelOrderRequest(BaseModel):
    paypal_order_id: str


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEventRead(BaseModel):
    id: int
    event_type: str
    proposal_id: Optional[str]
    payment_id: Optional[str]
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}
