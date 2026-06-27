"""Vendor/supplier management."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_vendors(session: Session, limit: int = 200) -> list[dict]:
    """Fetch all vendors with their financial status."""
    rows = session.scalars(select(m.Vendor).order_by(m.Vendor.vendor_id)).all()
    return [
        {
            "vendor_id": v.vendor_id,
            "name_ar": v.name_ar,
            "name_en": v.name_en,
            "tel": v.tel,
            "mobile": v.mobile,
            "credit_limit": float(v.credit_limit or 0),
            "current_balance": float(v.current_balance or 0),
            "available_credit": float((v.credit_limit or 0) - (v.current_balance or 0)),
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in rows[:limit]
    ]


def vendor_detail(session: Session, vendor_id: int) -> dict | None:
    """Fetch a single vendor with financial details."""
    v = session.scalar(select(m.Vendor).where(m.Vendor.vendor_id == vendor_id))
    if not v:
        return None

    # Get purchase count and total
    purchase_count = session.scalar(
        select(func.count()).select_from(m.Purchase).where(m.Purchase.vendor_id == vendor_id)
    ) or 0
    total_spent = session.scalar(
        select(func.sum(m.Purchase.total_gross)).where(m.Purchase.vendor_id == vendor_id)
    ) or 0

    return {
        "vendor_id": v.vendor_id,
        "name_ar": v.name_ar,
        "name_en": v.name_en,
        "tel": v.tel,
        "mobile": v.mobile,
        "credit_limit": float(v.credit_limit or 0),
        "current_balance": float(v.current_balance or 0),
        "available_credit": float((v.credit_limit or 0) - (v.current_balance or 0)),
        "is_active": v.is_active,
        "purchase_count": int(purchase_count),
        "total_spent": float(total_spent),
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def vendor_purchases(session: Session, vendor_id: int, limit: int = 100) -> list[dict]:
    """Fetch recent purchases from a vendor."""
    rows = session.scalars(
        select(m.Purchase)
        .where(m.Purchase.vendor_id == vendor_id)
        .order_by(m.Purchase.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "purchase_id": p.purchase_id,
            "bill_date": p.bill_date.isoformat() if p.bill_date else None,
            "bill_number": p.bill_number,
            "total_gross": float(p.total_gross or 0),
            "total_discount": float(p.total_discount or 0),
            "total_tax": float(p.total_tax or 0),
            "is_return": p.is_return,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


def vendor_summary(session: Session) -> dict:
    """Summary: total vendors, active, total credit, over-limit."""
    total_vendors = session.scalar(select(func.count()).select_from(m.Vendor)) or 0
    active_vendors = session.scalar(
        select(func.count()).select_from(m.Vendor).where(m.Vendor.is_active == True)
    ) or 0

    total_credit_limit = session.scalar(select(func.sum(m.Vendor.credit_limit)).select_from(m.Vendor)) or 0
    total_balance = session.scalar(select(func.sum(m.Vendor.current_balance)).select_from(m.Vendor)) or 0

    over_limit = session.scalar(
        select(func.count()).select_from(m.Vendor).where(m.Vendor.current_balance > m.Vendor.credit_limit)
    ) or 0

    return {
        "total_vendors": int(total_vendors),
        "active_vendors": int(active_vendors),
        "total_credit_limit": float(total_credit_limit),
        "total_balance": float(total_balance),
        "available_credit": float(total_credit_limit) - float(total_balance),
        "vendors_over_limit": int(over_limit),
    }
