"""Inventory / catalogue endpoints (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import inventory

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
