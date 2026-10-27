"""
main.py — FastAPI application entry point.

Mounts all routers and configures CORS.
Reads FRONTEND_ORIGIN from env; never hard-codes secrets.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (no-op if they already exist)
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()

app = FastAPI(
    title="AgentPay Guard API",
    description=(
        "Safety layer for AI-assisted purchases. "
        "Backend is the trust boundary — policy enforcement is deterministic. "
        "PayPal Sandbox only — no real money."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api")

# Additional routers will be added in later phases:
# app.include_router(policy.router, prefix="/api")
# app.include_router(products.router, prefix="/api")
# app.include_router(agent.router, prefix="/api")
# app.include_router(payments.router, prefix="/api")
# app.include_router(audit.router, prefix="/api")
