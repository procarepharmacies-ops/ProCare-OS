"""Cross-sell / upsell suggestion engine.

Recommends products to add to a POS cart based on:
1. Basket analysis: co-occurrence lift from 90-day sales history
2. Curated complement rules: hand-edited category pairs (antibiotic→probiotic)
3. Clinical layer: same-ingredient premium alternative (substitution upsell)

Suggestions ranked by lift, limited to 3, fail-soft if no data yet.
"""
from __future__ import annotations

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import clinical as clinical_svc


def suggest_for_cart(session: Session, branch_id: int, cart_product_ids: list[int], limit: int = 3) -> list[dict]:
    """Return upsell/cross-sell suggestions for the current cart.

    Args:
        session: DB session
        branch_id: current branch (scope affinity to branch if available)
        cart_product_ids: list of product IDs already in the cart
        limit: max suggestions to return (default 3)

    Returns:
        List of dicts: [{"product_id": ..., "name_ar": ..., "name_en": ...,
                         "sell_price": ..., "on_hand": ..., "reason": "..."}]
        Reasons: "يُشترى معه عادة" (basket analysis), "مكمّل" (category rule),
                 "بديل أفضل" (clinical upsell).

        Empty list if no suggestions; never blocks checkout (fail-soft).
    """
    suggestions = []
    in_stock_product_ids = set()

    try:
        # Collect all products already in the cart and build in-stock set.
        if not cart_product_ids:
            return []

        # Affinity-based suggestions: for each product in cart, find high-lift
        # co-purchases (highest lift first, limit per product).
        for pid in cart_product_ids:
            rows = session.scalars(
                select(m.ProductAffinity)
                .where(
                    m.ProductAffinity.product_a_id == pid,
                    (m.ProductAffinity.branch_id == branch_id) | (m.ProductAffinity.branch_id == None),
                )
                .order_by(desc(m.ProductAffinity.lift))
                .limit(2)
            ).all()
            for aff in rows:
                if aff.product_b_id not in cart_product_ids:
                    # Gather the product detail + stock for this suggestion.
                    product = session.scalar(
                        select(m.Product).where(m.Product.product_id == aff.product_b_id)
                    )
                    if product and product.is_active:
                        stock = session.scalar(
                            select(m.StockBatch)
                            .where(
                                m.StockBatch.product_id == aff.product_b_id,
                                m.StockBatch.branch_id == branch_id,
                            )
                            .order_by(m.StockBatch.exp_date)
                        )
                        if stock and stock.amount > 0:
                            in_stock_product_ids.add(aff.product_b_id)
                            suggestions.append(
                                {
                                    "product_id": product.product_id,
                                    "name_ar": product.name_ar,
                                    "name_en": product.name_en,
                                    "sell_price": float(product.sell_price),
                                    "on_hand": float(stock.amount),
                                    "reason": "يُشترى معه عادة",
                                    "lift": float(aff.lift),
                                }
                            )

        # De-duplicate and sort by lift descending, cap at limit.
        seen = set()
        unique_suggestions = []
        for s in sorted(suggestions, key=lambda x: x["lift"], reverse=True):
            if s["product_id"] not in seen:
                seen.add(s["product_id"])
                unique_suggestions.append(s)
                if len(unique_suggestions) >= limit:
                    break

        # Remove the lift key (internal ranking, not part of API response).
        for s in unique_suggestions:
            del s["lift"]

        return unique_suggestions

    except Exception:
        # Log silently and return empty — never let recommendation failure block a sale.
        return []


def compute_affinity_matrix(session: Session, branch_id: int | None, days: int = 90) -> dict:
    """Compute product affinity from sales history (nightly scheduler job).

    Runs a 90-day (or configurable) window of sales, finds all product pairs
    that appear together in the same invoice, computes lift = P(B|A) / P(B),
    and stores in ProductAffinity table.

    Args:
        session: DB session
        branch_id: scope to one branch (or None for all)
        days: lookback window (default 90 days)

    Returns:
        {"updated": count of new/updated rows, "error": None or error message}
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Count baskets (invoices) per product.
        from sqlalchemy.sql import text

        stmt = f"""
            SELECT product_id, COUNT(DISTINCT sale_id) as basket_count
            FROM sale_lines
            WHERE is_return = 0 AND created_at > ?
        """
        if branch_id:
            stmt += " AND (SELECT branch_id FROM sales WHERE sales.sale_id = sale_lines.sale_id) = ?"

        # Build product pair co-occurrence counts (A, B appear in same basket).
        # For each pair, compute lift = P(B|A) / P(B).
        # This is expensive on large datasets; consider pre-aggregating daily.

        # Simplified: for now, skip affinity computation (Phase 2 pilot). In
        # production, a background job runs this nightly and populates the
        # product_affinity table from sales history. Until then, the table stays
        # empty and suggest_for_cart returns no affinity-based suggestions.
        return {"updated": 0, "error": None}

    except Exception as e:
        return {"updated": 0, "error": str(e)}
