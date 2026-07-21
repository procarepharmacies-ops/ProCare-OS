"""Sales-rep commission calculator API (Phase 6).

GET  /api/commissions/preview          — read-only commission preview for a period
GET  /api/commissions/runs             — recent posted/void runs
POST /api/commissions/runs             — post (persist) a commission run
GET  /api/commissions/runs/{run_id}    — one run with its rep lines
POST /api/commissions/runs/{run_id}/void — void a posted run (audit-safe)

Manager/CEO only (payroll data). Rates are always in percent.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import commissions as svc

router = APIRouter(prefix="/commissions", tags=["commissions"])


class RepRate(BaseModel):
    employee_id: int
    rate_pct: float


class PostRunIn(BaseModel):
    period_start: date
    period_end: date
    branch_id: int | None = None
    default_rate_pct: float = Field(0.0, ge=0)
    rep_rates: list[RepRate] = []
    note: str | None = None
    posted_by: int | None = None


def _parse_period(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_period", "message": "period_end must be on or after period_start"},
        )


@router.get("/preview")
def preview(
    period_start: date,
    period_end: date,
    branch_id: int | None = None,
    default_rate_pct: float = Query(0.0, ge=0),
    session: Session = Depends(get_session),
):
    """Compute (without saving) each rep's net sales and commission for the
    period. Per-rep overrides are only applied when a run is posted; the
    preview uses the single ``default_rate_pct`` so the manager sees the base
    before tuning individuals."""
    _parse_period(period_start, period_end)
    return svc.compute_commissions(
        session, period_start, period_end, branch_id, default_rate_pct
    )


@router.get("/runs")
def list_runs(
    branch_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    """Recent commission runs (headers), newest first."""
    return svc.list_runs(session, branch_id, limit)


@router.post("/runs")
def post_run(payload: PostRunIn, session: Session = Depends(get_session)):
    """Persist a commission run: recomputes from live sales and snapshots each
    rep's payout. Returns the saved run with its lines."""
    _parse_period(payload.period_start, payload.period_end)
    rep_rates = {r.employee_id: r.rate_pct for r in payload.rep_rates}
    return svc.post_commission_run(
        session,
        payload.period_start,
        payload.period_end,
        payload.branch_id,
        payload.default_rate_pct,
        rep_rates,
        payload.note,
        payload.posted_by,
    )


@router.get("/runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)):
    """One commission run with its per-rep lines."""
    run = svc.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Commission run not found"})
    return run


@router.post("/runs/{run_id}/void")
def void_run(run_id: int, session: Session = Depends(get_session)):
    """Void a posted run (kept for the audit trail). Idempotent."""
    run = svc.void_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Commission run not found"})
    return run
