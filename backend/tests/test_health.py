"""
tests/test_health.py — Phase 1 health endpoint tests.
"""


from unittest.mock import patch
from app.config import Settings


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_health_shows_fallback_when_ai_unconfigured(client):
    with patch("app.routers.health.get_settings") as mock_settings:
        mock_settings.return_value = Settings(ai_api_key="", ai_provider="none")
        response = client.get("/api/health")
        body = response.json()
        assert body["ai_configured"] is False


def test_health_shows_paypal_unconfigured(client):
    with patch("app.routers.health.get_settings") as mock_settings:
        mock_settings.return_value = Settings(paypal_client_id="", paypal_client_secret="")
        response = client.get("/api/health")
        body = response.json()
        assert body["paypal_configured"] is False


def test_health_contains_sandbox_note(client):
    response = client.get("/api/health")
    body = response.json()
    assert "sandbox" in body["note"].lower() or "Sandbox" in body["note"]


def test_health_does_not_leak_secrets(client):
    response = client.get("/api/health")
    body = response.json()
    text = str(body)
    # Ensure no secret-looking values appear in the response
    forbidden = ["PAYPAL_CLIENT_SECRET", "AI_API_KEY", "sk-", "Bearer "]
    for term in forbidden:
        assert term not in text, f"Potential secret '{term}' found in health response"
