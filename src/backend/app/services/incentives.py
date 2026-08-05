"""Incentive-list builder — the CEO's "push the most profitable brand of each
active ingredient" strategy.

A customer asks for a molecule (e.g. ESOMEPRAZOLE); several brands sit on the
shelf at different margins. This groups the catalogue by active ingredient
(``products.scientific_name``) and, within each ingredient that has competing
brands, ranks them by profitability so the CEO can put the top 2-3 on the
incentive list the cashiers earn from (see ``api/incentives.py``).

"Most profitable" is deliberately not fixed — the same ingredient's winner
changes with the lens, so all three are returned and the UI toggles:
  * ``egp_margin``   — profit in pounds per unit (sell − buy). Absolute earner.
  * ``margin_pct``   — profit proportion (margin ÷ sell). Markup efficiency.
  * ``profit_volume``— margin × units sold in the window. Realised contribution
                       (rewards what already sells — weakest at *steering*).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import branch_filter, money, today

METRICS = ("egp_margin", "margin_pct", "profit_volume")


def _metric_value(metric: str, sell: float, buy: float, vol: float) -> float:
    margin = sell - buy
    if metric == "margin_pct":
        return round(100.0 * margin / sell, 2) if sell else 0.0
    if metric == "profit_volume":
        return round(margin * vol, 2)
    return round(margin, 2)  # egp_margin (default)


def incentive_candidates(
    session: Session,
    metric: str = "egp_margin",
    top_n: int = 3,
    branch_id: int | None = None,
    window_days: int = 90,
    min_brands: int = 2,
    search: str | None = None,
    max_ingredients: int = 400,
) -> dict:
    """Active ingredients (with ≥``min_brands`` competing brands) and the top
    ``top_n`` most-profitable brands of each, by ``metric``. Each brand carries
    all three metric values so the UI can re-rank live, plus its current
    ``incentive_points`` so the CEO sees what's already on the list."""
    if metric not in METRICS:
        metric = "egp_margin"
    top_n = max(1, min(top_n, 5))

    # 90-day sold units per product (branch-scoped), for the volume metric.
    cutoff = today() - timedelta(days=window_days)
    vol_rows = session.execute(
        select(m.SaleLine.product_id, func.coalesce(func.sum(m.SaleLine.amount), 0))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            m.Sale.sale_date >= cutoff,
            branch_filter(m.Sale, branch_id),
        )
        .group_by(m.SaleLine.product_id)
    ).all()
    vol = {pid: float(q or 0) for pid, q in vol_rows}

    # Qualifying products: real molecule, real prices. NB: no func.trim/length
    # here — the production instance is SQL Server 2008 (TRIM/LENGTH absent);
    # the whitespace-only guard is done in Python below.
    stmt = select(m.Product).where(
        m.Product.is_deleted == False,  # noqa: E712
        m.Product.scientific_name.is_not(None),
        m.Product.scientific_name != "",
        m.Product.sell_price > 0,
        m.Product.buy_price > 0,
    )
    if search:
        stmt = stmt.where(m.Product.scientific_name.ilike(f"%{search.strip()}%"))
    products = session.scalars(stmt).all()

    # Group by active ingredient.
    groups: dict[str, list] = {}
    for p in products:
        key = (p.scientific_name or "").strip().upper()
        if not key:
            continue
        groups.setdefault(key, []).append(p)

    out_groups = []
    on_list = 0
    for ingredient, brands in groups.items():
        if len(brands) < min_brands:
            continue

        def brand_row(p):
            sell, buy = float(p.sell_price), float(p.buy_price)
            v = vol.get(p.product_id, 0.0)
            return {
                "product_id": p.product_id,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "code": p.code,
                "sell_price": money(sell),
                "buy_price": money(buy),
                "egp_margin": money(sell - buy),
                "margin_pct": _metric_value("margin_pct", sell, buy, v),
                "profit_volume": _metric_value("profit_volume", sell, buy, v),
                "sold_window": money(v),
                "incentive_points": money(p.incentive_points),
            }

        rows = [brand_row(p) for p in brands]
        rows.sort(key=lambda r: r[metric], reverse=True)
        top = rows[:top_n]
        on_list += sum(1 for r in top if r["incentive_points"] > 0)
        # A group is only interesting if the top brands actually differ in
        # profitability — a best margin worth steering toward.
        out_groups.append({
            "ingredient": ingredient,
            "brand_count": len(brands),
            "top": top,
            "best_margin": top[0]["egp_margin"] if top else 0,
        })

    # Surface the ingredients with the biggest profit headroom first.
    out_groups.sort(key=lambda g: g["best_margin"], reverse=True)
    total = len(out_groups)
    out_groups = out_groups[:max_ingredients]

    return {
        "metric": metric,
        "top_n": top_n,
        "window_days": window_days,
        "ingredient_count": total,
        "shown": len(out_groups),
        "already_on_list": on_list,
        "groups": out_groups,
    }


def apply_incentives(session: Session, items: list[dict]) -> dict:
    """Bulk set/clear incentive points. ``items``: [{product_id, points}]. A
    points value of 0 removes the product from the incentive list. Returns the
    counts changed. Atomic (single commit by the caller's session scope)."""
    set_count = clear_count = missing = 0
    for it in items:
        pid = it.get("product_id")
        pts = float(it.get("points") or 0)
        product = session.get(m.Product, pid) if pid is not None else None
        if product is None or product.is_deleted:
            missing += 1
            continue
        product.incentive_points = pts
        if pts > 0:
            set_count += 1
        else:
            clear_count += 1
    session.commit()
    return {"set": set_count, "cleared": clear_count, "missing": missing}
