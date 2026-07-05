"""Treasury endpoints: cash vouchers, branch→branch money transfers, branch
balance accounts, and the treasury statement."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import treasury
from app.services.pos import POSError

router = APIRouter(prefix="/treasury", tags=["treasury"])


class VoucherIn(BaseModel):
    branch_id: int
    amount: float = Field(gt=0)
    note: str | None = None
    party: str | None = None  # who paid / was paid
    employee_id: int | None = None


class TransferIn(BaseModel):
    from_branch_id: int
    to_branch_id: int
    amount: float = Field(gt=0)
    note: str | None = None
    employee_id: int | None = None


class AdjustIn(BaseModel):
    branch_id: int
    delta: float
    note: str
    employee_id: int | None = None


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("/balances")
def balances(session: Session = Depends(get_session)):
    return {"branches": treasury.branch_balances(session)}


@router.get("/movements")
def movements(
    branch_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"movements": treasury.recent_movements(session, branch_id or None, limit)}


@router.get("/transfers")
def transfers(
    branch_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"transfers": treasury.list_transfers(session, branch_id or None, limit)}


@router.post("/receive")
def receive(payload: VoucherIn, session: Session = Depends(get_session)):
    return _wrap(
        treasury.receive_voucher, session, payload.branch_id, payload.amount,
        note=payload.note, party=payload.party, employee_id=payload.employee_id,
    )


@router.post("/pay")
def pay(payload: VoucherIn, session: Session = Depends(get_session)):
    return _wrap(
        treasury.pay_voucher, session, payload.branch_id, payload.amount,
        note=payload.note, party=payload.party, employee_id=payload.employee_id,
    )


@router.post("/transfer")
def transfer(payload: TransferIn, session: Session = Depends(get_session)):
    return _wrap(
        treasury.transfer_money, session, payload.from_branch_id, payload.to_branch_id,
        payload.amount, note=payload.note, employee_id=payload.employee_id,
    )


@router.post("/adjust")
def adjust(payload: AdjustIn, session: Session = Depends(get_session)):
    return _wrap(
        treasury.adjust_balance, session, payload.branch_id, payload.delta,
        note=payload.note, employee_id=payload.employee_id,
    )
