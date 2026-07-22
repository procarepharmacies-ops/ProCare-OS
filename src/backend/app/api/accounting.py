"""Accounting and financial reporting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import accounting
from app.services.pos import POSError

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


@router.get("/chart")
def chart_of_accounts(branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    """شجرة الحسابات: الحسابات مجمّعة بالنوع بأسمائها وأرصدتها."""
    return accounting.chart_of_accounts(session, branch_id)


@router.get("/account-balance")
def account_balance(
    account_type: str = Query(...),
    account_ref: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return accounting.account_balance(session, account_type, account_ref)


@router.get("/profit-loss")
def profit_loss(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return accounting.profit_loss(session, branch_id, days)


class JournalIn(BaseModel):
    branch_id: int
    account_type: str
    debit: float = Field(0.0, ge=0)
    credit: float = Field(0.0, ge=0)
    account_ref: int | None = None
    note: str | None = None
    reason_code: str | None = None


@router.post("/journal")
def create_journal(payload: JournalIn, session: Session = Depends(get_session)):
    """Manual journal entry (eStock's Manual Journal Entries menu). Passing a
    ``reason_code`` records it as a Tuning adjustment (تسوية)."""
    try:
        return accounting.create_journal_entry(
            session,
            payload.branch_id,
            payload.account_type,
            debit=payload.debit,
            credit=payload.credit,
            account_ref=payload.account_ref,
            note=payload.note,
            reason_code=payload.reason_code,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("/adjustment-reasons")
def adjustment_reasons():
    """The Tuning_accounts (تسويات) reason catalogue for the adjustment form."""
    return {"reasons": accounting.adjustment_reasons()}


@router.get("/statement")
def account_statement(
    account_type: str = Query(...),
    account_ref: int | None = Query(None),
    days: int = Query(90, ge=1, le=365),
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    """كشف حساب: opening balance + movements with a running balance + closing."""
    try:
        return accounting.account_statement(session, account_type, account_ref, days, branch_id)
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("/adjustments")
def adjustments(
    branch_id: int | None = Query(None),
    days: int = Query(90, ge=1, le=365),
    session: Session = Depends(get_session),
):
    """تقرير التسويات: manual adjustments grouped by Tuning reason."""
    return accounting.adjustments_report(session, branch_id, days)


@router.get("/sales-by-customer")
def sales_by_customer(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return {"customers": accounting.sales_by_customer(session, branch_id, days, limit)}


@router.get("/sales-summary")
def sales_summary(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    return accounting.sales_summary(session, branch_id, days)
