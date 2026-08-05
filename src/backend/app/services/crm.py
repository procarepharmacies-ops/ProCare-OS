"""Phase 3: CRM engagement — RFM segmentation, customer segments, WhatsApp campaigns.

RFM (Recency/Frequency/Monetary) divides customers into actionable segments:
- VIP (محاور): best customers, engage to retain
- Regular (منتظم): steady repeat buyers, nurture growth
- At Risk (مهدد): lapsed but formerly active, win them back
- Dormant (خامل): very old or never purchased, re-activate

Segments computed daily by scheduler; used by WhatsApp automation (Phase 3).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import models as m


def compute_rfm_segments(session: Session) -> dict[int, str]:
    """Recompute RFM segments for all customers.

    Returns: {customer_id: segment_name}
    Updates customer.rfm_segment and customer.last_purchase_date.
    No commit.
    """
    # For each customer: R (days since last purchase), F (# purchases), M (total spend)
    segments = {}
    today = datetime.now().date()

    for customer in session.query(m.Customer).all():
        # Recent: last purchase date
        recent_sale = (
            session.query(m.Sale)
            .filter(m.Sale.customer_id == customer.customer_id, m.Sale.is_return == False)  # noqa: E712
            .order_by(m.Sale.sale_date.desc())
            .first()
        )
        last_purchase = recent_sale.sale_date if recent_sale else None
        recency_days = (datetime.now() - last_purchase).days if last_purchase else 999

        # Frequency: count of purchases in last 2 years
        two_years_ago = datetime.now() - timedelta(days=730)
        frequency = (
            session.query(func.count(m.Sale.sale_id))
            .filter(
                m.Sale.customer_id == customer.customer_id,
                m.Sale.is_return == False,  # noqa: E712
                m.Sale.sale_date >= two_years_ago,
            )
            .scalar()
            or 0
        )

        # Monetary: total spend in last 2 years
        monetary = (
            session.query(func.sum(m.Sale.total_net))
            .filter(
                m.Sale.customer_id == customer.customer_id,
                m.Sale.is_return == False,  # noqa: E712
                m.Sale.sale_date >= two_years_ago,
            )
            .scalar()
            or 0.0
        )
        monetary = float(monetary)

        # Segment logic (configurable thresholds):
        # VIP: recent + frequent + high-spend
        # Regular: steady customers
        # At Risk: used to buy but dormant
        # Dormant: never or very old
        if recency_days <= 30 and frequency >= 12 and monetary >= 5000:
            segment = "vip"
        elif recency_days <= 60 and frequency >= 6 and monetary >= 1000:
            segment = "regular"
        elif recency_days > 60 and recency_days <= 180 and frequency >= 3:
            segment = "at_risk"
        else:
            segment = "dormant"

        customer.rfm_segment = segment
        if last_purchase:
            customer.last_purchase_date = last_purchase
        segments[customer.customer_id] = segment

    return segments


def segment_customers(session: Session, segment: str) -> list[m.Customer]:
    """Get all customers in a given segment (vip/regular/at_risk/dormant)."""
    return session.query(m.Customer).filter(m.Customer.rfm_segment == segment).all()


def segment_counts(session: Session) -> dict[str, int]:
    """Count customers per segment."""
    counts = {}
    for segment in ("vip", "regular", "at_risk", "dormant"):
        count = (
            session.query(func.count(m.Customer.customer_id))
            .filter(m.Customer.rfm_segment == segment)
            .scalar()
            or 0
        )
        counts[segment] = count
    return counts


def segment_summary(session: Session) -> dict:
    """Segment distribution with names + icons."""
    counts = segment_counts(session)
    return {
        "vip": {"ar": "محاور", "en": "VIP", "count": counts["vip"], "icon": "⭐"},
        "regular": {"ar": "منتظم", "en": "Regular", "count": counts["regular"], "icon": "👤"},
        "at_risk": {"ar": "مهدد بالفقد", "en": "At Risk", "count": counts["at_risk"], "icon": "⚠️"},
        "dormant": {"ar": "خامل", "en": "Dormant", "count": counts["dormant"], "icon": "💤"},
    }
