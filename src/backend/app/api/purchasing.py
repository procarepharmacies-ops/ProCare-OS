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


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: int, session: Session = Depends(get_session)):
    result = purchasing.set_draft_status(session, draft_id, "approved")
    if result is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return result


@router.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: int, session: Session = Depends(get_session)):
    result = purchasing.set_draft_status(session, draft_id, "rejected")
    if result is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return result


class PurchaseLineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)
    buy_price: float = Field(ge=0)
    sell_price: float | None = None
    bonus: float = 0.0
    disc_money: float = Field(0.0, ge=0)  # per-line cash discount (خصم نقدي)
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


class PurchaseReturnLineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)


class PurchaseReturnIn(BaseModel):
    lines: list[PurchaseReturnLineIn] | None = None  # None => everything returnable
    is_credit: bool = True


@router.post("/purchases/{purchase_id}/return")
def return_purchase(purchase_id: int, payload: PurchaseReturnIn, session: Session = Depends(get_session)):
    from app.services.pos import POSError

    try:
        ret = purchasing.create_purchase_return(
            session,
            purchase_id,
            [l.model_dump() for l in payload.lines] if payload.lines else None,
            is_credit=payload.is_credit,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return {
        "return_id": ret.purchase_id,
        "original_purchase_id": purchase_id,
        "total_returned": float(ret.total_gross),
        "lines": len(ret.lines),
    }


@router.get("/budget")
def budget(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    """Today's purchasing budget: 80% (PURCHASE_BUDGET_PCT) of avg daily sales."""
    from app.services import autopurchase

    return autopurchase.daily_budget(session, branch_id or None)


@router.get("/auto-proposal")
def auto_proposal(
    branch_id: int | None = Query(None),
    cover_days: int = Query(14, ge=3, le=90),
    session: Session = Depends(get_session),
):
    """Preview the predictive, budget-capped purchase proposal (no writes)."""
    from app.services import autopurchase

    return autopurchase.propose(session, branch_id or None, cover_days=cover_days)


@router.get("/plan")
def plan(branch_id: int = Query(...), session: Session = Depends(get_session)):
    """كشكول نواقص الفرع بأولوية الشراء: رصيد صفر ← طلب عميل ← تحت الحد الأدنى.
    Each row says transfer-from-branch (preferred) or buy."""
    from app.services import autopurchase

    return autopurchase.purchase_plan(session, branch_id)


@router.get("/plan/consolidated")
def plan_consolidated(session: Session = Depends(get_session)):
    """طلبية شراء مجمعة لكل الفروع (transfer-first rows excluded) تحت ميزانية 80%."""
    from app.services import autopurchase

    return autopurchase.consolidated_plan(session)


@router.post("/auto-generate")
def auto_generate(
    branch_id: int = Query(...),
    cover_days: int = Query(14, ge=3, le=90),
    session: Session = Depends(get_session),
):
    """Write the predictive proposal as approvable PurchaseOrderDraft rows."""
    from app.services import autopurchase

    return autopurchase.generate_drafts(session, branch_id, cover_days=cover_days)
