"""Purchase order endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import purchasing

router = APIRouter(prefix="/purchasing", tags=["purchasing"])


@router.get("/purchases")
def purchases(
    branch_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"purchases": purchasing.list_purchases(session, branch_id, limit)}


@router.get("/purchases/{purchase_id}")
def purchase_detail(
    purchase_id: int,
    session: Session = Depends(get_session),
):
    result = purchasing.purchase_detail(session, purchase_id)
    if not result:
        return {"error": "Purchase not found"}
    return result


@router.get("/drafts")
def purchase_drafts(
    branch_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"drafts": purchasing.list_purchase_drafts(session, branch_id, limit)}


@router.get("/summary")
def purchasing_summary(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return purchasing.purchase_summary(session, branch_id)
