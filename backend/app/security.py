"""
security.py — Administrative authorization dependencies.
"""
from __future__ import annotations
import secrets
from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None)) -> bool:
    """
    Enforce administrative authorization on sensitive configuration endpoints.

    Rules:
      1. When APP_ENV is "development", access is allowed without an admin token.
      2. In non-development environments, the X-Admin-Token header must match ADMIN_TOKEN
         using a constant-time comparison (secrets.compare_digest).
    """
    settings = get_settings()

    # In development mode, open access is allowed for local ease of testing
    if settings.app_env.lower() == "development":
        return True

    configured_token = settings.admin_token
    if not configured_token:
        # If admin_token is not configured in non-development mode, deny access
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication is not configured on this server.",
        )

    if not x_admin_token or not secrets.compare_digest(x_admin_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Token header.",
        )

    return True

