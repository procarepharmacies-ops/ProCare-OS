"""Automation/intelligence endpoints: expiry, low-stock, reorder, forecast."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/expiry")
def expiry(
    branch_id: int | None = Query(None),
    horizon_days: int = Query(90, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return alerts.expiry_risk(session, branch_id or None, horizon_days)


@router.get("/low-stock")
def low_stock(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    return {"items": alerts.low_stock(session, branch_id or None)}


@router.get("/reorder")
def reorder(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    return {"drafts": alerts.smart_reorder(session, branch_id or None)}


@router.get("/forecast/{product_id}")
def forecast(
    product_id: int,
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    session: Session = Depends(get_session),
):
    return alerts.forecast(session, product_id, branch_id or None, days)
