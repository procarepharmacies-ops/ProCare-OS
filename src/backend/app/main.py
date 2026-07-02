"""ProCare OS — FastAPI backend.

ProCare's own, independent system of record. It runs standalone on its own
database (SQLite in dev, SQL Server in production) and exposes the dashboard,
inventory, customers/vendors, POS write-path, automation alerts and the Arabic
AI assistant.

eStock and Titan/Drug-Eye are read-only *sources* reached only by the
``app.services.etl`` adapter (Phase 1 mirror) — never written to. When no live
eStock login is configured the system runs on its own seeded demo data so the
whole stack is runnable offline.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.db.base import SessionLocal, engine
from app.db.migrate import bootstrap_ceo_if_configured, ensure_role_column
from app.db.seed import ensure_seeded
from app.services import sync


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Patch pre-login-feature databases: adds employees.role if a pharmacy's
    # table predates it (create_all only creates missing tables, never alters
    # existing ones). Safe no-op on a fresh DB or one that already has it.
    ensure_role_column(engine)
    # Create the schema and seed demo data on first run (idempotent). In
    # production with a live eStock login this is replaced by the read-only ETL.
    ensure_seeded()
    # eStock sync never mirrors employees, so a freshly-synced production DB
    # has no login at all unless BOOTSTRAP_CEO_USERNAME/PASSWORD are set.
    with SessionLocal() as session:
        bootstrap_ceo_if_configured(session)
    # Start the continuous eStock→ProCare sync when enabled (SYNC_ENABLED + a
    # read-only eStock source configured); otherwise it stays idle.
    sync.start()
    try:
        yield
    finally:
        sync.stop()


app = FastAPI(
    title="ProCare OS API",
    version="1.0.0",
    description="Independent pharmacy OS backend — dashboard, POS, automation, Arabic AI assistant.",
    lifespan=lifespan,
)

# CORS. In dev the Next.js server runs on :3000. In a deployment the frontend
# proxies /api to the backend server-side (same origin), so CORS isn't strictly
# needed — but allow it to be configured for setups that call the API directly.
# Set PROCARE_CORS_ORIGINS to a comma-separated list, or "*" to allow any origin.
_cors_env = os.environ.get("PROCARE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").strip()
_allow_all = _cors_env == "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else [o.strip() for o in _cors_env.split(",") if o.strip()],
    # "*" origins and credentials can't be combined per the CORS spec; the app
    # uses no cookies/auth, so dropping credentials in that mode is safe.
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["meta"])
def root():
    return {
        "app": "ProCare OS API",
        "version": app.version,
        "status": "ok",
        "docs": "/docs",
        "phase": "1–2 — dashboard, POS, automation, AI assistant on ProCare's own DB",
    }
