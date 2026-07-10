"""Inventory / catalogue endpoints (reads + stock adjustment write)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import inventory
from app.services.pos import POSError

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/products")
def products(
    branch_id: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"products": inventory.list_products(session, branch_id or None, search, limit)}


@router.get("/products/{product_id}/batches")
def batches(
    product_id: int,
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return {"batches": inventory.product_batches(session, product_id, branch_id or None)}


@router.get("/products/{product_id}/insight")
def insight(
    product_id: int,
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """Product drill-down for the dashboard: on-hand per branch, 30-day demand
    forecast, and recent sales."""
    out = inventory.product_insight(session, product_id, branch_id or None)
    if out is None:
        raise HTTPException(status_code=404, detail="product not found")
    return out


class AdjustIn(BaseModel):
    batch_id: int
    new_amount: float = Field(ge=0)
    reason: str = "adjust"  # adjust | writeoff
    employee_id: int | None = None


@router.post("/adjust")
def adjust(payload: AdjustIn, session: Session = Depends(get_session)):
    """Stock adjustment / stock-count correction (eStock's Stock Adjustments)."""
    try:
        return inventory.adjust_stock(
            session,
            payload.batch_id,
            payload.new_amount,
            reason=payload.reason,
            employee_id=payload.employee_id,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


class LocationIn(BaseModel):
    shelf_location: str | None = Field(None, max_length=80)


@router.post("/products/{product_id}/location")
def set_location(product_id: int, payload: LocationIn, session: Session = Depends(get_session)):
    """Merchandising: where this product lives on the shelves."""
    try:
        return inventory.set_shelf_location(session, product_id, payload.shelf_location)
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
