"""Door-counter ingestion + visitor analytics.

The NVR (or any camera people-counter) pushes one event per person crossing
the door line. Most NVRs can fire an HTTP action on a line-crossing rule; point
it at ``POST /api/footfall/event``. If FOOTFALL_KEY is set in the backend's
environment, the request must carry it in the ``X-Footfall-Key`` header so a
random device on the LAN can't inflate the numbers.
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import insights

router = APIRouter(prefix="/footfall", tags=["footfall"])


class EventIn(BaseModel):
    branch_id: int
    direction: str = "in"  # in | out
    count: int = Field(1, ge=1, le=500)
    source: str | None = None  # e.g. "nvr-ch3"
    ts: datetime | None = None


@router.post("/event")
def record_event(
    payload: EventIn,
    x_footfall_key: str | None = Header(None),
    session: Session = Depends(get_session),
):
    expected = os.environ.get("FOOTFALL_KEY", "")
    if expected and x_footfall_key != expected:
        raise HTTPException(status_code=401, detail="Bad or missing X-Footfall-Key")
    try:
        return insights.record_footfall(
            session, payload.branch_id, payload.direction, payload.count, payload.source, payload.ts
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/summary")
def summary(
    branch_id: int | None = None,
    days: int = 14,
    _auth=Depends(auth_guard()),
    session: Session = Depends(get_session),
):
    return insights.footfall_summary(session, branch_id, max(1, min(days, 90)))
