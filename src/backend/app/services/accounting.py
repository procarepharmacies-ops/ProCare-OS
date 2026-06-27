"""Financial accounting and ledger endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_ledger_entries(
    session: Session,
    branch_id: int | None = None,
    account_type: str | None = None,
    days: int = 30,
    limit: int = 500,
) -> list[dict]:
    """Fetch recent ledger entries, optionally filtered by branch/account type/timeframe."""
    cutoff = datetime.now() - timedelta(days=days)
    q = select(m.LedgerEntry).where(m.LedgerEntry.entry_date >= cutoff).order_by(m.LedgerEntry.entry_date.desc())

    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)
    if account_type:
        q = q.where(m.LedgerEntry.account_type == account_type)

    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "entry_id": e.entry_id,
            "branch_id": e.branch_id,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "account_type": e.account_type,
            "account_ref": e.account_ref,
            "ref_type": e.ref_type,
            "ref_id": e.ref_id,
            "debit": float(e.debit or 0),
            "credit": float(e.credit or 0),
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def trial_balance(session: Session, branch_id: int | None = None) -> dict:
    """Trial balance grouped by account type."""
    q = select(
        m.LedgerEntry.account_type,
        m.LedgerEntry.account_ref,
        func.sum(m.LedgerEntry.debit).label("total_debit"),
        func.sum(m.LedgerEntry.credit).label("total_credit"),
    ).group_by(m.LedgerEntry.account_type, m.LedgerEntry.account_ref)

    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)

    rows = session.execute(q).all()

    accounts = {}
    for account_type, account_ref, total_debit, total_credit in rows:
        key = f"{account_type}:{account_ref}" if account_ref else account_type
        accounts[key] = {
            "type": account_type,
            "ref": account_ref,
            "debit": float(total_debit or 0),
            "credit": float(total_credit or 0),
            "balance": float((total_debit or 0) - (total_credit or 0)),
        }

    return {
        "accounts": accounts,
        "total_debit": sum(a["debit"] for a in accounts.values()),
        "total_credit": sum(a["credit"] for a in accounts.values()),
    }


def account_balance(session: Session, account_type: str, account_ref: int | None = None) -> dict:
    """Get the balance for a specific account (e.g., customer, vendor)."""
    q = select(
        func.sum(m.LedgerEntry.debit).label("total_debit"),
        func.sum(m.LedgerEntry.credit).label("total_credit"),
    ).where(m.LedgerEntry.account_type == account_type)

    if account_ref is not None:
        q = q.where(m.LedgerEntry.account_ref == account_ref)

    row = session.execute(q).one_or_none()
    if not row:
        return {"account_type": account_type, "account_ref": account_ref, "debit": 0, "credit": 0, "balance": 0}

    total_debit, total_credit = row
    total_debit = float(total_debit or 0)
    total_credit = float(total_credit or 0)

    return {
        "account_type": account_type,
        "account_ref": account_ref,
        "debit": total_debit,
        "credit": total_credit,
        "balance": total_debit - total_credit,
    }


def sales_summary(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    """Sales summary: total sales, returns, net revenue, by time period."""
    cutoff = datetime.now() - timedelta(days=days)

    q_sales = select(m.Sale).where(m.Sale.is_return == False).where(m.Sale.sale_date >= cutoff)
    q_returns = select(m.Sale).where(m.Sale.is_return == True).where(m.Sale.sale_date >= cutoff)

    if branch_id:
        q_sales = q_sales.where(m.Sale.branch_id == branch_id)
        q_returns = q_returns.where(m.Sale.branch_id == branch_id)

    total_sales = session.scalar(select(func.sum(m.Sale.total_net)).where(m.Sale.is_return == False).where(m.Sale.sale_date >= cutoff) if not branch_id else select(func.sum(m.Sale.total_net)).where(m.Sale.branch_id == branch_id).where(m.Sale.is_return == False).where(m.Sale.sale_date >= cutoff)) or 0

    total_returns = session.scalar(select(func.sum(m.Sale.total_net)).where(m.Sale.is_return == True).where(m.Sale.sale_date >= cutoff) if not branch_id else select(func.sum(m.Sale.total_net)).where(m.Sale.branch_id == branch_id).where(m.Sale.is_return == True).where(m.Sale.sale_date >= cutoff)) or 0

    num_sales = session.scalar(select(func.count()).select_from(m.Sale).where(m.Sale.is_return == False).where(m.Sale.sale_date >= cutoff) if not branch_id else select(func.count()).select_from(m.Sale).where(m.Sale.branch_id == branch_id).where(m.Sale.is_return == False).where(m.Sale.sale_date >= cutoff)) or 0

    return {
        "period_days": days,
        "total_sales_net": float(total_sales),
        "total_returns_net": float(total_returns),
        "num_sales": int(num_sales),
        "net_revenue": float(total_sales) - float(total_returns),
    }
