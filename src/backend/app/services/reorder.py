"""Reorder proposal generation (Phase 5): forecast-driven PO recommendations.

Runs nightly: analyzes forecasts + stock levels, suggests optimal order quantities
per product×vendor, attempts transfer-first logic (move from other branch before buying),
and groups recommendations by vendor for efficiency. Fail-soft: suggestions never block
pharmacy operations.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TypedDict

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import models as m


class ReorderSuggestion(TypedDict):
    product_id: int
    product_name_ar: str
    product_name_en: str
    current_stock: float
    daily_avg_demand: float
    days_to_stockout: float
    stockout_date: date | None
    suggested_qty: float
    unit_big: str | None
    unit_factor: float
    lead_time_days: int
    buy_price: float
    suggested_vendors: list[dict]  # [{vendor_id, vendor_name, price, qty_in_stock}, ...]
    transfer_available_qty: float  # qty available at other branches
    transfer_from_branch_id: int | None
    priority: str  # critical (days_to_stockout <= 3), urgent (≤7), normal, low


def _current_stock(session: Session, product_id: int, branch_id: int) -> float:
    """Get current on-hand stock for a product at a branch."""
    qty = session.scalar(
        select(func.sum(m.StockBatch.amount)).where(
            m.StockBatch.product_id == product_id,
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
        )
    )
    return float(qty or 0)


def _available_in_other_branches(
    session: Session, product_id: int, exclude_branch_id: int
) -> tuple[float, int | None]:
    """Get total qty available at other branches (excluding current branch).
    Returns (total_qty, branch_id_with_most)."""
    rows = session.execute(
        select(
            m.StockBatch.branch_id,
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(
            m.StockBatch.product_id == product_id,
            m.StockBatch.branch_id != exclude_branch_id,
            m.StockBatch.amount > 0,
        )
        .group_by(m.StockBatch.branch_id)
        .order_by(func.sum(m.StockBatch.amount).desc())
    ).all()

    total_qty = sum(qty for _, qty in rows)
    best_branch_id = rows[0][0] if rows else None
    return float(total_qty), best_branch_id


def _get_vendors_for_product(
    session: Session, product_id: int
) -> list[dict]:
    """Get list of vendors + stock for a product (best price first).
    Returns [{vendor_id, vendor_name_ar, vendor_name_en, price, qty_in_stock}, ...]"""
    # Query purchase history for price + vendors
    vendor_prices = session.execute(
        select(
            m.Vendor.vendor_id,
            m.Vendor.name_ar,
            m.Vendor.name_en,
            func.avg(m.PurchaseLine.buy_price).label("avg_price"),
            func.max(m.Purchase.created_at).label("last_purchase"),
        )
        .join(m.Purchase, m.Purchase.vendor_id == m.Vendor.vendor_id)
        .join(m.PurchaseLine, m.PurchaseLine.purchase_id == m.Purchase.purchase_id)
        .where(
            m.PurchaseLine.product_id == product_id,
            m.Purchase.is_return == False,  # noqa: E712
        )
        .group_by(m.Vendor.vendor_id)
        .order_by(func.avg(m.PurchaseLine.buy_price).asc())
    ).all()

    return [
        {
            "vendor_id": vendor_id,
            "vendor_name_ar": name_ar,
            "vendor_name_en": name_en,
            "price": float(price or 0),
            "last_purchase": last_purchase.isoformat() if last_purchase else None,
        }
        for vendor_id, name_ar, name_en, price, last_purchase in vendor_prices
    ]


def generate_reorder_suggestions(
    session: Session, branch_id: int
) -> list[ReorderSuggestion]:
    """Generate reorder suggestions for a branch based on forecasts.

    Algorithm:
    1. Query forecasts with stockout_date approaching
    2. For each product, calculate optimal order qty (days to stockout + buffer)
    3. Check transfer-first: qty available at other branches
    4. If transfer enough, suggest transfer (qty, from_branch_id)
    5. If transfer insufficient, suggest PO from best-price vendor
    6. Rank by priority (critical → urgent → normal → low)

    Returns list of suggestions, sorted by priority + product name.
    """
    suggestions = []

    forecasts = session.scalars(
        select(m.Forecast)
        .where(
            m.Forecast.branch_id == branch_id,
            m.Forecast.stockout_date.isnot(None),
            m.Forecast.stockout_date <= date.today() + timedelta(days=30),
        )
        .order_by(m.Forecast.stockout_date.asc())
    ).all()

    for forecast in forecasts:
        product = session.get(m.Product, forecast.product_id)
        if not product or not product.is_active:
            continue

        current = _current_stock(session, product.product_id, branch_id)
        days_to_stockout = (forecast.stockout_date - date.today()).days if forecast.stockout_date else 999

        # Safety buffer: order enough to cover lead time + 3 days buffer
        lead_time = 5  # days (configurable per vendor later)
        buffer_days = 3
        coverage_days = days_to_stockout + lead_time + buffer_days

        suggested_qty = max(0, (coverage_days * float(forecast.daily_avg)) - current)
        if suggested_qty < 0.1:
            continue  # No order needed

        # Priority based on urgency
        if days_to_stockout <= 3:
            priority = "critical"
        elif days_to_stockout <= 7:
            priority = "urgent"
        elif days_to_stockout <= 14:
            priority = "normal"
        else:
            priority = "low"

        # Check transfer-first: can we move from another branch?
        transfer_available, best_branch = _available_in_other_branches(
            session, product.product_id, branch_id
        )
        transfer_qty = min(transfer_available, suggested_qty)

        # If transfer covers all, suggest transfer only
        if transfer_qty >= suggested_qty:
            suggestions.append(
                ReorderSuggestion(
                    product_id=product.product_id,
                    product_name_ar=product.name_ar,
                    product_name_en=product.name_en or product.name_ar,
                    current_stock=current,
                    daily_avg_demand=float(forecast.daily_avg),
                    days_to_stockout=days_to_stockout,
                    stockout_date=forecast.stockout_date,
                    suggested_qty=suggested_qty,
                    unit_big=product.unit_big,
                    unit_factor=product.unit_factor,
                    lead_time_days=lead_time,
                    buy_price=product.buy_price,
                    suggested_vendors=[],  # No PO needed
                    transfer_available_qty=transfer_qty,
                    transfer_from_branch_id=best_branch,
                    priority=priority,
                )
            )
        else:
            # Transfer insufficient; need PO
            po_qty = suggested_qty - transfer_qty
            vendors = _get_vendors_for_product(session, product.product_id)

            suggestions.append(
                ReorderSuggestion(
                    product_id=product.product_id,
                    product_name_ar=product.name_ar,
                    product_name_en=product.name_en or product.name_ar,
                    current_stock=current,
                    daily_avg_demand=float(forecast.daily_avg),
                    days_to_stockout=days_to_stockout,
                    stockout_date=forecast.stockout_date,
                    suggested_qty=po_qty,
                    unit_big=product.unit_big,
                    unit_factor=product.unit_factor,
                    lead_time_days=lead_time,
                    buy_price=product.buy_price,
                    suggested_vendors=vendors,
                    transfer_available_qty=transfer_qty,
                    transfer_from_branch_id=best_branch if transfer_qty > 0 else None,
                    priority=priority,
                )
            )

    # Sort by priority + days_to_stockout (most urgent first)
    priority_order = {"critical": 1, "urgent": 2, "normal": 3, "low": 4}
    suggestions.sort(
        key=lambda s: (
            priority_order.get(s["priority"], 99),
            s["days_to_stockout"],
            s["product_name_ar"],
        )
    )

    return suggestions


def summarize_suggestions(suggestions: list[ReorderSuggestion]) -> dict:
    """Summarize reorder suggestions by vendor + priority.

    Returns grouped view suitable for manager dashboards:
    {
      "total_suggestions": int,
      "by_priority": {"critical": count, "urgent": count, ...},
      "by_vendor": {vendor_name: {"qty": sum, "line_items": [...]}, ...},
      "transfer_available": total_qty_available_to_transfer,
    }
    """
    by_priority = {"critical": 0, "urgent": 0, "normal": 0, "low": 0}
    by_vendor = {}
    transfer_total = 0.0

    for sugg in suggestions:
        by_priority[sugg["priority"]] += 1

        if sugg["suggested_vendors"]:
            # PO needed
            best_vendor = sugg["suggested_vendors"][0]
            vendor_name = best_vendor["vendor_name_ar"]
            if vendor_name not in by_vendor:
                by_vendor[vendor_name] = {"qty": 0, "line_items": []}
            by_vendor[vendor_name]["qty"] += sugg["suggested_qty"]
            by_vendor[vendor_name]["line_items"].append(
                {
                    "product_ar": sugg["product_name_ar"],
                    "product_en": sugg["product_name_en"],
                    "qty": sugg["suggested_qty"],
                    "unit_big": sugg["unit_big"],
                    "price": best_vendor["price"],
                    "days_to_stockout": sugg["days_to_stockout"],
                }
            )

        if sugg["transfer_available_qty"] > 0:
            transfer_total += sugg["transfer_available_qty"]

    return {
        "total_suggestions": len(suggestions),
        "by_priority": by_priority,
        "by_vendor": by_vendor,
        "transfer_available_total": transfer_total,
    }
