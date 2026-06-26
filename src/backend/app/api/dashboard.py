"""Dashboard / KPI endpoints (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _branch(branch_id: int | None) -> int | None:
    return branch_id or None  # 0 / None => consolidated


@router.get("/summary")
def summary(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    return dashboard.summary(session, _branch(branch_id))


@router.get("/daily-sales")
def daily_sales(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    session: Session = Depends(get_session),
):
    return {"days": days, "series": dashboard.daily_sales(session, _branch(branch_id), days)}


@router.get("/top-products")
def top_products(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    return {"products": dashboard.top_products(session, _branch(branch_id), days, limit)}


@router.get("/hourly")
def hourly(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    return {"hours": dashboard.hourly_sales(session, _branch(branch_id))}


@router.get("/cashiers")
def cashiers(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    session: Session = Depends(get_session),
):
    return {"cashiers": dashboard.cashier_performance(session, _branch(branch_id), days)}
