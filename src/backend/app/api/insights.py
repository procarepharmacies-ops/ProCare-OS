"""Owner intelligence endpoints: daily report + staff productivity."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/daily")
def daily(
    branch_id: int | None = Query(None),
    on: date | None = Query(None),
    session: Session = Depends(get_session),
):
    """End-of-day sheet: sales, returns, visitors + conversion, tasks, alerts."""
    return insights.daily_report(session, branch_id, on)


@router.get("/productivity")
def productivity(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    session: Session = Depends(get_session),
):
    """Per-employee POS activity: bills, revenue, hourly rhythm, peak hours."""
    return insights.productivity(session, branch_id, days)
