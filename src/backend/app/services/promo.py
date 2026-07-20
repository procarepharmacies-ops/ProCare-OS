"""Promo codes (كود الخصم) — discount codes redeemable at POS.

Tracks code validity, usage limits, discount type (% or fixed EGP), and campaigns.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import models as m

logger = logging.getLogger(__name__)


class PromoError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def create_promo_code(
    session: Session,
    code: str,
    discount_type: str,
    discount_value: float,
    valid_from: datetime,
    valid_until: datetime,
    description_ar: str | None = None,
    description_en: str | None = None,
    max_uses: int | None = None,
    created_by: int | None = None,
) -> m.PromoCode:
    """Create a new promo code (no commit).

    Args:
        session: Database session
        code: Unique code (e.g., 'SUMMER20', 'FIRSTBUY')
        discount_type: 'percentage' or 'fixed'
        discount_value: Discount amount (% or EGP)
        valid_from: Start datetime
        valid_until: End datetime
        description_ar: Arabic description (optional)
        description_en: English description (optional)
        max_uses: Maximum redemptions (None = unlimited)
        created_by: Employee ID (optional)

    Returns:
        New PromoCode object
    """
    # Check for duplicate code
    existing = session.query(m.PromoCode).filter(m.PromoCode.code == code).first()
    if existing:
        raise PromoError("duplicate_code", f"Code {code} already exists")

    if valid_from >= valid_until:
        raise PromoError("invalid_dates", "valid_from must be before valid_until")

    if discount_value <= 0:
        raise PromoError("invalid_discount", "discount_value must be positive")

    if discount_type == "percentage" and discount_value > 100:
        raise PromoError("invalid_percentage", "percentage discount cannot exceed 100%")

    promo = m.PromoCode(
        code=code.upper(),
        discount_type=discount_type,
        discount_value=float(discount_value),
        valid_from=valid_from,
        valid_until=valid_until,
        description_ar=description_ar,
        description_en=description_en,
        max_uses=max_uses,
        created_by=created_by,
    )
    session.add(promo)
    return promo


def validate_promo_code(session: Session, code: str, invoice_total: float = 0.0) -> m.PromoCode:
    """Validate a promo code for redemption.

    Checks: code exists, is active, hasn't expired, usage limit not exceeded.

    Raises:
        PromoError if validation fails

    Returns:
        PromoCode object if valid
    """
    promo = session.query(m.PromoCode).filter(m.PromoCode.code == code.upper()).first()

    if not promo:
        raise PromoError("code_not_found", f"Promo code {code} not found")

    if not promo.is_active:
        raise PromoError("code_inactive", f"Promo code {code} is not active")

    now = datetime.now()
    if now < promo.valid_from:
        raise PromoError("code_not_yet_valid", f"Promo code {code} is not yet active")

    if now > promo.valid_until:
        raise PromoError("code_expired", f"Promo code {code} has expired")

    if promo.max_uses and promo.current_uses >= promo.max_uses:
        raise PromoError("code_limit_reached", f"Promo code {code} has reached usage limit")

    return promo


def calculate_discount(promo: m.PromoCode, invoice_total: float) -> tuple[float, str]:
    """Calculate discount amount and message.

    Args:
        promo: PromoCode object
        invoice_total: Invoice total before discount (in EGP)

    Returns:
        (discount_amount, message) tuple
    """
    if promo.discount_type == "percentage":
        discount_amount = (invoice_total * float(promo.discount_value)) / 100
        message = f"Discount {promo.discount_value}%: -{discount_amount:.2f} EGP"
    else:  # fixed
        discount_amount = min(float(promo.discount_value), invoice_total)
        message = f"Discount {promo.code}: -{discount_amount:.2f} EGP"

    return round(discount_amount, 2), message


def redeem_promo_code(session: Session, code: str) -> m.PromoCode:
    """Increment usage counter for a redeemed promo code (no commit).

    Should be called AFTER successful POS sale to track redemption.

    Returns:
        Updated PromoCode object
    """
    promo = validate_promo_code(session, code)
    promo.current_uses += 1
    return promo


def deactivate_promo_code(session: Session, code: str) -> m.PromoCode:
    """Deactivate a promo code (no commit).

    Returns:
        Updated PromoCode object
    """
    promo = session.query(m.PromoCode).filter(m.PromoCode.code == code.upper()).first()
    if not promo:
        raise PromoError("code_not_found", f"Promo code {code} not found")
    promo.is_active = False
    return promo


def get_active_promo_codes(session: Session) -> list[m.PromoCode]:
    """Get all currently valid promo codes.

    Returns:
        List of active PromoCode objects
    """
    now = datetime.now()
    return (
        session.query(m.PromoCode)
        .filter(
            m.PromoCode.is_active == True,  # noqa: E712
            m.PromoCode.valid_from <= now,
            m.PromoCode.valid_until >= now,
        )
        .all()
    )


def get_promo_usage_report(session: Session, code: str | None = None) -> list[dict]:
    """Get usage report for promo codes.

    Args:
        session: Database session
        code: Filter to specific code (optional)

    Returns:
        List of dicts with code, usage, discount_type, discount_value, valid_until, status
    """
    query = session.query(m.PromoCode)
    if code:
        query = query.filter(m.PromoCode.code == code.upper())

    result = []
    for promo in query.all():
        remaining = "unlimited"
        if promo.max_uses:
            remaining = str(max(0, promo.max_uses - promo.current_uses))

        status = "expired"
        if datetime.now() < promo.valid_from:
            status = "not_yet_active"
        elif datetime.now() <= promo.valid_until:
            status = "active" if promo.is_active else "inactive"

        result.append({
            "code": promo.code,
            "discount_type": promo.discount_type,
            "discount_value": float(promo.discount_value),
            "current_uses": promo.current_uses,
            "max_uses": promo.max_uses,
            "remaining_uses": remaining,
            "valid_until": promo.valid_until.isoformat(),
            "status": status,
            "description_ar": promo.description_ar,
            "description_en": promo.description_en,
        })

    return result
