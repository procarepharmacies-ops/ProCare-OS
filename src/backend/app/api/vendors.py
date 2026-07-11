"""Vendor/supplier management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import vendors
from app.services.pos import POSError

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("/list")
def vendors_list(
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"vendors": vendors.list_vendors(session, limit)}


@router.get("/summary")
def vendor_summary(session: Session = Depends(get_session)):
    return vendors.vendor_summary(session)


@router.get("/{vendor_id}")
def vendor_detail(
    vendor_id: int,
    session: Session = Depends(get_session),
):
    result = vendors.vendor_detail(session, vendor_id)
    if not result:
        return {"error": "Vendor not found"}
    return result


@router.get("/{vendor_id}/purchases")
def vendor_purchases(
    vendor_id: int,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"purchases": vendors.vendor_purchases(session, vendor_id, limit)}


@router.get("/{vendor_id}/statement")
def vendor_statement(vendor_id: int, session: Session = Depends(get_session)):
    """كشف حساب المورد: فواتير وسدادات برصيد جارٍ."""
    result = vendors.vendor_statement(session, vendor_id)
    if result is None:
        raise HTTPException(status_code=404, detail="vendor not found")
    return result


class PayIn(BaseModel):
    branch_id: int
    amount: float = Field(gt=0)
    note: str | None = Field(None, max_length=255)
    employee_id: int | None = None


@router.post("/{vendor_id}/pay")
def pay_vendor(vendor_id: int, payload: PayIn, session: Session = Depends(get_session)):
    """صرف نقدية لمورد من خزينة الفرع (يخفض رصيده المستحق)."""
    try:
        return vendors.pay_vendor(
            session, vendor_id, payload.branch_id, payload.amount,
            note=payload.note, employee_id=payload.employee_id,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
