"""Purchase order endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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


class PurchaseLineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)
    buy_price: float = Field(ge=0)
    sell_price: float | None = None
    bonus: float = 0.0
    exp_date: date | None = None


class PurchaseIn(BaseModel):
    branch_id: int
    vendor_id: int
    lines: list[PurchaseLineIn]
    bill_number: str | None = None
    total_discount: float = 0.0
    total_tax: float = 0.0
    is_credit: bool = True


@router.post("/purchases")
def create_purchase(payload: PurchaseIn, session: Session = Depends(get_session)):
    from app.services.pos import POSError

    try:
        p = purchasing.create_purchase(
            session,
            payload.branch_id,
            payload.vendor_id,
            [l.model_dump() for l in payload.lines],
            bill_number=payload.bill_number,
            total_discount=payload.total_discount,
            total_tax=payload.total_tax,
            is_credit=payload.is_credit,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return {
        "purchase_id": p.purchase_id,
        "vendor_id": p.vendor_id,
        "total_gross": float(p.total_gross),
        "lines": len(p.lines),
    }
