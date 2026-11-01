"""
database.py — SQLite engine and session factory.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def run_sqlite_migrations(target_engine):
    """
    Idempotent, non-destructive schema migrations for SQLite without requiring Alembic.
    Inspects existing tables and safely adds new columns if they do not yet exist.
    """
    with target_engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        if "policies" in tables:
            cols = {c["name"] for c in inspector.get_columns("policies")}
            if "daily_limit_cents" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN daily_limit_cents INTEGER NOT NULL DEFAULT 0"))
            if "monthly_limit_cents" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN monthly_limit_cents INTEGER NOT NULL DEFAULT 0"))
            if "blocked_categories" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN blocked_categories TEXT NOT NULL DEFAULT '[]'"))
            if "agent_enabled" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN agent_enabled BOOLEAN NOT NULL DEFAULT 1"))
            if "policy_version" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN policy_version INTEGER NOT NULL DEFAULT 1"))
            if "last_reset_at" not in cols:
                conn.execute(text("ALTER TABLE policies ADD COLUMN last_reset_at TIMESTAMP DEFAULT NULL"))

        if "products" in tables:
            cols = {c["name"] for c in inspector.get_columns("products")}
            if "category" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN category VARCHAR(64) NOT NULL DEFAULT 'peripherals'"))

        if "payments" in tables:
            cols = {c["name"] for c in inspector.get_columns("payments")}
            if "approval_binding" not in cols:
                conn.execute(text("ALTER TABLE payments ADD COLUMN approval_binding TEXT NOT NULL DEFAULT '{}'"))


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
