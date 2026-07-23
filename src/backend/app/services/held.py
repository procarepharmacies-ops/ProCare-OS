"""Hold / park invoice (الفواتير المعلّقة) — save a POS cart, resume it later.

A held invoice is JUST a saved cart. It touches no stock and runs no credit
check — those happen only when it's resumed into the POS and completed as a
normal sale. Holds auto-expire after ``HOLD_EXPIRE_DAYS`` (env, default 3) so a
forgotten cart doesn't linger; expired holds are purged lazily on every list.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money


def _expire_days() -> int:
    try:
        return max(1, int(os.environ.get("HOLD_EXPIRE_DAYS", "3")))
    except ValueError:
        return 3


def hold_invoice(
    session: Session,
    branch_id: int,
    cart: list[dict],
    *,
    cashier_id: int | None = None,
    customer_id: int | None = None,
    label: str | None = None,
    note: str | None = None,
) -> dict:
    """Park a cart. ``cart`` is stored verbatim (the exact line dicts the POS
    sends). No stock/credit is touched."""
    if not cart:
        from app.services.pos import POSError

        raise POSError("empty_hold", "لا توجد أصناف لتعليقها / nothing to hold")
    held = m.HeldInvoice(
        branch_id=branch_id,
        cashier_id=cashier_id,
        customer_id=customer_id,
        label=(label or None),
        note=(note or None),
        cart_json=json.dumps(cart, ensure_ascii=False),
        expires_at=datetime.utcnow() + timedelta(days=_expire_days()),
    )
    session.add(held)
    session.commit()
    session.refresh(held)
    return {"held_id": held.held_id, "lines": len(cart)}


def _purge_expired(session: Session) -> None:
    session.execute(
        delete(m.HeldInvoice).where(
            m.HeldInvoice.expires_at.is_not(None), m.HeldInvoice.expires_at < datetime.utcnow()
        )
    )
    session.commit()


def list_held(session: Session, branch_id: int | None = None) -> dict:
    """Active (non-expired) held invoices, newest first. Purges expired first."""
    _purge_expired(session)
    stmt = select(m.HeldInvoice).order_by(m.HeldInvoice.held_id.desc())
    if branch_id:
        stmt = stmt.where(m.HeldInvoice.branch_id == branch_id)
    rows = session.scalars(stmt).all()
    out = []
    for h in rows:
        try:
            n = len(json.loads(h.cart_json))
        except (ValueError, TypeError):
            n = 0
        out.append({
            "held_id": h.held_id,
            "branch_id": h.branch_id,
            "cashier_id": h.cashier_id,
            "customer_id": h.customer_id,
            "label": h.label,
            "note": h.note,
            "lines": n,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "expires_at": h.expires_at.isoformat() if h.expires_at else None,
        })
    return {"held": out, "count": len(out)}


def resume_held(session: Session, held_id: int) -> dict | None:
    """Return a held cart re-resolved against CURRENT products so the POS can
    load it back: each line gets the live name + sell_price, plus flags —
    ``missing`` (product deleted since hold) and ``price_changed`` (stored price
    differs from the current one). Does not delete the hold (discard does)."""
    h = session.get(m.HeldInvoice, held_id)
    if h is None:
        return None
    try:
        cart = json.loads(h.cart_json)
    except (ValueError, TypeError):
        cart = []

    lines = []
    for ln in cart:
        pid = ln.get("product_id")
        product = session.get(m.Product, pid) if pid is not None else None
        missing = product is None or product.is_deleted
        stored_price = ln.get("sell_price")
        current_price = float(product.sell_price) if not missing else None
        price_changed = (
            not missing and stored_price is not None
            and abs(float(stored_price) - current_price) > 1e-9
        )
        lines.append({
            **ln,
            "name_ar": product.name_ar if not missing else None,
            "name_en": product.name_en if not missing else None,
            "current_sell_price": money(current_price) if current_price is not None else None,
            "missing": missing,
            "price_changed": bool(price_changed),
        })
    return {
        "held_id": h.held_id,
        "branch_id": h.branch_id,
        "customer_id": h.customer_id,
        "note": h.note,
        "label": h.label,
        "lines": lines,
    }


def discard_held(session: Session, held_id: int) -> bool:
    """Delete a held invoice. Returns False if it didn't exist. Idempotent."""
    h = session.get(m.HeldInvoice, held_id)
    if h is None:
        return False
    session.delete(h)
    session.commit()
    return True
