"""Phase-0 stub endpoints. Read-only, no database required.

These exist so the frontend has something live to render. The real queries land
in Phase 1 (see ../../sql/dashboard-queries.sql and docs/06-roadmap.md).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health", tags=["meta"])
def health():
    """Liveness + configuration status. Never returns secrets."""
    return {
        "status": "ok",
        "using_example_config": settings.using_example,
        "config_source": settings.source_file,
        "databases_configured": {
            "estock_source": settings.estock_configured,
            "titan_drugeye_source": settings.titan_configured,
            "procare_database": settings.procare_configured,
        },
        "ui_defaults": {
            "language": settings.default_language,
            "theme": settings.default_theme,
        },
    }


@router.get("/branches", tags=["branches"])
def branches():
    """The two physical branches (Main / Elsanta) from config."""
    return {"branches": settings.branch_list()}


@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary():
    """Stub KPIs. Wired to the ProCare DB in Phase 1."""
    return {
        "wired_to_db": False,
        "note": "Stub data — Phase 1 ETL connects this to the ProCare database.",
        "kpis": {
            "sales_today": None,
            "sales_month": None,
            "low_stock_items": None,
            "expiring_30_days": None,
            "debtors_over_limit": None,
        },
    }
