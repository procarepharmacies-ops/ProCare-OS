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
from app.db.migrate import (
    bootstrap_ceo_if_configured,
    ensure_assigned_agent_column,
    ensure_customer_address_column,
    ensure_employee_reset_columns,
    ensure_loyalty_points_column,
    ensure_original_sale_id_column,
    ensure_prescription_status_columns,
    ensure_product_classification_columns,
    ensure_product_unit_columns,
    ensure_role_column,
    ensure_roster,
    ensure_shelf_location_column,
    ensure_task_priority_columns,
    ensure_titan_match_columns,
)
from app.db.seed import ensure_seeded
from app.services import scheduler, sync


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Patch pre-login-feature databases: adds employees.role if a pharmacy's
    # table predates it (create_all only creates missing tables, never alters
    # existing ones). Safe no-op on a fresh DB or one that already has it.
    ensure_role_column(engine)
    ensure_original_sale_id_column(engine)
    ensure_shelf_location_column(engine)
    ensure_loyalty_points_column(engine)
    ensure_task_priority_columns(engine)
    ensure_prescription_status_columns(engine)
    ensure_employee_reset_columns(engine)
    ensure_titan_match_columns(engine)
    ensure_product_unit_columns(engine)
    ensure_product_classification_columns(engine)
    ensure_customer_address_column(engine)
    ensure_assigned_agent_column(engine)
    # Daily safety net: the pharmacy never opens without a fresh backup.
    from app.services import backup

    backup.backup_if_stale(24, "startup-daily")
    # Create the schema and seed demo data on first run (idempotent). In
    # production with a live eStock login this is replaced by the read-only ETL.
    ensure_seeded()
    # eStock sync never mirrors employees, so a freshly-synced production DB
    # has no login at all unless BOOTSTRAP_CEO_USERNAME/PASSWORD are set.
    with SessionLocal() as session:
        bootstrap_ceo_if_configured(session)
        # The pharmacy's real staff accounts (create-only, survives restarts).
        ensure_roster(session)
        # This week's recurring operations tasks (stocktake, merchandising,
        # expiry sweep, reorder review) — created once per ISO week per branch.
        from app.services import tasks as tasks_svc

        tasks_svc.ensure_weekly_ops_tasks(session)
        # Today's daily operations checklist (opening/closing/inventory), once
        # per day per branch, auto-assigned by role where the template names one.
        tasks_svc.ensure_daily_ops_tasks(session)
    # Start the continuous eStock→ProCare sync when enabled (SYNC_ENABLED + a
    # read-only eStock source configured); otherwise it stays idle.
    sync.start()
    # Start the automation scheduler (expiry alerts / auto-purchase drafts /
    # auto-reports) when AUTOMATION_ENABLED is set and APScheduler is installed;
    # otherwise it stays idle and jobs remain fireable on demand.
    scheduler.start()
    # Index business knowledge graph (docs, schemas, findings).
    from app.services import knowledge as knowledge_svc
    knowledge_svc.refresh()
    try:
        yield
    finally:
        sync.stop()
        scheduler.shutdown()


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
_cors_env = os.environ.get("PROCARE_CORS_ORIGINS", "http://localhost:3100,http://localhost:3000,http://localhost:3001,http://127.0.0.1:3100,http://127.0.0.1:3000,http://127.0.0.1:3001").strip()
_allow_all = _cors_env == "*"
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # Allow all origins (browser will include Origin header)
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,  # Cookies/auth not used
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
