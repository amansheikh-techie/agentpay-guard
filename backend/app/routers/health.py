"""
routers/health.py — GET /api/health

Returns API status and configured integration flags.
Never returns secret values.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_env: str
    ai_configured: bool
    ai_provider: str
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
    return HealthResponse(
        status="ok",
        app_env=s.app_env,
        ai_configured=s.ai_configured,
        ai_provider=s.ai_provider if s.ai_configured else "none (fallback mode active)",
        paypal_configured=s.paypal_configured,
        paypal_mode=s.paypal_mode,
        paypal_currency=s.paypal_currency,
        note="PayPal Sandbox — test transactions only. No real money.",
    )
