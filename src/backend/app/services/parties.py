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
