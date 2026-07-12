"""Stock transfer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import pos, transfers

router = APIRouter(prefix="/transfers", tags=["transfers"])


class RequestLineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)


class TransferRequestIn(BaseModel):
    from_branch_id: int
    to_branch_id: int
    lines: list[RequestLineIn]
    requested_by: int | None = None


@router.post("/request")
def request_transfer(payload: TransferRequestIn, session: Session = Depends(get_session)):
    """Create a transfer REQUEST (no stock moves yet). Raises an approval task
    for the source-branch manager + a WhatsApp alert."""
    try:
        return transfers.request_transfer(
            session,
            payload.from_branch_id,
            payload.to_branch_id,
            [(l.product_id, l.amount) for l in payload.lines],
            requested_by=payload.requested_by,
        )
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.post("/{transfer_id}/approve", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def approve_transfer(transfer_id: int, approved_by: int | None = None, session: Session = Depends(get_session)):
    """Approve a requested transfer: move the stock now and mark it received."""
    try:
        return transfers.approve_transfer(session, transfer_id, approved_by=approved_by)
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.post("/{transfer_id}/reject", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def reject_transfer(transfer_id: int, session: Session = Depends(get_session)):
    try:
        return transfers.reject_transfer(session, transfer_id)
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.post("/{transfer_id}/ship", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def ship_transfer(transfer_id: int, shipped_by: int | None = None, session: Session = Depends(get_session)):
    """Source releases the goods (requested -> in_transit). Stock leaves the
    source now; the destination must confirm receipt to complete it."""
    try:
        return transfers.ship_transfer(session, transfer_id, shipped_by=shipped_by)
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


class ReceiveLineIn(BaseModel):
    line_id: int
    amount: float = Field(ge=0)
    exp_date: str | None = None


class ReceiveIn(BaseModel):
    received_by: int | None = None
    lines: list[ReceiveLineIn] = []


@router.post("/{transfer_id}/receive", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def receive_transfer(transfer_id: int, payload: ReceiveIn, session: Session = Depends(get_session)):
    """Destination confirms receipt (استلام الإذن): review each line's expiry +
    quantity, then the stock enters destination inventory (in_transit ->
    received). Omitted lines are accepted as shipped."""
    confirmations = {
        l.line_id: {"amount": l.amount, "exp_date": l.exp_date} for l in payload.lines
    }
    try:
        return transfers.receive_transfer(
            session, transfer_id, confirmations, received_by=payload.received_by
        )
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("/list")
def transfer_list(
    branch_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"transfers": transfers.list_transfers(session, branch_id, status, limit)}


@router.get("/{transfer_id}")
def transfer_detail(
    transfer_id: int,
    session: Session = Depends(get_session),
):
    result = transfers.transfer_detail(session, transfer_id)
    if not result:
        return {"error": "Transfer not found"}
    return result


@router.get("/summary")
def transfer_summary(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return transfers.transfer_summary(session, branch_id)
