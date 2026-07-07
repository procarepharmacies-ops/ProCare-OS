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
