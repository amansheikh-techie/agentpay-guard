"""
tests/conftest.py — Shared pytest fixtures.

Uses an in-memory SQLite database so tests never touch the dev DB.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=test_engine)
    from app.seed import seed_if_empty
    db = TestSessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_test_db(setup_tables):
    """Ensure each test runs with clean database records."""
    db = TestSessionLocal()
    try:
        from app.models import Payment, Proposal, AuditEvent, Policy
        from app.seed import DEFAULT_POLICY
        db.query(Payment).delete()
        db.query(Proposal).delete()
        db.query(AuditEvent).delete()
        policy = db.query(Policy).first()
        if policy:
            policy.total_budget_cents = DEFAULT_POLICY["total_budget_cents"]
            policy.max_per_order_cents = DEFAULT_POLICY["max_per_order_cents"]
            policy.currency = DEFAULT_POLICY["currency"]
            policy.approved_merchant_ids = DEFAULT_POLICY["approved_merchant_ids"]
            policy.require_approval = DEFAULT_POLICY["require_approval"]
            policy.successful_spend_cents = 0
            policy.daily_limit_cents = 0
            policy.monthly_limit_cents = 0
            policy.blocked_categories = []
            policy.agent_enabled = True
            policy.policy_version = 1
            policy.last_reset_at = None
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def mock_ai_fallback(monkeypatch):
    """Ensure tests run deterministically in fast offline fallback mode without network timeouts."""
    from app import config
    settings = config.get_settings()
    monkeypatch.setattr(settings, "ai_provider", "none")


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
