"""Meta + branch endpoints, and the aggregation of all feature routers.

Health reports configuration status (never secrets). The feature routers (under
this same ``/api`` prefix) expose the dashboard, inventory, parties, POS, alerts
and AI assistant over ProCare's own database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import accounting, agents, ai, alerts, audit, auth, automation, cashdesk, catalogue, clinical, crm, dashboard, employees, footfall, forecast, incentives, insights, inventory, knowledge, marketing, parties, performance, prescriptions, purchasing, reports, sales, shortages, stocktaking, tasks, transfers, treasury, vendors
from app.api.auth import auth_guard
from app.config import settings
from app.db import models as m
from app.db.base import IS_SQLITE, get_session
from app.services import clinical as clinical_svc
from app.services import llm as llm_svc
from app.services import etl, sync

router = APIRouter()


@router.get("/health", tags=["meta"])
def health(session: Session = Depends(get_session)):
    """Liveness + configuration status. Never returns secrets."""
    products = session.scalar(select(func.count()).select_from(m.Product)) or 0
    return {
        "status": "ok",
        "using_example_config": settings.using_example,
        "config_source": settings.source_file,
        "procare_db": "sqlite (dev)" if IS_SQLITE else "sqlserver",
        "seeded_products": products,
        "databases_configured": {
            "estock_source": settings.estock_configured,
            "titan_drugeye_source": settings.titan_configured,
            "procare_database": settings.procare_configured,
        },
        "ai_assistant": {
            "engine": settings.ai_provider if llm_svc.is_configured() else "rule-based (not configured)",
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "configured": llm_svc.is_configured(),
            "base_url": settings.ai_base_url if settings.ai_provider == "ollama" else None,
        },
        "clinical_advisory": {
            "mode": "live" if clinical_svc.is_live() else "offline (curated advisory rules)",
        },
        "sync": {
            "enabled": sync.is_enabled(),
            "configured": sync.is_configured(),
            "interval_seconds": sync.interval_seconds(),
        },
        "auth": {"enabled": settings.auth_enabled},
        "ui_defaults": {"language": settings.default_language, "theme": settings.default_theme},
    }


@router.get("/branches", tags=["branches"], dependencies=[Depends(auth_guard())])
def branches(session: Session = Depends(get_session)):
    """The branches from ProCare's own DB (falls back to config if unseeded)."""
    rows = session.scalars(select(m.Branch).order_by(m.Branch.branch_id)).all()
    if rows:
        return {
            "branches": [
                {
                    "branch_id": b.branch_id,
                    "code": b.code,
                    "name_ar": b.name_ar,
                    "name_en": b.name_en,
                    "pilot": b.is_pilot,
                }
                for b in rows
            ]
        }
    return {"branches": settings.branch_list()}


@router.get("/etl/status", tags=["etl"], dependencies=[Depends(auth_guard())])
def etl_status():
    """Read-only eStock mirror status (live vs offline) + the table mapping plan."""
    return etl.status()


@router.post("/etl/run", tags=["etl"], dependencies=[Depends(auth_guard(("ceo", "manager")))])
def etl_run():
    """Trigger the Phase-1 full mirror from the live eStock DB into ProCare.

    Safely refuses unless a real read-only eStock login is configured. Read-only
    against eStock by construction.
    """
    return etl.run_full_load()


@router.get("/sync/status", tags=["sync"], dependencies=[Depends(auth_guard())])
def sync_status():
    """Continuous eStock→ProCare sync status (enabled, interval, last run)."""
    return sync.status()


@router.post("/sync/run", tags=["sync"], dependencies=[Depends(auth_guard(("ceo", "manager")))])
def sync_run():
    """Run one sync cycle now (in addition to the background interval)."""
    return sync.run_once()


@router.get("/sync/preflight", tags=["sync"], dependencies=[Depends(auth_guard(("ceo", "manager")))])
def sync_preflight():
    """Check the eStock connection: reachable, read-only, and which store_ids
    (branches) it exposes. Safe to run before the first sync."""
    return etl.preflight()


@router.post("/backup", tags=["backup"], dependencies=[Depends(auth_guard(("ceo", "manager")))])
def backup_now():
    """Take a database backup right now (نسخة احتياطية)."""
    from app.services import backup

    return backup.backup_now("manual")


@router.get("/backup", tags=["backup"], dependencies=[Depends(auth_guard(("ceo", "manager")))])
def backup_list():
    """List existing backups (newest first) + when the last one was taken."""
    from app.services import backup

    last = backup.last_backup_at()
    return {"backups": backup.list_backups(), "last_backup_at": last.isoformat() if last else None}


# Feature routers, all under /api.
router.include_router(auth.router)
router.include_router(dashboard.router, dependencies=[Depends(auth_guard())])
router.include_router(inventory.router, dependencies=[Depends(auth_guard())])
router.include_router(stocktaking.router, dependencies=[Depends(auth_guard())])
router.include_router(parties.router, dependencies=[Depends(auth_guard())])
router.include_router(sales.router, dependencies=[Depends(auth_guard())])
router.include_router(cashdesk.router, dependencies=[Depends(auth_guard())])
router.include_router(alerts.router, dependencies=[Depends(auth_guard())])
router.include_router(forecast.router, dependencies=[Depends(auth_guard())])
router.include_router(clinical.router, dependencies=[Depends(auth_guard())])
router.include_router(ai.router, dependencies=[Depends(auth_guard())])
router.include_router(purchasing.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
# CRM: loyalty points, per-invoice WhatsApp, marketing campaigns.
router.include_router(crm.router, dependencies=[Depends(auth_guard())])
# Financial + salary data — CEO only once AUTH_ENABLED=true (no-op otherwise).
router.include_router(accounting.router, dependencies=[Depends(auth_guard(("ceo",)))])
router.include_router(employees.router, dependencies=[Depends(auth_guard(("ceo",)))])
router.include_router(transfers.router, dependencies=[Depends(auth_guard())])
router.include_router(vendors.router, dependencies=[Depends(auth_guard())])
# Daily staff tasks (role checks live on the endpoints themselves).
router.include_router(tasks.router, dependencies=[Depends(auth_guard())])
# Employee incentives: points for selling OTC items, leaderboard.
router.include_router(incentives.router)
# Marketing & social studio: content calendar, AI copywriting, promo codes.
router.include_router(marketing.router, dependencies=[Depends(auth_guard())])
# Catalogue quality: duplicate detection + Titan enrichment review (read-only).
router.include_router(catalogue.router)
# NVR door-counter ingestion + visitor analytics (POST is key-protected via
# FOOTFALL_KEY, not bearer auth — the NVR can't do a login flow).
router.include_router(footfall.router)
# Owner intelligence: daily report + staff productivity — management only.
router.include_router(insights.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
# Performance-over-time, audit report + supplier purchasing — management only.
router.include_router(performance.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
# Prescription reader (phone camera → Gemini) + doctor-habits analytics.
router.include_router(prescriptions.router, dependencies=[Depends(auth_guard())])
# Stock-shortage sheet — any logged-in employee can add to it.
router.include_router(shortages.router, dependencies=[Depends(auth_guard())])
# Branch treasuries: vouchers, money transfers, balances — management only.
router.include_router(treasury.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
# Stock report suite with CSV export.
router.include_router(reports.router, dependencies=[Depends(auth_guard())])
# In-system cash-flow & inventory audit — management only.
router.include_router(audit.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
router.include_router(automation.router, dependencies=[Depends(auth_guard(("ceo", "manager")))])
# AgenticOS unified capabilities
router.include_router(agents.router, dependencies=[Depends(auth_guard())])
router.include_router(knowledge.router, dependencies=[Depends(auth_guard())])
