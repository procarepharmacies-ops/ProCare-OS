"""Dashboard / KPI endpoints (read-only)."""
from __future__ import annotations

from datetime import date

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


@router.get("/monthly")
def monthly(
    branch_id: int | None = Query(None),
    months: int = Query(12, ge=1, le=36),
    session: Session = Depends(get_session),
):
    """Month-view series: revenue, bills, discount and profit per month."""
    return {"months": dashboard.monthly_sales(session, _branch(branch_id), months)}


@router.get("/by-branch")
def branch_comparison(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: Session = Depends(get_session),
):
    """Per-branch revenue/bills/discount/profit over a date range
    (defaults to the current month)."""
    return {"branches": dashboard.by_branch(session, date_from, date_to)}


@router.get("/range")
def range_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """KPIs for an arbitrary date range — the choose-your-dates view."""
    return dashboard.range_summary(session, _branch(branch_id), date_from, date_to)


@router.get("/purchasing")
def purchasing(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Daily + monthly purchasing totals and purchasing-to-sales ratio (target 79-80%)."""
    return dashboard.purchasing_summary(session, _branch(branch_id))


@router.get("/yoy")
def yoy(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Year-over-Year sales + profit: current year vs last year, month by month."""
    return dashboard.yoy_comparison(session, _branch(branch_id))


@router.get("/cash")
def cash(session: Session = Depends(get_session)):
    """Current treasury cash balance per branch (POS 1 = Elsanta / POS 2 = Mashala)."""
    return {"branches": dashboard.cash_by_branch(session)}


@router.get("/expenses")
def expenses(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Daily + monthly expenses (pay vouchers from treasury)."""
    return dashboard.expenses_summary(session, _branch(branch_id))


@router.get("/staff-now")
def staff_now(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Who is on shift right now and who is next in the handover queue."""
    return dashboard.staff_on_shift(session, _branch(branch_id))
