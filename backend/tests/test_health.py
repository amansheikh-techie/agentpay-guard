"""
tests/test_health.py — Phase 1 health endpoint tests.
"""


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_health_shows_fallback_when_ai_unconfigured(client):
    response = client.get("/api/health")
    body = response.json()
    # With empty AI_API_KEY the provider must default to fallback
    assert body["ai_configured"] is False


def test_health_shows_paypal_unconfigured(client):
    response = client.get("/api/health")
    body = response.json()
    # No PayPal credentials in test env
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
