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
