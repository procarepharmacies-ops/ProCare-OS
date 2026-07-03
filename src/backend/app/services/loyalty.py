"""Loyalty points — earn on sales, redeem as an instant POS discount.

Rates come from ``settings`` (env-overridable per pharmacy):
  * earn:   every ``loyalty_egp_per_point`` EGP of net spend = 1 whole point;
  * redeem: each point is worth ``loyalty_point_value`` EGP off the invoice.

``customers.loyalty_points`` is the running balance; every movement is written
to ``loyalty_transactions`` (earn / redeem / clawback / adjust) so the balance
is always auditable. All mutations here run inside the caller's transaction —
``pos.create_sale`` / ``pos.return_sale`` commit or roll back the lot.
"""
from __future__ import annotations

import math

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m


class LoyaltyError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def points_for_spend(net: float) -> float:
    """Whole points earned for a net spend (floor, never negative)."""
    per = float(settings.loyalty_egp_per_point)
    if per <= 0 or net <= 0:
        return 0.0
    return float(math.floor(float(net) / per))


def redemption_value(points: float) -> float:
    """EGP value of redeeming ``points``."""
    return round(float(points) * float(settings.loyalty_point_value), 2)


def award_for_sale(session: Session, sale: m.Sale) -> float:
    """Earn points on a (non-return) sale with a customer. No commit."""
    if sale.customer_id is None or sale.is_return:
        return 0.0
    pts = points_for_spend(float(sale.total_net))
    if pts <= 0:
        return 0.0
    customer = session.get(m.Customer, sale.customer_id)
    customer.loyalty_points = float(customer.loyalty_points or 0) + pts
    session.add(
        m.LoyaltyTransaction(
            customer_id=sale.customer_id,
            sale_id=sale.sale_id,
            points_delta=pts,
            kind="earn",
            note=f"نقاط شراء فاتورة #{sale.sale_id} / earned on sale",
        )
    )
    return pts


def redeem_on_sale(
    session: Session, customer_id: int, points: float
) -> tuple[float, "m.LoyaltyTransaction"]:
    """Spend ``points`` (whole number). Returns (EGP value, the transaction) —
    the caller applies the value as an invoice discount and sets the
    transaction's ``sale_id`` once the sale row has an id. No commit.
    Raises LoyaltyError if the customer doesn't have enough points.
    """
    points = float(math.floor(float(points)))
    if points <= 0:
        raise LoyaltyError("bad_points", "عدد النقاط يجب أن يكون أكبر من صفر / points must be positive")
    customer = session.get(m.Customer, customer_id)
    if customer is None:
        raise LoyaltyError("customer_not_found", "العميل غير موجود / customer not found")
    balance = float(customer.loyalty_points or 0)
    if points > balance + 1e-9:
        raise LoyaltyError(
            "insufficient_points",
            f"نقاط غير كافية: الرصيد {balance:g} والمطلوب {points:g} / not enough loyalty points",
        )
    customer.loyalty_points = balance - points
    tx = m.LoyaltyTransaction(
        customer_id=customer_id,
        points_delta=-points,
        kind="redeem",
        note="استبدال نقاط بخصم / points redeemed as discount",
    )
    session.add(tx)
    return redemption_value(points), tx


def clawback_for_return(session: Session, ret: m.Sale) -> float:
    """On a return, claw back the points the refunded amount had earned
    (never taking the balance below zero). No commit."""
    if ret.customer_id is None:
        return 0.0
    pts = points_for_spend(float(ret.total_net))
    if pts <= 0:
        return 0.0
    customer = session.get(m.Customer, ret.customer_id)
    balance = float(customer.loyalty_points or 0)
    pts = min(pts, balance)  # a redeemed-then-returned edge case can't go negative
    if pts <= 0:
        return 0.0
    customer.loyalty_points = balance - pts
    session.add(
        m.LoyaltyTransaction(
            customer_id=ret.customer_id,
            sale_id=ret.sale_id,
            points_delta=-pts,
            kind="clawback",
            note=f"استرداد نقاط مرتجع #{ret.sale_id} / clawback on return",
        )
    )
    return pts


def summary(session: Session, customer_id: int, limit: int = 30) -> dict:
    """Balance + recent movements + what the balance is worth in EGP."""
    customer = session.get(m.Customer, customer_id)
    if customer is None:
        raise LoyaltyError("customer_not_found", "العميل غير موجود / customer not found")
    txs = session.scalars(
        select(m.LoyaltyTransaction)
        .where(m.LoyaltyTransaction.customer_id == customer_id)
        .order_by(desc(m.LoyaltyTransaction.created_at), desc(m.LoyaltyTransaction.loyalty_tx_id))
        .limit(limit)
    ).all()
    balance = float(customer.loyalty_points or 0)
    return {
        "customer_id": customer_id,
        "customer": customer.name_ar,
        "points": balance,
        "value_egp": redemption_value(balance),
        "earn_rate_egp_per_point": float(settings.loyalty_egp_per_point),
        "point_value_egp": float(settings.loyalty_point_value),
        "history": [
            {
                "id": t.loyalty_tx_id,
                "sale_id": t.sale_id,
                "points": float(t.points_delta),
                "kind": t.kind,
                "note": t.note,
                "at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txs
        ],
    }
