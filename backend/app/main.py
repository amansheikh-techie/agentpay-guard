"""
main.py — FastAPI application entry point.

Mounts all routers and configures CORS.
Reads FRONTEND_ORIGIN from env; never hard-codes secrets.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base, SessionLocal, run_sqlite_migrations
from app.routers import health, policy, products, audit, agent, payments, summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run safe schema migrations for existing databases
    run_sqlite_migrations(engine)
    # Create all tables on startup (no-op if they already exist)
    Base.metadata.create_all(bind=engine)
    # Seed demo catalogue and default policy if empty
    from app.seed import seed_if_empty
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
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
app.include_router(policy.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(agent.router, prefix="/api/agent")
app.include_router(payments.router, prefix="/api/payments")
app.include_router(summary.router, prefix="/api")

# ── Static SPA Serving (Render / Production Single-Service) ───────────────────
import os
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = os.path.join(frontend_dist, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"status": "ok", "message": "AgentPay Guard API online"}


