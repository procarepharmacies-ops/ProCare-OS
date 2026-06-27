"""Vendor/supplier management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import vendors

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("/list")
def vendors_list(
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"vendors": vendors.list_vendors(session, limit)}


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


@router.get("/summary")
def vendor_summary(session: Session = Depends(get_session)):
    return vendors.vendor_summary(session)
