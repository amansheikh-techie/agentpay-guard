"""
models.py — SQLAlchemy ORM models.

Money is always stored as integer cents (minor units) to avoid
IEEE-754 floating-point errors in monetary calculations.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Policy(Base):
    """Single-row spending policy for the demo user."""
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    total_budget_cents = Column(Integer, nullable=False)          # e.g. 10000 = $100.00
    max_per_order_cents = Column(Integer, nullable=False)         # e.g. 4000  = $40.00
    currency = Column(String(3), nullable=False, default="USD")
    _approved_merchant_ids = Column("approved_merchant_ids", Text, nullable=False, default="[]")
    require_approval = Column(Boolean, nullable=False, default=True)
    successful_spend_cents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    @property
    def approved_merchant_ids(self) -> list[str]:
        return json.loads(self._approved_merchant_ids)

    @approved_merchant_ids.setter
    def approved_merchant_ids(self, value: list[str]):
        self._approved_merchant_ids = json.dumps(value)

    @property
    def remaining_budget_cents(self) -> int:
        return self.total_budget_cents - self.successful_spend_cents


class Product(Base):
    """Authoritative demo catalogue entry."""
    __tablename__ = "products"

    id = Column(String(64), primary_key=True)                     # stable slug, e.g. "nexus-wireless-mouse"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    price_cents = Column(Integer, nullable=False)                  # always in cents
    currency = Column(String(3), nullable=False, default="USD")
    merchant_id = Column(String(64), nullable=False)
    merchant_name = Column(String(200), nullable=False)
    _features = Column("features", Text, nullable=False, default="[]")
    active = Column(Boolean, nullable=False, default=True)

    @property
    def features(self) -> list[str]:
        return json.loads(self._features)

    @features.setter
    def features(self, value: list[str]):
        self._features = json.dumps(value)


class Proposal(Base):
    """AI-generated purchase proposal and policy verdict."""
    __tablename__ = "proposals"

    id = Column(String(64), primary_key=True)
    user_request = Column(Text, nullable=False)
    selected_product_id = Column(String(64), ForeignKey("products.id"), nullable=True)
    rationale = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="pending")    # pending | approved | rejected
    policy_decision = Column(String(16), nullable=False, default="BLOCKED")  # ALLOWED | BLOCKED
    _decision_reasons = Column("decision_reasons", Text, nullable=False, default="[]")
    _decision_explanations = Column("decision_explanations", Text, nullable=False, default="[]")
    ai_mode = Column(String(16), nullable=False, default="fallback")   # live | fallback
    created_at = Column(DateTime(timezone=True), default=_now)

    product = relationship("Product", foreign_keys=[selected_product_id])
    payments = relationship("Payment", back_populates="proposal")

    @property
    def decision_reasons(self) -> list[str]:
        return json.loads(self._decision_reasons)

    @decision_reasons.setter
    def decision_reasons(self, value: list[str]):
        self._decision_reasons = json.dumps(value)

    @property
    def decision_explanations(self) -> list[str]:
        return json.loads(self._decision_explanations)

    @decision_explanations.setter
    def decision_explanations(self, value: list[str]):
        self._decision_explanations = json.dumps(value)


class Payment(Base):
    """PayPal Sandbox order and capture record."""
    __tablename__ = "payments"

    id = Column(String(64), primary_key=True)
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=False)
    paypal_order_id = Column(String(128), nullable=True, unique=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    # Possible statuses: pending | approved | captured | cancelled | failed | needs_verification
    status = Column(String(32), nullable=False, default="pending")
    paypal_capture_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    proposal = relationship("Proposal", back_populates="payments")


class AuditEvent(Base):
    """Immutable log of every significant system event."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False)               # e.g. PROPOSAL_CREATED, POLICY_DECISION, PAYMENT_CAPTURED
    proposal_id = Column(String(64), nullable=True)
    payment_id = Column(String(64), nullable=True)
    _details = Column("details", Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now)

    @property
    def details(self) -> dict:
        return json.loads(self._details)

    @details.setter
    def details(self, value: dict):
        self._details = json.dumps(value)
