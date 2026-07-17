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
    # متوسط الخصم الكلي: total discount ÷ total gross across every bill.
    total_discount = session.scalar(
        select(func.sum(m.Purchase.total_discount)).where(m.Purchase.vendor_id == vendor_id)
    ) or 0
    avg_discount_pct = (
        round(float(total_discount) / float(total_spent) * 100, 2) if float(total_spent) > 0 else 0.0
    )

    return {
        "total_discount": float(total_discount),
        "avg_discount_pct": avg_discount_pct,
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


def vendor_statement(session: Session, vendor_id: int, limit: int = 300) -> dict | None:
    """كشف حساب مورد: every bill (credit — we owe more) and every payment
    (debit — we paid), newest last, with a running balance."""
    v = session.get(m.Vendor, vendor_id)
    if v is None:
        return None
    rows: list[dict] = []
    for p in session.scalars(
        select(m.Purchase).where(m.Purchase.vendor_id == vendor_id).order_by(m.Purchase.bill_date)
    ):
        net = float(p.total_gross or 0) - float(p.total_discount or 0)
        rows.append(
            {
                "date": p.bill_date.isoformat() if p.bill_date else None,
                "kind": "مرتجع شراء" if p.is_return else "فاتورة شراء",
                "ref": p.bill_number or f"#{p.purchase_id}",
                "debit": net if p.is_return else 0.0,
                "credit": 0.0 if p.is_return else net,
                "discount": float(p.total_discount or 0),
            }
        )
    for e in session.scalars(
        select(m.LedgerEntry)
        .where(m.LedgerEntry.account_type == "vendor", m.LedgerEntry.account_ref == vendor_id)
        .order_by(m.LedgerEntry.entry_date)
    ):
        rows.append(
            {
                "date": e.entry_date.isoformat() if e.entry_date else None,
                "kind": "سداد" if float(e.debit or 0) > 0 else "قيد",
                "ref": e.note or f"قيد #{e.entry_id}",
                "debit": float(e.debit or 0),
                "credit": float(e.credit or 0),
                "discount": 0.0,
            }
        )
    rows.sort(key=lambda r: r["date"] or "")
    balance = float(v.opening_balance) if hasattr(v, "opening_balance") else 0.0
    for r in rows:
        balance = round(balance + r["credit"] - r["debit"], 3)
        r["balance"] = balance
    return {
        "vendor_id": vendor_id,
        "name_ar": v.name_ar,
        "rows": rows[-limit:],
        "closing_balance": balance,
        "current_balance": float(v.current_balance or 0),
    }


def pay_vendor(
    session: Session, vendor_id: int, branch_id: int, amount: float, *,
    note: str | None = None, employee_id: int | None = None,
) -> dict:
    """صرف لمورد: one atomic operation — cash leaves the branch treasury AND the
    vendor's payable balance drops by the same amount."""
    from app.services.pos import POSError
    from app.services import treasury

    v = session.get(m.Vendor, vendor_id)
    if v is None:
        raise POSError("vendor_not_found", f"المورد غير موجود #{vendor_id} / vendor not found")
    if amount <= 0:
        raise POSError("bad_amount", "المبلغ يجب أن يكون أكبر من صفر / amount must be positive")
    bal = treasury.branch_balance(session, branch_id)
    if amount > bal + 1e-9:
        raise POSError(
            "insufficient_treasury",
            f"رصيد الخزينة غير كافٍ: متاح {round(bal,2)} / insufficient treasury balance",
        )
    session.add(
        m.LedgerEntry(
            branch_id=branch_id, account_type="cash", credit=float(amount),
            ref_type="vendor_payment", ref_id=vendor_id,
            note=f"سداد للمورد {v.name_ar}" + (f" / {note}" if note else ""),
        )
    )
    session.add(
        m.LedgerEntry(
            branch_id=branch_id, account_type="vendor", account_ref=vendor_id,
            debit=float(amount), ref_type="vendor_payment",
            note=note or "سداد نقدي",
        )
    )
    v.current_balance = float(v.current_balance or 0) - float(amount)
    session.commit()
    return {
        "vendor_id": vendor_id,
        "paid": float(amount),
        "new_balance": float(v.current_balance),
    }


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
