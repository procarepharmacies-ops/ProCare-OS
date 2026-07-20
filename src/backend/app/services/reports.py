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
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import available_stock_filter, branch_filter, fefo_order, money, sql_day, today


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
        .order_by(*fefo_order())
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
            "days_to_expiry": (b.exp_date - today()).days if b.exp_date else None,
            "expired": bool(b.exp_date and b.exp_date <= today()),
        }
        for b, name_ar, name_en, branch in rows
    ]


def stock_movements(
    session: Session, branch_id: int | None = None, days: int = 30, limit: int = 1000
) -> list[dict]:
    start = today() - timedelta(days=days)
    rows = session.execute(
        select(m.StockMovement, m.StockBatch.product_id, m.Product.name_ar, m.Branch.name_ar.label("branch"))
        .join(m.StockBatch, m.StockBatch.batch_id == m.StockMovement.batch_id)
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Branch, m.Branch.branch_id == m.StockMovement.branch_id)
        .where(branch_filter(m.StockMovement, branch_id), sql_day(m.StockMovement.created_at) >= start)
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


# --- item sales-movement report (eStock: تقرير حركة مبيعات صنف في فترة) -------
def _daily_sum(session, day_col, amount_expr, *filters) -> dict[date, float]:
    """{day -> summed amount} for one product's flow, grouped by calendar day."""
    rows = session.execute(
        select(day_col.label("d"), func.coalesce(func.sum(amount_expr), 0))
        .where(*filters)
        .group_by(day_col)
    ).all()
    out: dict[date, float] = {}
    for d, total in rows:
        # sql_day returns a date on SQLite, a str on some drivers — normalise.
        if isinstance(d, str):
            d = date.fromisoformat(d[:10])
        out[d] = float(total or 0)
    return out


def item_movement(
    session: Session,
    product_id: int,
    start: date,
    end: date,
    branch_id: int | None = None,
) -> dict:
    """Per-day stock movement of ONE item over a period — the eStock
    "حركة مبيعات صنف في فترة" report: opening balance, then purchases in,
    sales out, customer returns in, purchase returns out, جرد adjustments,
    and the running closing balance for each day.

    Balances are PHYSICAL (include expired stock, like eStock's ledger). The
    opening balance is derived from the live on-hand rolled back through every
    flow between the period start and today, so the last day's closing equals
    on-hand when the period ends today (``reconciles``).
    """
    product = session.get(m.Product, product_id)
    if product is None:
        from app.services.pos import POSError

        raise POSError("product_not_found", f"No product #{product_id}")
    if end < start:
        start, end = end, start

    now = today()
    horizon = max(end, now)  # roll opening back through everything up to today

    sday_s = sql_day(m.Sale.sale_date)
    pday = sql_day(m.Purchase.bill_date)
    mday = sql_day(m.StockMovement.created_at)

    # Each flow, per day, over [start .. horizon].
    sold = _daily_sum(
        session, sday_s, m.SaleLine.amount,
        m.SaleLine.sale_id == m.Sale.sale_id,
        m.SaleLine.product_id == product_id,
        m.Sale.is_return == False,  # noqa: E712
        branch_filter(m.Sale, branch_id),
        sday_s >= start, sday_s <= horizon,
    )
    sale_returned = _daily_sum(
        session, sday_s, m.SaleLine.amount,
        m.SaleLine.sale_id == m.Sale.sale_id,
        m.SaleLine.product_id == product_id,
        m.Sale.is_return == True,  # noqa: E712
        branch_filter(m.Sale, branch_id),
        sday_s >= start, sday_s <= horizon,
    )
    purchased = _daily_sum(
        session, pday, m.PurchaseLine.amount + m.PurchaseLine.bonus,
        m.PurchaseLine.purchase_id == m.Purchase.purchase_id,
        m.PurchaseLine.product_id == product_id,
        m.Purchase.is_return == False,  # noqa: E712
        branch_filter(m.Purchase, branch_id),
        pday >= start, pday <= horizon,
    )
    purchase_returned = _daily_sum(
        session, pday, m.PurchaseLine.amount + m.PurchaseLine.bonus,
        m.PurchaseLine.purchase_id == m.Purchase.purchase_id,
        m.PurchaseLine.product_id == product_id,
        m.Purchase.is_return == True,  # noqa: E712
        branch_filter(m.Purchase, branch_id),
        pday >= start, pday <= horizon,
    )
    adjusted = _daily_sum(
        session, mday, m.StockMovement.delta,
        m.StockMovement.batch_id == m.StockBatch.batch_id,
        m.StockBatch.product_id == product_id,
        m.StockMovement.reason == "adjust",
        branch_filter(m.StockMovement, branch_id),
        mday >= start, mday <= horizon,
    )

    def net(d: date) -> float:
        return (
            purchased.get(d, 0) + sale_returned.get(d, 0) + adjusted.get(d, 0)
            - sold.get(d, 0) - purchase_returned.get(d, 0)
        )

    # Current physical on-hand (include expired: a ledger balance is physical).
    on_hand = float(session.scalar(
        select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
            m.StockBatch.product_id == product_id,
            branch_filter(m.StockBatch, branch_id),
        )
    ) or 0)

    # Opening at period start = on-hand today minus every net flow since start.
    total_flow_to_today = sum(net(start + timedelta(days=i))
                              for i in range((horizon - start).days + 1))
    opening = on_hand - total_flow_to_today

    rows = []
    running = opening
    tot = {"purchased": 0.0, "sold": 0.0, "sale_returned": 0.0,
           "purchase_returned": 0.0, "adjusted": 0.0}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        running += net(d)
        day = {
            "date": d.isoformat(),
            "purchased": money(purchased.get(d, 0)),
            "sold": money(sold.get(d, 0)),
            "sale_returned": money(sale_returned.get(d, 0)),
            "purchase_returned": money(purchase_returned.get(d, 0)),
            "adjusted": money(adjusted.get(d, 0)),
            "closing": money(running),
        }
        # Skip fully-idle days to keep the sheet as tight as eStock's.
        if any(day[k] for k in ("purchased", "sold", "sale_returned",
                                "purchase_returned", "adjusted")):
            rows.append(day)
            for k in tot:
                tot[k] += day[k]

    closing = money(running)
    return {
        "product": {
            "product_id": product.product_id,
            "code": product.code,
            "name_ar": product.name_ar,
            "name_en": product.name_en,
            "unit": product.unit_big,
        },
        "period": {"start": start.isoformat(), "end": end.isoformat(),
                   "branch_id": branch_id or 0},
        "opening": money(opening),
        "rows": rows,
        "totals": {k: money(v) for k, v in tot.items()} | {"closing": closing},
        # When the period ends today, the last closing must equal live on-hand.
        "reconciles": (end >= now and abs(closing - money(on_hand)) < 0.01),
        "on_hand_now": money(on_hand),
    }


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
