"""Accounting and financial reporting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import accounting

router = APIRouter(prefix="/accounting", tags=["accounting"])


@router.get("/ledger")
def ledger(
    branch_id: int | None = Query(None),
    account_type: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
):
    return {"entries": accounting.list_ledger_entries(session, branch_id, account_type, days, limit)}


@router.get("/trial-balance")
def trial_balance(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return accounting.trial_balance(session, branch_id)


@router.get("/account-balance")
def account_balance(
    account_type: str = Query(...),
    account_ref: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return accounting.account_balance(session, account_type, account_ref)


@router.get("/sales-summary")
def sales_summary(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return accounting.sales_summary(session, branch_id, days)
