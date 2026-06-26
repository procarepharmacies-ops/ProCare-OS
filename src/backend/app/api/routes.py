"""Meta + branch endpoints, and the aggregation of all feature routers.

Health reports configuration status (never secrets). The feature routers (under
this same ``/api`` prefix) expose the dashboard, inventory, parties, POS, alerts
and AI assistant over ProCare's own database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import ai, alerts, dashboard, inventory, parties, sales
from app.config import settings
from app.db import models as m
from app.db.base import IS_SQLITE, get_session
from app.services import etl

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
            "engine": "claude" if settings.ai_api_key() else "rule-based (no API key set)",
            "model": settings.ai_model,
        },
        "ui_defaults": {"language": settings.default_language, "theme": settings.default_theme},
    }


@router.get("/branches", tags=["branches"])
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


@router.get("/etl/status", tags=["etl"])
def etl_status():
    """Read-only eStock mirror status (live vs offline) + the table mapping plan."""
    return etl.status()


@router.post("/etl/run", tags=["etl"])
def etl_run():
    """Trigger the Phase-1 full mirror from the live eStock DB into ProCare.

    Safely refuses unless a real read-only eStock login is configured. Read-only
    against eStock by construction.
    """
    return etl.run_full_load()


# Feature routers, all under /api.
router.include_router(dashboard.router)
router.include_router(inventory.router)
router.include_router(parties.router)
router.include_router(sales.router)
router.include_router(alerts.router)
router.include_router(ai.router)
