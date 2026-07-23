"""Shareholders / owners API (Phase 6): capital register + dividend history.

GET /api/shareholders          — the owners register (capital + total dividends)
GET /api/shareholders/{id}     — one shareholder with annual dividend history

CEO only (ownership + payout data) — gated at the router in routes.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import shareholders as svc

router = APIRouter(prefix="/shareholders", tags=["shareholders"])


@router.get("")
def list_shareholders(session: Session = Depends(get_session)):
    return svc.list_shareholders(session)


@router.get("/{shareholder_id}")
def shareholder_detail(shareholder_id: int, session: Session = Depends(get_session)):
    out = svc.shareholder_detail(session, shareholder_id)
    if out is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Shareholder not found"})
    return out
