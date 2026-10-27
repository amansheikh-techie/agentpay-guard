"""
services/audit_service.py — Immutable event logging helper.
"""
from sqlalchemy.orm import Session
from app.models import AuditEvent


def log(
    db: Session,
    event_type: str,
    details: dict,
    proposal_id: str | None = None,
    payment_id: str | None = None,
) -> AuditEvent:
    """
    Record an audit event.
    Never log raw API keys, secrets, or full PayPal tokens.
    """
    event = AuditEvent(
        event_type=event_type,
        proposal_id=proposal_id,
        payment_id=payment_id,
    )
    event.details = details
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
