"""Automation/intelligence read service: expiry risk, low-stock, smart reorder,
and a lightweight sales forecast.

These power the dashboard alert panels and the scheduled jobs. All are read-only
and per-branch / consolidated. The forecast is a transparent moving-average +
trend (Prophet is the documented production upgrade; this keeps the stack
dependency-light and fully runnable).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, as_date, available_stock_filter, branch_filter, money


def expiry_risk(session: Session, branch_id: int | None = None, horizon_days: int = 90) -> dict:
    """Batches expiring within the horizon, bucketed 7 / 30 / 90 days, plus the
    expected loss (qty x buy_price) and any already-expired (lock candidates)."""
    rows = session.execute(
        select(
            m.StockBatch.exp_date,
            m.StockBatch.amount,
            m.StockBatch.buy_price,
            m.Product.name_ar,
            m.Product.name_en,
            m.Branch.name_ar.label("branch"),
        )
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(
            m.StockBatch.amount > 0,
            m.StockBatch.exp_date != None,  # noqa: E711
            branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date <= TODAY + timedelta(days=horizon_days),
        )
        .order_by(m.StockBatch.exp_date.asc())
    ).all()

    buckets = {"expired": [], "d7": [], "d30": [], "d90": []}
    total_loss = 0.0
    for exp, amount, buy, name_ar, name_en, branch in rows:
        days = (exp - TODAY).days
        loss = float(amount) * float(buy)
        item = {
            "name_ar": name_ar,
            "name_en": name_en,
            "branch": branch,
            "exp_date": exp.isoformat(),
            "days_left": days,
            "qty": money(amount),
            "expected_loss": money(loss),
        }
        if days <= 0:
            buckets["expired"].append(item)
        elif days <= 7:
            buckets["d7"].append(item)
            total_loss += loss
        elif days <= 30:
            buckets["d30"].append(item)
            total_loss += loss
        else:
            buckets["d90"].append(item)
            total_loss += loss
    return {
        "horizon_days": horizon_days,
        "expected_loss_within_horizon": money(total_loss),
        "counts": {k: len(v) for k, v in buckets.items()},
        "buckets": buckets,
    }


def low_stock(session: Session, branch_id: int | None = None, limit: int = 100) -> list[dict]:
    """Products whose available qty is below their configured ``min_stock``."""
    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    stmt = (
        select(m.Product, func.coalesce(on_hand.c.qty, 0).label("on_hand"))
        .join(on_hand, on_hand.c.pid == m.Product.product_id, isouter=True)
        .where(
            m.Product.is_active == True,  # noqa: E712
            m.Product.is_deleted == False,  # noqa: E712
            func.coalesce(on_hand.c.qty, 0) < m.Product.min_stock,
        )
        .order_by((func.coalesce(on_hand.c.qty, 0) - m.Product.min_stock).asc())
        .limit(limit)
    )
    out = []
    for p, qty in session.execute(stmt):
        on_hand_qty = float(qty)
        out.append(
            {
                "product_id": p.product_id,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "on_hand": money(on_hand_qty),
                "min_stock": money(p.min_stock),
                "shortfall": money(float(p.min_stock or 0) - on_hand_qty),
            }
        )
    return out


def _avg_daily_consumption(session: Session, branch_id: int | None, days: int = 30) -> dict[int, float]:
    """Average units sold per day per product over the trailing window."""
    start = TODAY - timedelta(days=days)
    rows = session.execute(
        select(m.SaleLine.product_id, func.sum(m.SaleLine.amount))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            as_date(m.Sale.sale_date) >= start,
        )
        .group_by(m.SaleLine.product_id)
    ).all()
    return {pid: float(total) / days for pid, total in rows}


def smart_reorder(
    session: Session, branch_id: int | None = None, lead_time_days: int = 7, cover_days: int = 30
) -> list[dict]:
    """Draft purchase suggestions: for each below-min product, order enough to
    cover ``cover_days`` of consumption beyond the lead time. Drafts only — a
    human approves. Transfer-aware hint: flags when the other branch is
    overstocked on the same item."""
    consumption = _avg_daily_consumption(session, branch_id)
    shorts = low_stock(session, branch_id, limit=500)

    # On-hand at the OTHER branch, for the transfer hint (only when scoped).
    other_on_hand: dict[int, float] = {}
    if branch_id:
        other = session.execute(
            select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
            .where(available_stock_filter(), m.StockBatch.branch_id != branch_id)
            .group_by(m.StockBatch.product_id)
        ).all()
        other_on_hand = {pid: float(q) for pid, q in other}

    out = []
    for item in shorts:
        pid = item["product_id"]
        daily = consumption.get(pid, 0.0)
        target = daily * (lead_time_days + cover_days)
        suggested = max(item["min_stock"] - item["on_hand"], target - item["on_hand"])
        suggested = round(max(suggested, 0), 0)
        if suggested <= 0:
            continue
        transfer_available = other_on_hand.get(pid, 0.0)
        out.append(
            {
                **item,
                "avg_daily_consumption": round(daily, 2),
                "suggested_qty": suggested,
                "transfer_candidate": transfer_available > suggested,
                "transfer_qty_available_other_branch": money(transfer_available),
                "reason": "below_min",
            }
        )
    out.sort(key=lambda r: r["shortfall"], reverse=True)
    return out


def forecast(session: Session, product_id: int, branch_id: int | None = None, days: int = 30) -> dict:
    """Naive but honest forecast: trailing daily average projected forward, with
    a simple linear trend. Documented stand-in for Prophet."""
    window = 60
    start = TODAY - timedelta(days=window)
    rows = session.execute(
        select(as_date(m.Sale.sale_date), func.sum(m.SaleLine.amount))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.SaleLine.product_id == product_id,
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            as_date(m.Sale.sale_date) >= start,
        )
        .group_by(as_date(m.Sale.sale_date))
    ).all()
    by_day = {str(d): float(q) for d, q in rows}
    series = [by_day.get((start + timedelta(days=i)).isoformat(), 0.0) for i in range(window)]
    if not any(series):
        return {"product_id": product_id, "daily_avg": 0.0, "projected_units": 0.0, "method": "moving_average"}
    first_half = sum(series[: window // 2]) / (window // 2)
    second_half = sum(series[window // 2 :]) / (window // 2)
    daily_avg = sum(series) / window
    trend = (second_half - first_half) / (window // 2)  # per-day slope
    projected = sum(max(daily_avg + trend * i, 0) for i in range(1, days + 1))
    return {
        "product_id": product_id,
        "daily_avg": round(daily_avg, 2),
        "trend_per_day": round(trend, 3),
        "horizon_days": days,
        "projected_units": round(projected, 1),
        "method": "moving_average+trend (Prophet upgrade documented)",
    }
