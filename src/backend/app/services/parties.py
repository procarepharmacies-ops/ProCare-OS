"""Customers & vendors read service.

Includes the credit picture (limit vs balance) — the control eStock lacked,
which let 61 customers run over their limit. ProCare surfaces it here and
enforces it at the POS (see ``app.services.pos.check_credit``).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money


def list_customers(session: Session, only_debtors: bool = False, limit: int = 200) -> list[dict]:
    stmt = select(m.Customer).where(m.Customer.is_deleted == False)  # noqa: E712
    if only_debtors:
        stmt = stmt.where(m.Customer.current_balance > 0)
    stmt = stmt.order_by(m.Customer.current_balance.desc()).limit(limit)
    out = []
    for c in session.scalars(stmt):
        limit_v = float(c.credit_limit or 0)
        balance = float(c.current_balance or 0)
        out.append(
            {
                "customer_id": c.customer_id,
                "name_ar": c.name_ar,
                "name_en": c.name_en,
                "mobile": c.mobile,
                "credit_limit": money(limit_v),
                "current_balance": money(balance),
                "available_credit": money(limit_v - balance),
                "over_limit": limit_v > 0 and balance > limit_v,
            }
        )
    return out


def customer_statement(session: Session, customer_id: int, limit: int = 200) -> dict | None:
    """Account statement — the ProCare equivalent of eStock's Gedo_customers
    ledger (88,359 rows): every debit/credit on the account, newest first,
    with a running balance walked back from the current balance."""
    customer = session.get(m.Customer, customer_id)
    if customer is None or customer.is_deleted:
        return None
    entries = session.scalars(
        select(m.LedgerEntry)
        .where(m.LedgerEntry.account_type == "customer", m.LedgerEntry.account_ref == customer_id)
        .order_by(m.LedgerEntry.entry_date.desc(), m.LedgerEntry.entry_id.desc())
        .limit(limit)
    ).all()
    running = float(customer.current_balance or 0)
    rows = []
    for e in entries:
        debit = float(e.debit or 0)
        credit = float(e.credit or 0)
        rows.append(
            {
                "entry_id": e.entry_id,
                "date": e.entry_date.isoformat(),
                "ref_type": e.ref_type,
                "ref_id": e.ref_id,
                "debit": money(debit),
                "credit": money(credit),
                "balance_after": money(running),
                "note": e.note,
            }
        )
        running = running - debit + credit  # balance before this entry
    limit_v = float(customer.credit_limit or 0)
    balance = float(customer.current_balance or 0)
    return {
        "customer_id": customer.customer_id,
        "name_ar": customer.name_ar,
        "name_en": customer.name_en,
        "mobile": customer.mobile,
        "credit_limit": money(limit_v),
        "current_balance": money(balance),
        "opening_balance": money(customer.opening_balance),
        "available_credit": money(limit_v - balance),
        "over_limit": limit_v > 0 and balance > limit_v,
        "entries": rows,
    }


def list_vendors(session: Session, limit: int = 200) -> list[dict]:
    stmt = (
        select(m.Vendor)
        .where(m.Vendor.is_active == True)  # noqa: E712
        .order_by(m.Vendor.current_balance.desc())
        .limit(limit)
    )
    return [
        {
            "vendor_id": v.vendor_id,
            "name_ar": v.name_ar,
            "name_en": v.name_en,
            "mobile": v.mobile,
            "amount_owed": money(v.current_balance),
        }
        for v in session.scalars(stmt)
    ]
