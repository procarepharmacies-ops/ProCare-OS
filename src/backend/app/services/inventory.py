"""Inventory / catalogue read service.

Product list with on-hand stock, and per-product FEFO batch lookup. "Available"
stock follows the data-quality rule (positive and not expired).
"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, available_stock_filter, branch_filter, money


def list_products(
    session: Session,
    branch_id: int | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[dict]:
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
        .where(m.Product.is_deleted == False)  # noqa: E712
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                m.Product.name_ar.like(like),
                m.Product.name_en.like(like),
                m.Product.scientific_name.like(like),
                m.Product.code.like(like),
            )
        )
    stmt = stmt.order_by(m.Product.name_ar).limit(limit)
    out = []
    for p, qty in session.execute(stmt):
        on_hand_qty = money(qty)
        out.append(
            {
                "product_id": p.product_id,
                "code": p.code,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "scientific_name": p.scientific_name,
                "sell_price": money(p.sell_price),
                "buy_price": money(p.buy_price),
                "min_stock": money(p.min_stock),
                "on_hand": on_hand_qty,
                "is_controlled": p.is_controlled,
                "shelf_location": p.shelf_location,
                "low": on_hand_qty < float(p.min_stock or 0),
            }
        )
    return out


def product_batches(session: Session, product_id: int, branch_id: int | None = None) -> list[dict]:
    """All live batches for a product, FEFO-ordered (first to expire first)."""
    stmt = (
        select(m.StockBatch, m.Branch.name_ar)
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(
            m.StockBatch.product_id == product_id,
            m.StockBatch.amount > 0,
            branch_filter(m.StockBatch, branch_id),
        )
        .order_by(m.StockBatch.exp_date.asc().nulls_last())
    )
    out = []
    for batch, branch_name in session.execute(stmt):
        expired = batch.exp_date is not None and batch.exp_date <= TODAY
        out.append(
            {
                "batch_id": batch.batch_id,
                "branch": branch_name,
                "amount": money(batch.amount),
                "exp_date": batch.exp_date.isoformat() if batch.exp_date else None,
                "sell_price": money(batch.sell_price),
                "buy_price": money(batch.buy_price),
                "expired": expired,
            }
        )
    return out


def product_insight(session: Session, product_id: int, branch_id: int | None = None) -> dict | None:
    """Drill-down for a product: identity, on-hand per branch, a 30-day demand
    forecast, and recent sales — composed from existing services so a dashboard
    'second click' shows the detail behind a number."""
    from app.services import alerts

    p = session.get(m.Product, product_id)
    if p is None:
        return None

    # On-hand per branch (available = amount>0, non-expired).
    rows = session.execute(
        select(m.Branch.branch_id, m.Branch.name_ar, func.coalesce(func.sum(m.StockBatch.amount), 0))
        .select_from(m.Branch)
        .join(
            m.StockBatch,
            (m.StockBatch.branch_id == m.Branch.branch_id)
            & (m.StockBatch.product_id == product_id)
            & available_stock_filter(),
            isouter=True,
        )
        .group_by(m.Branch.branch_id, m.Branch.name_ar)
    ).all()
    per_branch = [{"branch_id": bid, "branch": name, "on_hand": money(qty)} for bid, name, qty in rows]

    # Recent sales of this product (last 20 lines).
    recent = session.execute(
        select(m.Sale.sale_id, m.Sale.sale_date, m.SaleLine.amount, m.SaleLine.total_sell)
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(m.SaleLine.product_id == product_id, m.Sale.is_return == False)  # noqa: E712
        .order_by(m.Sale.sale_date.desc())
        .limit(20)
    ).all()
    recent_sales = [
        {"sale_id": sid, "date": d.isoformat() if d else None, "qty": money(amt), "total": money(tot)}
        for sid, d, amt, tot in recent
    ]

    forecast = alerts.forecast(session, product_id, branch_id, days=30)

    return {
        "product_id": p.product_id,
        "name_ar": p.name_ar,
        "name_en": p.name_en,
        "scientific_name": p.scientific_name,
        "sell_price": money(p.sell_price),
        "buy_price": money(p.buy_price),
        "on_hand_by_branch": per_branch,
        "total_on_hand": money(sum(b["on_hand"] for b in per_branch)),
        "forecast_30d": forecast,
        "recent_sales": recent_sales,
    }


def adjust_stock(
    session: Session,
    batch_id: int,
    new_amount: float,
    *,
    reason: str = "adjust",
    employee_id: int | None = None,
) -> dict:
    """Manual stock adjustment / stock-count correction (eStock's
    Product_amount_update + Product_amount_reg_update): set a batch to the
    physically-counted quantity and record the delta in the audit trail."""
    from app.services.pos import POSError

    batch = session.get(m.StockBatch, batch_id)
    if batch is None:
        raise POSError("batch_not_found", f"التشغيلة غير موجودة #{batch_id} / batch not found")
    if new_amount < 0:
        raise POSError("bad_quantity", "الكمية لا يمكن أن تكون سالبة / amount cannot be negative")
    delta = round(float(new_amount) - float(batch.amount), 3)
    if delta == 0:
        return {"batch_id": batch_id, "amount": money(batch.amount), "delta": 0}
    batch.amount = float(new_amount)
    session.add(
        m.StockMovement(
            batch_id=batch.batch_id,
            branch_id=batch.branch_id,
            delta=delta,
            reason="adjust" if reason not in ("adjust", "writeoff") else reason,
            employee_id=employee_id,
        )
    )
    session.commit()
    return {"batch_id": batch_id, "amount": money(new_amount), "delta": money(delta)}


def set_shelf_location(session: Session, product_id: int, shelf_location: str | None) -> dict:
    """Merchandising: set/clear a product's physical shelf/place code."""
    from app.services.pos import POSError

    product = session.get(m.Product, product_id)
    if product is None or product.is_deleted:
        raise POSError("product_not_found", f"صنف غير موجود #{product_id} / product not found")
    product.shelf_location = (shelf_location or "").strip() or None
    session.commit()
    return {"product_id": product_id, "shelf_location": product.shelf_location}
