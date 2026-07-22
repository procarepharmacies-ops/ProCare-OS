"""Notification center + ticker API (Phase 6).

GET  /api/notifications          — full center, events grouped by category
GET  /api/notifications/ticker   — flat, severity-ranked ribbon feed + counts
POST /api/notifications/dismiss  — dismiss one or more events by key

Read-only against operational state (any logged-in employee).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def center(
    branch_id: int | None = Query(None),
    expiry_days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return svc.notification_center(session, branch_id or None, expiry_days)


@router.get("/ticker")
def ticker(
    branch_id: int | None = Query(None),
    limit: int = Query(12, ge=1, le=50),
    expiry_days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return svc.ticker(session, branch_id or None, limit, expiry_days)


class DismissIn(BaseModel):
    event_keys: list[str]
    branch_id: int | None = None
    by: int | None = None


@router.post("/dismiss")
def dismiss(payload: DismissIn, session: Session = Depends(get_session)):
    return svc.dismiss(session, payload.event_keys, payload.branch_id, payload.by)
