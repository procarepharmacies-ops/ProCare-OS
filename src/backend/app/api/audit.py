"""In-system audit endpoints — the cash-flow & inventory report, computed live
from ProCare's own database (mirroring both eStock stores once sync is on)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/cash-report")
def cash_report(
    months: int = Query(3, ge=1, le=24),
    vendor: str | None = Query(None, description="Vendor focus (substring, ar/en); default = biggest payable"),
    session: Session = Depends(get_session),
):
    return audit.cash_report(session, months=months, vendor_query=vendor)


@router.get("/auth-events")
def auth_events(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """Security audit trail (سجل الدخول): recent logins, failures, resets and
    password changes, newest first. Router-level guard = management only."""
    from sqlalchemy import select

    from app.db import models as m

    rows = session.scalars(
        select(m.AuthEvent).order_by(m.AuthEvent.created_at.desc(), m.AuthEvent.event_id.desc()).limit(limit)
    ).all()
    return {
        "events": [
            {
                "event_id": e.event_id,
                "username": e.username,
                "employee_id": e.employee_id,
                "event": e.event,
                "ip": e.ip,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
    }
