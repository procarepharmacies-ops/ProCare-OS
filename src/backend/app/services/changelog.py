"""Change-history / audit trails (سجل التغييرات) — eStock Product_Changes,
Product_amount_Change and user_login parity, over the tables ProCare owns.

Three read views the pharmacy can inspect after the fact:
  * **price changes** — the ``product_changes`` log (who changed a product's
    sell/buy price or minimum, from what, to what, when).
  * **stock changes** — every ``stock_movements`` row (each sale, adjustment,
    transfer and count writes one), joined to the product + who did it.
  * **login history** — the ``auth_events`` audit (login ok/fail, password
    changes), already captured at authentication time.

``log_product_change`` is the one writer here; it never commits (the caller's
transaction owns the commit) so a price edit and its log entry are atomic.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money

# Human labels for the stock-movement reason codes (Product_amount_Change).
STOCK_REASON_LABELS = {
    "sale": {"ar": "بيع", "en": "Sale"},
    "return": {"ar": "مرتجع", "en": "Return"},
    "adjust": {"ar": "تسوية جرد", "en": "Stock adjustment"},
    "writeoff": {"ar": "إهلاك / تلف", "en": "Write-off"},
    "purchase": {"ar": "شراء", "en": "Purchase"},
    "transfer_in": {"ar": "تحويل وارد", "en": "Transfer in"},
    "transfer_out": {"ar": "تحويل صادر", "en": "Transfer out"},
    "predictive": {"ar": "توريد تنبؤي", "en": "Predictive restock"},
}

FIELD_LABELS = {
    "sell_price": {"ar": "سعر البيع", "en": "Sell price"},
    "buy_price": {"ar": "سعر الشراء", "en": "Buy price"},
    "min_stock": {"ar": "الحد الأدنى", "en": "Minimum stock"},
}


def log_product_change(
    session: Session, product_id: int, field: str, old_value: float, new_value: float, employee_id: int | None
) -> None:
    """Record one product field change. Does NOT commit — the caller's
    transaction (e.g. the price edit) commits it atomically."""
    session.add(
        m.ProductChange(
            product_id=product_id,
            field=field,
            old_value=float(old_value or 0),
            new_value=float(new_value or 0),
            employee_id=employee_id,
        )
    )


def product_changes(session: Session, product_id: int | None = None, days: int = 90, limit: int = 200) -> list[dict]:
    """Price / min-stock change log, newest first, with product + who did it."""
    cutoff = datetime.now() - timedelta(days=days)
    q = (
        select(m.ProductChange, m.Product.name_ar, m.Product.name_en, m.Employee.name_ar.label("emp_ar"))
        .join(m.Product, m.Product.product_id == m.ProductChange.product_id)
        .join(m.Employee, m.Employee.employee_id == m.ProductChange.employee_id, isouter=True)
        .where(m.ProductChange.created_at >= cutoff)
        .order_by(m.ProductChange.created_at.desc())
        .limit(limit)
    )
    if product_id:
        q = q.where(m.ProductChange.product_id == product_id)
    out = []
    for ch, name_ar, name_en, emp_ar in session.execute(q):
        fl = FIELD_LABELS.get(ch.field, {"ar": ch.field, "en": ch.field})
        out.append({
            "change_id": ch.change_id,
            "product_id": ch.product_id,
            "name_ar": name_ar,
            "name_en": name_en,
            "field": ch.field,
            "field_ar": fl["ar"],
            "field_en": fl["en"],
            "old_value": money(ch.old_value),
            "new_value": money(ch.new_value),
            "delta": money(float(ch.new_value or 0) - float(ch.old_value or 0)),
            "employee_id": ch.employee_id,
            "employee_name": emp_ar,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
        })
    return out


def stock_changes(
    session: Session, product_id: int | None = None, branch_id: int | None = None, days: int = 30, limit: int = 200
) -> list[dict]:
    """Stock movement history (Product_amount_Change), newest first, joined to
    the product + the employee who caused it, with readable reason labels."""
    cutoff = datetime.now() - timedelta(days=days)
    q = (
        select(
            m.StockMovement, m.StockBatch.product_id, m.Product.name_ar, m.Product.name_en,
            m.Employee.name_ar.label("emp_ar"),
        )
        .join(m.StockBatch, m.StockBatch.batch_id == m.StockMovement.batch_id)
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Employee, m.Employee.employee_id == m.StockMovement.employee_id, isouter=True)
        .where(m.StockMovement.created_at >= cutoff)
        .order_by(m.StockMovement.created_at.desc())
        .limit(limit)
    )
    if branch_id:
        q = q.where(m.StockMovement.branch_id == branch_id)
    if product_id:
        q = q.where(m.StockBatch.product_id == product_id)
    out = []
    for mv, pid, name_ar, name_en, emp_ar in session.execute(q):
        rl = STOCK_REASON_LABELS.get(mv.reason, {"ar": mv.reason, "en": mv.reason})
        out.append({
            "movement_id": mv.movement_id,
            "product_id": pid,
            "name_ar": name_ar,
            "name_en": name_en,
            "branch_id": mv.branch_id,
            "batch_id": mv.batch_id,
            "delta": money(mv.delta),
            "reason": mv.reason,
            "reason_ar": rl["ar"],
            "reason_en": rl["en"],
            "ref_id": mv.ref_id,
            "employee_id": mv.employee_id,
            "employee_name": emp_ar,
            "created_at": mv.created_at.isoformat() if mv.created_at else None,
        })
    return out


def login_history(session: Session, days: int = 30, limit: int = 200) -> list[dict]:
    """Authentication audit trail (user_login), newest first."""
    cutoff = datetime.now() - timedelta(days=days)
    rows = session.scalars(
        select(m.AuthEvent)
        .where(m.AuthEvent.created_at >= cutoff)
        .order_by(m.AuthEvent.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "event_id": e.event_id,
            "username": e.username,
            "event": e.event,
            "employee_id": e.employee_id,
            "ip": e.ip,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]
