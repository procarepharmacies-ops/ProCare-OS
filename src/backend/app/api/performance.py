"""Performance-over-time, audit and supplier-purchasing endpoints.

Management-only (mounted under an owner/manager guard in ``routes``). Every
figure is derived from ProCare's own tables after the SQL Server Express / eStock
sync, and matches ``sql/performance-analysis.sql`` run directly on the database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import performance

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/overview")
def overview(
    years: int = Query(5, ge=1, le=15),
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Multi-year performance: revenue, profit, invoices, customers, cash,
    purchasing and stock — per year and per month, with a current snapshot."""
    return performance.overview(session, years=years, branch_id=branch_id)


@router.get("/audit")
def audit(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Post-sync data-quality / reconciliation audit report."""
    return performance.audit(session, branch_id=branch_id)


@router.get("/vendor")
def vendor(
    query: str = Query("pharmaoverseas", description="Vendor name (any language) or id"),
    years: int = Query(5, ge=1, le=15),
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Purchasing investigation for one supplier (PharmaOverseas by default):
    spend/orders/items per year, top products, payable, and vendor ranking."""
    return performance.vendor_purchasing(session, query=query, years=years, branch_id=branch_id)
