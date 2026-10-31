"""
routers/audit.py — GET /api/audit

Returns recent audit events in descending time order.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventRead

router = APIRouter()


@router.get("/audit", response_model=list[AuditEventRead], tags=["audit"])
def get_audit(
    limit: int = Query(default=50, le=200),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return the most recent audit events, newest first."""
    query = db.query(AuditEvent)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    events = (
        query
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return events
