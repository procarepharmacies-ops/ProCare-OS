"""Customers & vendors read service.

Includes the credit picture (limit vs balance) — the control eStock lacked,
which let 61 customers run over their limit. ProCare surfaces it here and
enforces it at the POS (see ``app.services.pos.check_credit``).
"""
from __future__ import annotations

from sqlalchemy import func, select
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


def customer_profile(session: Session, customer_id: int, limit: int = 100) -> dict | None:
    """Customer 360 (شاشة العميل): identity + address + loyalty points, the
    full purchase history, and the medicines they actually take (aggregated
    products with times bought + last date) — everything the pharmacist needs
    on one screen."""
    c = session.get(m.Customer, customer_id)
    if c is None or c.is_deleted:
        return None

    # Purchase history (their invoices).
    sales = session.execute(
        select(m.Sale.sale_id, m.Sale.sale_date, m.Sale.total_net, m.Sale.is_return)
        .where(m.Sale.customer_id == customer_id)
        .order_by(m.Sale.sale_date.desc())
        .limit(limit)
    ).all()
    history = [
        {
            "sale_id": sid,
            "date": d.isoformat() if d else None,
            "total": money(tot),
            "is_return": bool(ret),
        }
        for sid, d, tot, ret in sales
    ]

    # Medicines they take: aggregate sale lines by product.
    meds = session.execute(
        select(
            m.Product.product_id,
            m.Product.name_ar,
            m.Product.name_en,
            func.sum(m.SaleLine.amount).label("qty"),
            func.count(func.distinct(m.SaleLine.sale_id)).label("times"),
            func.max(m.Sale.sale_date).label("last"),
        )
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .join(m.Product, m.Product.product_id == m.SaleLine.product_id)
        .where(m.Sale.customer_id == customer_id, m.Sale.is_return == False)  # noqa: E712
        .group_by(m.Product.product_id, m.Product.name_ar, m.Product.name_en)
        .order_by(func.count(func.distinct(m.SaleLine.sale_id)).desc())
        .limit(50)
    ).all()
    medicines = [
        {
            "product_id": pid,
            "name_ar": nar,
            "name_en": nen,
            "total_qty": money(qty),
            "times_bought": int(times),
            "last_bought": last.isoformat() if last else None,
        }
        for pid, nar, nen, qty, times, last in meds
    ]

    total_spent = money(
        session.scalar(
            select(func.coalesce(func.sum(m.Sale.total_net), 0)).where(
                m.Sale.customer_id == customer_id, m.Sale.is_return == False  # noqa: E712
            )
        )
        or 0
    )
    return {
        "customer_id": c.customer_id,
        "name_ar": c.name_ar,
        "name_en": c.name_en,
        "mobile": c.mobile,
        "address": c.address,
        "loyalty_points": money(c.loyalty_points),
        "current_balance": money(c.current_balance),
        "credit_limit": money(c.credit_limit),
        "total_spent": total_spent,
        "visit_count": len(history),
        "history": history,
        "medicines": medicines,
    }


def update_customer(session: Session, customer_id: int, data: dict) -> dict | None:
    """Edit editable customer fields (address, mobile) — تحديث بيانات العميل."""
    c = session.get(m.Customer, customer_id)
    if c is None or c.is_deleted:
        return None
    if "address" in data:
        c.address = (data.get("address") or "").strip() or None
    if "mobile" in data:
        c.mobile = (data.get("mobile") or "").strip() or None
    session.commit()
    return {"customer_id": c.customer_id, "address": c.address, "mobile": c.mobile}


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
