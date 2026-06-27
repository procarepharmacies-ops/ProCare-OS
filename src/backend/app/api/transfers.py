"""Stock transfer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import transfers

router = APIRouter(prefix="/transfers", tags=["transfers"])


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
