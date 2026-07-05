"""Stock-shortage sheet (eStock's Shortcoming): staff log what customers asked
for and we didn't have; purchasing works the list and flips statuses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import get_session

router = APIRouter(prefix="/shortages", tags=["shortages"])

_STATUSES = ("open", "ordered", "received", "cancelled")


class ShortageIn(BaseModel):
    branch_id: int
    product_id: int | None = None
    product_name: str | None = None  # free text when not in the catalogue
    qty_requested: float = Field(1, gt=0)
    note: str | None = None
    reported_by: int | None = None


class StatusIn(BaseModel):
    status: str


def _row(s: m.ShortageItem, product_names: dict[int, str]) -> dict:
    return {
        "shortage_id": s.shortage_id,
        "branch_id": s.branch_id,
        "product_id": s.product_id,
        "product_name": product_names.get(s.product_id) if s.product_id else s.product_name,
        "qty_requested": float(s.qty_requested or 0),
        "note": s.note,
        "status": s.status,
        "reported_by": s.reported_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("")
def list_shortages(
    branch_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    q = select(m.ShortageItem).order_by(m.ShortageItem.created_at.desc())
    if branch_id:
        q = q.where(m.ShortageItem.branch_id == branch_id)
    if status:
        q = q.where(m.ShortageItem.status == status)
    rows = session.scalars(q.limit(limit)).all()
    pids = [s.product_id for s in rows if s.product_id]
    names = {}
    if pids:
        names = dict(
            session.execute(
                select(m.Product.product_id, m.Product.name_ar).where(m.Product.product_id.in_(pids))
            ).all()
        )
    return {"shortages": [_row(s, names) for s in rows]}


@router.post("")
def create_shortage(payload: ShortageIn, session: Session = Depends(get_session)):
    if not payload.product_id and not (payload.product_name or "").strip():
        raise HTTPException(status_code=422, detail="product_id or product_name is required")
    if payload.product_id and session.get(m.Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="product not found")
    item = m.ShortageItem(
        branch_id=payload.branch_id,
        product_id=payload.product_id,
        product_name=(payload.product_name or "").strip() or None,
        qty_requested=payload.qty_requested,
        note=payload.note,
        reported_by=payload.reported_by,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"shortage_id": item.shortage_id, "status": item.status}


@router.post("/{shortage_id}/status")
def set_status(shortage_id: int, payload: StatusIn, session: Session = Depends(get_session)):
    if payload.status not in _STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {_STATUSES}")
    item = session.get(m.ShortageItem, shortage_id)
    if item is None:
        raise HTTPException(status_code=404, detail="shortage item not found")
    item.status = payload.status
    session.commit()
    return {"shortage_id": shortage_id, "status": item.status}
