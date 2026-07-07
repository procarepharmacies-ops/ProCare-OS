"""Stock report suite + tabular export.

Reports (all read-only, branch-scoped or consolidated):
  * ``stock_on_hand``   — per product: qty, cost value, sell value, shelf.
  * ``stock_by_batch``  — batch-level with expiry (eStock Stock by Batch).
  * ``stock_movements`` — the audit trail (sale/purchase/transfer/adjust...).
  * ``stock_valuation`` — totals per branch (cost + retail + potential margin).

``to_csv`` renders any of these as UTF-8-BOM CSV so Excel opens Arabic text
correctly — the "data only" export. The branded PDF/print export is rendered by
the frontend's print stylesheet from the same JSON.
"""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, as_date, available_stock_filter, branch_filter, money


def stock_on_hand(session: Session, branch_id: int | None = None, limit: int = 2000) -> list[dict]:
    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
            func.sum(m.StockBatch.amount * m.StockBatch.buy_price).label("cost_value"),
            func.sum(m.StockBatch.amount * m.StockBatch.sell_price).label("sell_value"),
            func.min(m.StockBatch.exp_date).label("nearest_expiry"),
        )
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    rows = session.execute(
        select(m.Product, on_hand.c.qty, on_hand.c.cost_value, on_hand.c.sell_value, on_hand.c.nearest_expiry)
        .join(on_hand, on_hand.c.pid == m.Product.product_id)
        .where(m.Product.is_deleted == False)  # noqa: E712
        .order_by(m.Product.name_ar)
        .limit(limit)
    ).all()
    return [
        {
            "product_id": p.product_id,
            "code": p.code,
            "name_ar": p.name_ar,
            "name_en": p.name_en,
            "shelf_location": p.shelf_location,
            "qty": money(qty),
            "cost_value": money(cost),
            "sell_value": money(sell),
            "potential_profit": money(float(sell or 0) - float(cost or 0)),
            "min_stock": money(p.min_stock),
            "below_min": float(qty or 0) < float(p.min_stock or 0),
            "nearest_expiry": exp.isoformat() if exp else None,
        }
        for p, qty, cost, sell, exp in rows
    ]


def stock_by_batch(session: Session, branch_id: int | None = None, limit: int = 2000) -> list[dict]:
    rows = session.execute(
        select(m.StockBatch, m.Product.name_ar, m.Product.name_en, m.Branch.name_ar.label("branch"))
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(m.StockBatch.amount > 0, branch_filter(m.StockBatch, branch_id))
        .order_by(m.StockBatch.exp_date.asc().nulls_last())
        .limit(limit)
    ).all()
    return [
        {
            "batch_id": b.batch_id,
            "product_id": b.product_id,
            "name_ar": name_ar,
            "name_en": name_en,
            "branch": branch,
            "qty": money(b.amount),
            "buy_price": money(b.buy_price),
            "sell_price": money(b.sell_price),
            "exp_date": b.exp_date.isoformat() if b.exp_date else None,
            "days_to_expiry": (b.exp_date - TODAY).days if b.exp_date else None,
            "expired": bool(b.exp_date and b.exp_date <= TODAY),
        }
        for b, name_ar, name_en, branch in rows
    ]


def stock_movements(
    session: Session, branch_id: int | None = None, days: int = 30, limit: int = 1000
) -> list[dict]:
    start = TODAY - timedelta(days=days)
    rows = session.execute(
        select(m.StockMovement, m.StockBatch.product_id, m.Product.name_ar, m.Branch.name_ar.label("branch"))
        .join(m.StockBatch, m.StockBatch.batch_id == m.StockMovement.batch_id)
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Branch, m.Branch.branch_id == m.StockMovement.branch_id)
        .where(branch_filter(m.StockMovement, branch_id), as_date(m.StockMovement.created_at) >= start)
        .order_by(m.StockMovement.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "movement_id": mv.movement_id,
            "created_at": mv.created_at.isoformat() if mv.created_at else None,
            "branch": branch,
            "product_id": pid,
            "name_ar": name_ar,
            "delta": money(mv.delta),
            "reason": mv.reason,
            "ref_id": mv.ref_id,
        }
        for mv, pid, name_ar, branch in rows
    ]


def stock_valuation(session: Session) -> list[dict]:
    """Inventory value per branch: cost, retail, and the margin locked in it."""
    branches = {b.branch_id: b for b in session.scalars(select(m.Branch)).all()}
    rows = session.execute(
        select(
            m.StockBatch.branch_id,
            func.count(func.distinct(m.StockBatch.product_id)),
            func.coalesce(func.sum(m.StockBatch.amount), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.sell_price), 0),
        )
        .where(available_stock_filter())
        .group_by(m.StockBatch.branch_id)
    ).all()
    out = []
    for bid, products, units, cost, sell in rows:
        b = branches.get(bid)
        out.append(
            {
                "branch_id": bid,
                "name_ar": b.name_ar if b else str(bid),
                "name_en": b.name_en if b else str(bid),
                "products": products,
                "units": money(units),
                "cost_value": money(cost),
                "sell_value": money(sell),
                "potential_profit": money(float(sell) - float(cost)),
            }
        )
    return out


# --- CSV export ---------------------------------------------------------------
def to_csv(rows: list[dict]) -> str:
    """Rows → CSV with a UTF-8 BOM (Excel shows Arabic correctly). Data only —
    the ProCare-branded layout is the frontend's print template."""
    if not rows:
        return "\ufeff"
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()
