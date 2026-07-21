"""Decision card generation (Phase 5): creates actionable briefing items from forecast state.

Runs nightly: checks forecast, inventory, and expiry data, then creates decision cards
for manager review (stockout risks, below-min alerts, expiring items, overstocked).
Fail-soft: if generation fails, pharmacy operations continue unaffected.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import models as m


def _create_or_update_card(
    session: Session,
    branch_id: int,
    card_type: str,
    severity: str,
    title_ar: str,
    title_en: str,
    body_ar: str,
    body_en: str,
    action_type: str | None = None,
    ref_product_id: int | None = None,
    ref_purchase_id: int | None = None,
) -> m.DecisionCard:
    """Create or update a decision card. Idempotent: deduplicates on (branch, product, type)."""
    existing = session.scalar(
        select(m.DecisionCard).where(
            m.DecisionCard.branch_id == branch_id,
            m.DecisionCard.card_type == card_type,
            m.DecisionCard.ref_product_id == ref_product_id,
            m.DecisionCard.status == "open",
        )
    )
    if existing:
        existing.title_ar = title_ar
        existing.title_en = title_en
        existing.body_ar = body_ar
        existing.body_en = body_en
        existing.severity = severity
        existing.action_type = action_type
        return existing

    card = m.DecisionCard(
        branch_id=branch_id,
        card_type=card_type,
        severity=severity,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
        action_type=action_type,
        ref_product_id=ref_product_id,
        ref_purchase_id=ref_purchase_id,
        status="open",
    )
    session.add(card)
    return card


def generate_stockout_risk_cards(session: Session, days_ahead: int = 7) -> int:
    """Create decision cards for products forecasted to stockout within N days."""
    count = 0
    forecasts = session.scalars(
        select(m.Forecast)
        .where(
            m.Forecast.stockout_date.isnot(None),
            m.Forecast.stockout_date <= date.today() + timedelta(days=days_ahead),
            m.Forecast.stockout_date >= date.today(),
        )
        .distinct()
    ).all()

    for forecast in forecasts:
        product = session.get(m.Product, forecast.product_id)
        if not product:
            continue

        days_until = (forecast.stockout_date - date.today()).days
        action_type = "create_po" if days_until > 3 else "create_transfer"

        title_ar = f"⚠️ {product.name_ar} — نفاد المخزون خلال {days_until} يوم"
        title_en = f"⚠️ {product.name_en or product.name_ar} — Stockout in {days_until} days"
        body_ar = (
            f"المنتج: {product.name_ar}\n"
            f"المخزون الحالي: {forecast.days_of_cover:.1f} يوم\n"
            f"متوسط الطلب اليومي: {forecast.daily_avg:.1f}\n"
            f"تاريخ النفاد المتوقع: {forecast.stockout_date}\n"
            f"السعر الحالي: {product.buy_price} جنيه"
        )
        body_en = (
            f"Product: {product.name_en or product.name_ar}\n"
            f"Current stock cover: {forecast.days_of_cover:.1f} days\n"
            f"Daily avg demand: {forecast.daily_avg:.1f}\n"
            f"Forecasted stockout: {forecast.stockout_date}\n"
            f"Current buy price: {product.buy_price} EGP"
        )
        severity = "critical" if days_until <= 3 else "warning"

        _create_or_update_card(
            session,
            forecast.branch_id,
            "stockout_risk",
            severity,
            title_ar,
            title_en,
            body_ar,
            body_en,
            action_type,
            forecast.product_id,
        )
        count += 1

    return count


def generate_below_min_cards(session: Session) -> int:
    """Create decision cards for products below minimum stock."""
    count = 0
    # Get current stock levels per product×branch, filter below min
    rows = session.execute(
        select(
            m.StockBatch.branch_id,
            m.StockBatch.product_id,
            func.sum(m.StockBatch.quantity).label("qty"),
        )
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .where(
            m.Product.is_active == True,  # noqa: E712
            m.StockBatch.quantity > 0,
        )
        .group_by(m.StockBatch.branch_id, m.StockBatch.product_id)
        .having(func.sum(m.StockBatch.quantity) < m.Product.min_stock)
    ).all()

    for branch_id, product_id, qty in rows:
        product = session.get(m.Product, product_id)
        if not product or product.min_stock == 0:
            continue

        shortage = product.min_stock - qty
        title_ar = f"📉 {product.name_ar} — أقل من الحد الأدنى بـ {shortage:.0f}"
        title_en = f"📉 {product.name_en or product.name_ar} — {shortage:.0f} short of min"
        body_ar = (
            f"المنتج: {product.name_ar}\n"
            f"المخزون الحالي: {qty:.1f}\n"
            f"الحد الأدنى المطلوب: {product.min_stock:.1f}\n"
            f"النقص: {shortage:.1f}"
        )
        body_en = (
            f"Product: {product.name_en or product.name_ar}\n"
            f"Current stock: {qty:.1f}\n"
            f"Minimum required: {product.min_stock:.1f}\n"
            f"Shortage: {shortage:.1f}"
        )

        _create_or_update_card(
            session,
            branch_id,
            "below_min",
            "warning",
            title_ar,
            title_en,
            body_ar,
            body_en,
            "create_po",
            product_id,
        )
        count += 1

    return count


def generate_expiry_warning_cards(session: Session, days_ahead: int = 30) -> int:
    """Create decision cards for items expiring soon (within N days)."""
    count = 0
    expiring_batches = session.scalars(
        select(m.StockBatch)
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .where(
            m.StockBatch.exp_date.isnot(None),
            m.StockBatch.exp_date <= date.today() + timedelta(days=days_ahead),
            m.StockBatch.exp_date > date.today(),
            m.StockBatch.quantity > 0,
            m.Product.is_active == True,  # noqa: E712
        )
        .distinct()
    ).all()

    for batch in expiring_batches:
        product = session.get(m.Product, batch.product_id)
        if not product:
            continue

        days_until = (batch.exp_date - date.today()).days
        value = batch.quantity * product.buy_price

        title_ar = f"⏰ {product.name_ar} — ينتهي خلال {days_until} يوم"
        title_en = f"⏰ {product.name_en or product.name_ar} — Expires in {days_until} days"
        body_ar = (
            f"المنتج: {product.name_ar}\n"
            f"الكمية: {batch.quantity:.1f}\n"
            f"تاريخ الانتهاء: {batch.exp_date}\n"
            f"القيمة: {value:.2f} جنيه\n"
            f"الإجراء: تقليل السعر أو الترويج"
        )
        body_en = (
            f"Product: {product.name_en or product.name_ar}\n"
            f"Quantity: {batch.quantity:.1f}\n"
            f"Expiry date: {batch.exp_date}\n"
            f"Value: {value:.2f} EGP\n"
            f"Action: reduce price or promote"
        )
        severity = "critical" if days_until <= 7 else "warning"

        _create_or_update_card(
            session,
            batch.branch_id,
            "expiry_warning",
            severity,
            title_ar,
            title_en,
            body_ar,
            body_en,
            "promote",
            product_id,
        )
        count += 1

    return count


def generate_overstocked_cards(session: Session, coverage_threshold: float = 60.0) -> int:
    """Create decision cards for overstocked items (>60 days of cover).
    Indicates slow-moving inventory tied up capital."""
    count = 0
    forecasts = session.scalars(
        select(m.Forecast).where(
            m.Forecast.days_of_cover > coverage_threshold,
            m.Forecast.daily_avg > 0,
        )
    ).all()

    for forecast in forecasts:
        product = session.get(m.Product, forecast.product_id)
        if not product or forecast.daily_avg < 0.1:
            continue

        value = forecast.days_of_cover * forecast.daily_avg * product.buy_price
        title_ar = f"📦 {product.name_ar} — مخزون زائد ({forecast.days_of_cover:.0f} يوم)"
        title_en = f"📦 {product.name_en or product.name_ar} — Overstocked ({forecast.days_of_cover:.0f} days)"
        body_ar = (
            f"المنتج: {product.name_ar}\n"
            f"كمية المخزون: {forecast.days_of_cover:.1f} يوم\n"
            f"القيمة المرتبطة: {value:.2f} جنيه\n"
            f"يومياً: {forecast.daily_avg:.1f}\n"
            f"التوصية: دراسة الخصم أو النقل لفرع آخر"
        )
        body_en = (
            f"Product: {product.name_en or product.name_ar}\n"
            f"Stock cover: {forecast.days_of_cover:.1f} days\n"
            f"Tied-up value: {value:.2f} EGP\n"
            f"Daily demand: {forecast.daily_avg:.1f}\n"
            f"Recommendation: consider discount or transfer to another branch"
        )

        _create_or_update_card(
            session,
            forecast.branch_id,
            "overstocked",
            "info",
            title_ar,
            title_en,
            body_ar,
            body_en,
            "adjust_min",
            forecast.product_id,
        )
        count += 1

    return count


def generate_nightly_decision_cards(session: Session) -> dict:
    """Batch generate all decision card types. Runs nightly, idempotent.
    Returns counts by card type."""
    try:
        counts = {
            "stockout_risk": generate_stockout_risk_cards(session),
            "below_min": generate_below_min_cards(session),
            "expiry_warning": generate_expiry_warning_cards(session),
            "overstocked": generate_overstocked_cards(session),
        }
        session.commit()
        return {
            "status": "ok",
            "total_cards_created": sum(counts.values()),
            "by_type": counts,
        }
    except Exception as e:
        session.rollback()
        return {
            "status": "error",
            "message": str(e),
            "total_cards_created": 0,
            "by_type": {},
        }


def get_open_decision_cards(session: Session, branch_id: int | None = None) -> list[dict]:
    """Fetch open decision cards for a branch (or all branches if None).
    Returns sorted by severity (critical → warning → info) then by creation time."""
    query = select(m.DecisionCard).where(m.DecisionCard.status == "open")
    if branch_id:
        query = query.where(m.DecisionCard.branch_id == branch_id)

    severity_order = {"critical": 1, "warning": 2, "info": 3}
    cards = session.scalars(query).all()
    cards.sort(
        key=lambda c: (severity_order.get(c.severity, 99), c.created_at),
    )

    return [
        {
            "card_id": c.card_id,
            "branch_id": c.branch_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "card_type": c.card_type,
            "severity": c.severity,
            "title_ar": c.title_ar,
            "title_en": c.title_en,
            "body_ar": c.body_ar,
            "body_en": c.body_en,
            "action_type": c.action_type,
            "ref_product_id": c.ref_product_id,
            "status": c.status,
        }
        for c in cards
    ]


def dismiss_card(session: Session, card_id: int) -> bool:
    """Dismiss a decision card (mark as dismissed)."""
    card = session.get(m.DecisionCard, card_id)
    if card:
        card.status = "dismissed"
        session.commit()
        return True
    return False


def action_card(session: Session, card_id: int, employee_id: int | None = None) -> bool:
    """Mark a decision card as actioned (action taken by manager)."""
    card = session.get(m.DecisionCard, card_id)
    if card:
        card.status = "actioned"
        card.actioned_at = datetime.utcnow()
        card.actioned_by = employee_id
        session.commit()
        return True
    return False


def archive_old_cards(session: Session, days: int = 7) -> int:
    """Archive decision cards older than N days without action.
    Returns count of archived cards."""
    cutoff = date.today() - timedelta(days=days)
    result = session.execute(
        select(m.DecisionCard)
        .where(
            m.DecisionCard.status.in_(["open", "dismissed"]),
            m.DecisionCard.created_at < cutoff,
        )
    )
    count = 0
    for card in result.scalars():
        card.status = "archived"
        count += 1
    session.commit()
    return count
