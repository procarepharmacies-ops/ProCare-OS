"""Customer & vendor endpoints (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import parties

router = APIRouter(tags=["parties"])


@router.get("/customers")
def customers(
    only_debtors: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"customers": parties.list_customers(session, only_debtors, limit)}


@router.get("/vendors")
def vendors(limit: int = Query(200, ge=1, le=500), session: Session = Depends(get_session)):
    return {"vendors": parties.list_vendors(session, limit)}
