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
    cutoff = datetime.now() - timedelta(days=days)

    base_sales = select(func.sum(m.Sale.total_net)).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    base_returns = select(func.sum(m.Sale.total_net)).where(
        m.Sale.is_return == True,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    base_count = select(func.count()).select_from(m.Sale).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )

    if branch_id:
        base_sales = base_sales.where(m.Sale.branch_id == branch_id)
        base_returns = base_returns.where(m.Sale.branch_id == branch_id)
        base_count = base_count.where(m.Sale.branch_id == branch_id)

    total_sales = float(session.scalar(base_sales) or 0)
    total_returns = float(session.scalar(base_returns) or 0)
    num_sales = int(session.scalar(base_count) or 0)

    return {
        "period_days": days,
        "total_sales_net": total_sales,
        "total_returns_net": total_returns,
        "num_sales": num_sales,
        "net_revenue": total_sales - total_returns,
    }
