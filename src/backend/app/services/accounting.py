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


_ACCOUNT_TYPE_LABELS = {
    "customer": "العملاء",
    "vendor": "الموردون",
    "cash": "النقدية (الخزينة)",
    "bank": "البنوك",
    "branch": "الفروع",
    "general": "حسابات عامة",
}


def chart_of_accounts(session: Session, branch_id: int | None = None) -> dict:
    """شجرة الحسابات — the account tree grouped by type, each type carrying its
    sub-accounts with resolved names (customer/vendor/branch) and net balance.
    Builds on the trial-balance aggregation, adding readable names + Arabic
    group headers so it reads like eStock's chart of accounts."""
    tb = trial_balance(session, branch_id)
    # Resolve names for the ref-bearing account types in one pass each.
    cust_names = dict(session.execute(select(m.Customer.customer_id, m.Customer.name_ar)).all())
    vend_names = dict(session.execute(select(m.Vendor.vendor_id, m.Vendor.name_ar)).all())
    branch_names = dict(session.execute(select(m.Branch.branch_id, m.Branch.name_ar)).all())

    groups: dict[str, dict] = {}
    for acc in tb["accounts"].values():
        atype = acc["type"]
        g = groups.setdefault(
            atype,
            {
                "type": atype,
                "label": _ACCOUNT_TYPE_LABELS.get(atype, atype),
                "debit": 0.0,
                "credit": 0.0,
                "balance": 0.0,
                "accounts": [],
            },
        )
        ref = acc["ref"]
        name = None
        if ref is not None:
            if atype == "customer":
                name = cust_names.get(ref)
            elif atype == "vendor":
                name = vend_names.get(ref)
            elif atype == "branch":
                name = branch_names.get(ref)
        g["accounts"].append({**acc, "name": name or (f"#{ref}" if ref else g["label"])})
        g["debit"] += acc["debit"]
        g["credit"] += acc["credit"]
        g["balance"] += acc["balance"]

    ordered = [groups[k] for k in _ACCOUNT_TYPE_LABELS if k in groups]
    ordered += [g for k, g in groups.items() if k not in _ACCOUNT_TYPE_LABELS]
    for g in ordered:
        g["accounts"].sort(key=lambda a: abs(a["balance"]), reverse=True)
    return {
        "groups": ordered,
        "total_debit": tb["total_debit"],
        "total_credit": tb["total_credit"],
        "balanced": abs(tb["total_debit"] - tb["total_credit"]) < 0.01,
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


def profit_loss(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    """Gross P&L over a period — eStock's profit rule re-implemented cleanly:
    gross_profit = Σ total_sell − Σ(amount × buy_price) at the LINE level
    (cost captured at sale time, not current product cost), with return
    invoices reversing both revenue and cost."""
    cutoff = datetime.now() - timedelta(days=days)

    def _lines_totals(is_return: bool) -> tuple[float, float]:
        q = (
            select(
                func.coalesce(func.sum(m.SaleLine.total_sell), 0),
                func.coalesce(func.sum(m.SaleLine.amount * m.SaleLine.buy_price), 0),
            )
            .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
            .where(m.Sale.is_return == is_return, m.Sale.sale_date >= cutoff)
        )
        if branch_id:
            q = q.where(m.Sale.branch_id == branch_id)
        revenue, cogs = session.execute(q).one()
        return float(revenue or 0), float(cogs or 0)

    revenue, cogs = _lines_totals(is_return=False)
    returns_refund, returns_cogs = _lines_totals(is_return=True)

    net_revenue = round(revenue - returns_refund, 2)
    net_cogs = round(cogs - returns_cogs, 2)
    gross_profit = round(net_revenue - net_cogs, 2)
    return {
        "period_days": days,
        "branch_id": branch_id,
        "revenue": round(revenue, 2),
        "returns_refund": round(returns_refund, 2),
        "net_revenue": net_revenue,
        "cogs": net_cogs,
        "gross_profit": gross_profit,
        "margin_pct": round(gross_profit / net_revenue * 100, 1) if net_revenue else 0.0,
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


def create_journal_entry(
    session: Session,
    branch_id: int,
    account_type: str,
    *,
    debit: float = 0.0,
    credit: float = 0.0,
    account_ref: int | None = None,
    note: str | None = None,
) -> dict:
    """Manual journal entry (eStock's Tuning_accounts — 293 manual
    adjustments). One-sided by design, matching the source system."""
    from app.services.pos import POSError

    # Must match the CK_ledger_account check constraint on ledger_entries.
    if account_type not in ("customer", "vendor", "cash", "bank", "branch", "general"):
        raise POSError("bad_account_type", "نوع حساب غير صالح / invalid account type")
    if (debit <= 0 and credit <= 0) or (debit > 0 and credit > 0):
        raise POSError("bad_amounts", "أدخل مديناً أو دائناً (وليس كليهما) / enter debit OR credit")
    entry = m.LedgerEntry(
        branch_id=branch_id,
        account_type=account_type,
        account_ref=account_ref,
        ref_type="manual",
        debit=float(debit),
        credit=float(credit),
        note=note or "قيد يدوي / manual journal entry",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {"entry_id": entry.entry_id, "account_type": account_type, "debit": float(debit), "credit": float(credit)}


def sales_by_customer(session: Session, branch_id: int | None = None, days: int = 30, limit: int = 20) -> list[dict]:
    """Sales-by-customer report (an eStock report ProCare lacked): revenue and
    invoice count per named customer over the period, returns excluded."""
    cutoff = datetime.now() - timedelta(days=days)
    q = (
        select(
            m.Customer.customer_id,
            m.Customer.name_ar,
            m.Customer.name_en,
            func.count(m.Sale.sale_id),
            func.coalesce(func.sum(m.Sale.total_net), 0),
        )
        .join(m.Sale, m.Sale.customer_id == m.Customer.customer_id)
        .where(m.Sale.is_return == False, m.Sale.sale_date >= cutoff)  # noqa: E712
        .group_by(m.Customer.customer_id, m.Customer.name_ar, m.Customer.name_en)
        .order_by(func.coalesce(func.sum(m.Sale.total_net), 0).desc())
        .limit(limit)
    )
    if branch_id:
        q = q.where(m.Sale.branch_id == branch_id)
    return [
        {
            "customer_id": cid,
            "name_ar": name_ar,
            "name_en": name_en,
            "invoices": int(n),
            "revenue": round(float(total or 0), 2),
        }
        for cid, name_ar, name_en, n, total in session.execute(q)
    ]
