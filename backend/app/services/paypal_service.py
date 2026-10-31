"""
services/paypal_service.py — PayPal Sandbox Orders v2 API integration.

Security Rules:
- SANDBOX ONLY. Never connects to live PayPal endpoints.
- Client secret is read only on the server from backend configuration.
- Client secret is NEVER exposed to the frontend, logs, or API responses.
- Authoritative order amount is always passed in cents and safely converted to decimal string.
- Idempotency keys (PayPal-Request-Id) protect against duplicate charges.
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Any
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Token cache: (token, expiry_timestamp)
_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0}


class PayPalError(Exception):
    """Custom exception for safe PayPal error handling."""
    def __init__(self, message: str, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def get_access_token() -> str:
    """
    Obtain OAuth 2.0 access token via Client Credentials Grant.
    Uses in-memory caching to avoid redundant token requests.
    """
    settings = get_settings()
    if not settings.paypal_configured:
        raise PayPalError(
            "PayPal Sandbox credentials are not configured. "
            "Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in backend/.env."
        )

    now = time.time()
    if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expires_at"] > now + 60:
        return _TOKEN_CACHE["token"]

    url = f"{settings.paypal_base_url.rstrip('/')}/v1/oauth2/token"
    auth = (settings.paypal_client_id, settings.paypal_client_secret)
    data = {"grant_type": "client_credentials"}
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, auth=auth, data=data, headers=headers)
            if resp.status_code != 200:
                logger.error("PayPal OAuth failed with status %s", resp.status_code)
                raise PayPalError(
                    f"PayPal authentication failed ({resp.status_code}). Check sandbox credentials.",
                    status_code=resp.status_code,
                )
            token_data = resp.json()
            token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 3600))
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return token
    except httpx.RequestError as exc:
        logger.error("PayPal network error during OAuth: %s", exc)
        raise PayPalError("Unable to reach PayPal Sandbox. Please check network connection.")


def create_order(
    amount_cents: int,
    currency: str,
    reference_id: str,
    description: str,
    return_url: str,
    cancel_url: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a PayPal Orders v2 order with intent=CAPTURE.
    Amount is strictly derived from integer cents (e.g. 2999 -> "29.99").
    """
    settings = get_settings()
    token = get_access_token()
    req_id = request_id or str(uuid.uuid4())

    url = f"{settings.paypal_base_url.rstrip('/')}/v2/checkout/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": req_id,
        "Prefer": "return=representation",
    }

    decimal_amount = f"{amount_cents / 100:.2f}"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": reference_id,
                "description": description[:120],
                "amount": {
                    "currency_code": currency.upper(),
                    "value": decimal_amount,
                },
            }
        ],
        "application_context": {
            "brand_name": "AgentPay Guard Sandbox",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                logger.error("PayPal create_order returned status %s", resp.status_code)
                error_msg = "PayPal order creation failed."
                try:
                    data = resp.json()
                    error_msg = data.get("message", error_msg)
                except Exception:
                    pass
                raise PayPalError(error_msg, status_code=resp.status_code)
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("PayPal network error during create_order: %s", exc)
        raise PayPalError("Network timeout connecting to PayPal Sandbox.")


def capture_order(paypal_order_id: str, request_id: str | None = None) -> dict[str, Any]:
    """
    Capture an approved PayPal order.
    Pre-checks order status to provide clear, actionable errors.
    Idempotent via PayPal-Request-Id.
    """
    settings = get_settings()
    token = get_access_token()

    # ── Pre-flight: verify the order is in APPROVED state ──────────────
    order_details = get_order_details(paypal_order_id)
    order_status = order_details.get("status", "UNKNOWN")

    if order_status == "COMPLETED":
        # Already captured — return existing data for idempotency
        logger.info("Order %s is already COMPLETED; returning existing data.", paypal_order_id)
        return order_details

    if order_status != "APPROVED":
        logger.warning(
            "Cannot capture order %s: status is '%s', expected 'APPROVED'. "
            "The buyer must complete approval at PayPal before capture.",
            paypal_order_id, order_status,
        )
        raise PayPalError(
            f"Order cannot be captured because its status is '{order_status}'. "
            f"The buyer must first complete checkout approval at PayPal Sandbox. "
            f"Please click the PayPal approval link, log in with a Sandbox buyer "
            f"account, and approve the payment before clicking Capture.",
            status_code=422,
            details={"issue": "ORDER_NOT_APPROVED", "order_status": order_status},
        )

    # ── Capture the approved order ─────────────────────────────────────
    req_id = request_id or f"cap_{uuid.uuid4()}"
    url = f"{settings.paypal_base_url.rstrip('/')}/v2/checkout/orders/{paypal_order_id}/capture"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": req_id,
        "Prefer": "return=representation",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json={})
            if resp.status_code not in (200, 201):
                logger.error("PayPal capture_order returned status %s", resp.status_code)
                error_msg = "PayPal capture failed."
                details = {}
                try:
                    data = resp.json()
                    error_msg = data.get("message", error_msg)
                    # Extract the specific PayPal issue code for diagnostics
                    issues = data.get("details", [])
                    if issues:
                        issue_code = issues[0].get("issue", "")
                        issue_desc = issues[0].get("description", "")
                        if issue_code:
                            error_msg = f"{error_msg} [{issue_code}]: {issue_desc}"
                            details = {"issue": issue_code, "description": issue_desc}
                    debug_id = data.get("debug_id", "")
                    if debug_id:
                        details["debug_id"] = debug_id
                except Exception:
                    pass
                raise PayPalError(error_msg, status_code=resp.status_code, details=details)
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("PayPal network error during capture_order: %s", exc)
        raise PayPalError("Network timeout while capturing PayPal payment.")


def get_order_details(paypal_order_id: str) -> dict[str, Any]:
    """Fetch status and details of an order from PayPal."""
    settings = get_settings()
    token = get_access_token()

    url = f"{settings.paypal_base_url.rstrip('/')}/v2/checkout/orders/{paypal_order_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                raise PayPalError("Order not found on PayPal Sandbox.", status_code=resp.status_code)
            return resp.json()
    except httpx.RequestError:
        raise PayPalError("Network error checking PayPal order status.")
