"""
routers/health.py — GET /api/health

Returns API status and configured integration flags.
Never returns secret values.
"""
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services import ai_service

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_env: str
    ai_configured: bool
    ai_provider: str
    ai_status: str
    ai_host: Optional[str] = None
    paypal_configured: bool
    paypal_mode: str
    paypal_currency: str
    note: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """
    Returns service health and integration status.
    Safe to call publicly — no secrets are included.
    """
    s = get_settings()
    host = None
    if s.effective_ai_base_url:
        try:
            host = urlparse(s.effective_ai_base_url).hostname
        except Exception:
            host = None

    return HealthResponse(
        status="ok",
        app_env=s.app_env,
        ai_configured=s.ai_configured,
        ai_provider=s.ai_provider,
        ai_status=ai_service.get_ai_status(s),
        ai_host=host,
        paypal_configured=s.paypal_configured,
        paypal_mode=s.paypal_mode,
        paypal_currency=s.paypal_currency,
        note="PayPal Sandbox — test transactions only. No real money.",
    )
