"""Cash desk endpoints — shift open/close (eStock's Cash Desk menu)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import get_session
from app.services import cashdesk
from app.services.pos import POSError

router = APIRouter(prefix="/cashdesk", tags=["cashdesk"])


class OpenIn(BaseModel):
    branch_id: int
    cashier_id: int | None = None
    opening_float: float = Field(0.0, ge=0)


class CloseIn(BaseModel):
    branch_id: int
    counted_cash: float = Field(ge=0)


@router.get("/current")
def current(branch_id: int, session: Session = Depends(get_session)):
    shift = cashdesk.current_shift(session, branch_id)
    return {"shift": cashdesk.shift_dict(shift) if shift else None}


@router.post("/open")
def open_shift(payload: OpenIn, session: Session = Depends(get_session)):
    try:
        shift = cashdesk.open_shift(
            session, payload.branch_id, cashier_id=payload.cashier_id, opening_float=payload.opening_float
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return cashdesk.shift_dict(shift)


@router.post("/close")
def close_shift(payload: CloseIn, session: Session = Depends(get_session)):
    try:
        shift = cashdesk.close_shift(session, payload.branch_id, counted_cash=payload.counted_cash)
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return cashdesk.shift_dict(shift)


@router.get("/history")
def history(branch_id: int | None = None, limit: int = 30, session: Session = Depends(get_session)):
    stmt = select(m.CashShift).order_by(m.CashShift.opened_at.desc()).limit(limit)
    if branch_id:
        stmt = stmt.where(m.CashShift.branch_id == branch_id)
    return {"shifts": [cashdesk.shift_dict(s) for s in session.scalars(stmt)]}
