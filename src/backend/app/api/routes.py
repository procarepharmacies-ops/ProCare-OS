"""ProCare OS API — Phase 1 (read-only shadow mode).

All endpoints read ProCare's own clean database. In demo mode that DB is the
seeded SQLite shadow; in production it is the SQL Server system of record. The
Arabic AI assistant and the ETL/reconcile endpoints obey the project guardrails
(read-only, advisory clinical output, draft-only reorder, no secrets exposed).
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app import alerts, drugs, etl, queries, scheduler
from app import ai as ai_engine
from app.config import settings
from app.db import get_db

router = APIRouter()

Branch = Query("ALL", description="Branch code (MAIN / ELSANTA), branch_id, or ALL")


# -- meta --------------------------------------------------------------------
@router.get("/health", tags=["meta"])
def health():
    """Liveness + configuration status. Never returns secrets."""
    db = get_db()
    return {
        "status": "ok",
        "phase": "1 — mirror & read (shadow mode)",
        "data_backend": db.mode,  # 'demo' (SQLite) or 'procare' (SQL Server)
        "using_example_config": settings.using_example,
        "config_source": settings.source_file,
        "databases_configured": {
            "estock_source": settings.estock_configured,
            "titan_drugeye_source": settings.titan_configured,
            "procare_database": settings.procare_configured,
        },
        "ai_engine": ai_engine.engine_status()["engine"],
        "automation": scheduler.jobs_overview()["running"],
        "ui_defaults": {"language": settings.default_language, "theme": settings.default_theme},
    }


@router.get("/branches", tags=["branches"])
def branches():
    """The two physical branches (Main / Elsanta), enriched from the DB."""
    db = get_db()
    rows = db.query("SELECT code, name_ar, name_en, is_pilot FROM branches ORDER BY branch_id")
    if rows:
        return {"branches": [
            {"code": r["code"], "name_ar": r["name_ar"], "name_en": r["name_en"],
             "pilot": bool(r["is_pilot"])} for r in rows]}
    return {"branches": settings.branch_list()}


# -- dashboard ---------------------------------------------------------------
@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(branch: str = Branch):
    return queries.dashboard_summary(branch)


@router.get("/dashboard/daily-sales", tags=["dashboard"])
def daily_sales(branch: str = Branch, days: int = Query(30, ge=1, le=180)):
    return {"branch": branch.upper(), "days": days, "series": queries.daily_sales(branch, days)}


@router.get("/dashboard/top-products", tags=["dashboard"])
def top_products(branch: str = Branch, days: int = Query(30, ge=1, le=365),
                 limit: int = Query(10, ge=1, le=50)):
    return {"branch": branch.upper(), "days": days,
            "products": queries.top_products(branch, days, limit)}


@router.get("/dashboard/hourly", tags=["dashboard"])
def hourly(branch: str = Branch, day: str | None = None):
    return {"branch": branch.upper(), "day": day, "hours": queries.hourly_sales(branch, day)}


@router.get("/dashboard/cashiers", tags=["dashboard"])
def cashiers(branch: str = Branch, day: str | None = None):
    return {"branch": branch.upper(), "day": day,
            "cashiers": queries.cashier_performance(branch, day)}


@router.get("/dashboard/profit", tags=["dashboard"])
def profit(branch: str = Branch, date_from: str | None = None, date_to: str | None = None):
    return queries.profit(branch, date_from, date_to)


# -- alerts ------------------------------------------------------------------
@router.get("/alerts/expiry", tags=["alerts"])
def expiry(branch: str = Branch):
    return alerts.expiry_alerts(branch)


@router.get("/alerts/low-stock", tags=["alerts"])
def low_stock(branch: str = Branch):
    return alerts.reorder_drafts(branch)


@router.get("/alerts/debtors", tags=["alerts"])
def debtor_alerts():
    return alerts.debtor_alerts()


# -- inventory ---------------------------------------------------------------
@router.get("/inventory/lookup", tags=["inventory"])
def inventory_lookup(q: str = Query(..., min_length=1), branch: str = Branch):
    """FEFO batch lookup for a product by name / code / barcode."""
    return {"query": q, "branch": branch.upper(), "batches": queries.stock_lookup(q, branch)}


# -- AI assistant ------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str
    branch: str = "ALL"


@router.post("/ai/chat", tags=["ai"])
def ai_chat(req: ChatRequest):
    """Arabic NL question -> constrained read-only SQL -> Arabic answer."""
    return ai_engine.chat(req.query, req.branch)


@router.get("/ai/status", tags=["ai"])
def ai_status():
    return ai_engine.engine_status()


# -- clinical (advisory) -----------------------------------------------------
class BasketRequest(BaseModel):
    product_ids: list[int]


@router.post("/drugs/check", tags=["clinical"])
def drugs_check(req: BasketRequest):
    """Advisory pairwise interaction check for a sale basket (never blocks)."""
    return drugs.check_basket(req.product_ids)


@router.get("/drugs/product/{product_id}", tags=["clinical"])
def drug_product(product_id: int):
    return drugs.interactions_for_product(product_id)


@router.get("/drugs/status", tags=["clinical"])
def drugs_status():
    return drugs.status()


# -- ETL / reconciliation ----------------------------------------------------
@router.get("/etl/status", tags=["etl"])
def etl_status():
    return etl.status()


@router.post("/etl/reconcile", tags=["etl"])
def etl_reconcile(days: int = Query(7, ge=1, le=90)):
    return etl.reconcile(days)


@router.post("/etl/mirror", tags=["etl"])
def etl_mirror():
    """Refresh the mirror. In demo mode this regenerates the shadow data."""
    return etl.run_mirror()


# -- automation --------------------------------------------------------------
@router.get("/automation/jobs", tags=["automation"])
def automation_jobs():
    return scheduler.jobs_overview()


@router.post("/automation/run/{job}", tags=["automation"])
def automation_run(job: str):
    return scheduler.run_now(job)
