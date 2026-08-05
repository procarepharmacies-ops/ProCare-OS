"""Tests for promo code management (Phase 4)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from app.db import models as m
from app.services import promo as promo_svc


def unique_code(prefix: str) -> str:
    """Generate a unique code using timestamp."""
    return f"{prefix}_{int(time.time() * 1000000) % 1000000}"


@pytest.fixture
def valid_dates() -> tuple[datetime, datetime]:
    """Valid date range for promo codes."""
    now = datetime.now()
    return now - timedelta(days=1), now + timedelta(days=30)


def test_create_promo_code_percentage(session, valid_dates):
    """Test creating a percentage-based promo code."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="SUMMER20",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        description_ar="خصم صيفي",
        description_en="Summer discount",
    )
    session.commit()

    assert promo.code == "SUMMER20"
    assert promo.discount_type == "percentage"
    assert promo.discount_value == 20.0
    assert promo.is_active is True
    assert promo.current_uses == 0
    assert promo.max_uses is None


def test_create_promo_code_fixed(session, valid_dates):
    """Test creating a fixed EGP discount promo code."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="FIXED50",
        discount_type="fixed",
        discount_value=50.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    assert promo.code == "FIXED50"
    assert promo.discount_type == "fixed"
    assert promo.discount_value == 50.0


def test_create_promo_code_uppercase_conversion(session, valid_dates):
    """Test that promo code is converted to uppercase."""
    valid_from, valid_until = valid_dates
    code = unique_code("summer")
    promo = promo_svc.create_promo_code(
        session,
        code=code.lower(),
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    assert promo.code == code.upper()


def test_create_promo_code_with_max_uses(session, valid_dates):
    """Test creating a promo code with usage limit."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="LIMITED100",
        discount_type="percentage",
        discount_value=10.0,
        valid_from=valid_from,
        valid_until=valid_until,
        max_uses=100,
    )
    session.commit()

    assert promo.max_uses == 100
    assert promo.current_uses == 0


def test_create_promo_code_duplicate(session, valid_dates):
    """Test that duplicate promo codes are rejected."""
    valid_from, valid_until = valid_dates
    promo_svc.create_promo_code(
        session,
        code="DUPLICATE",
        discount_type="percentage",
        discount_value=15.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.create_promo_code(
            session,
            code="DUPLICATE",
            discount_type="percentage",
            discount_value=20.0,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    assert "already exists" in exc_info.value.message


def test_create_promo_code_invalid_dates(session):
    """Test that invalid date ranges are rejected."""
    now = datetime.now()
    valid_until = now - timedelta(days=1)
    valid_from = now

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.create_promo_code(
            session,
            code="INVALIDATES",
            discount_type="percentage",
            discount_value=20.0,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    assert "must be before" in exc_info.value.message


def test_create_promo_code_invalid_discount_value(session, valid_dates):
    """Test that non-positive discount values are rejected."""
    valid_from, valid_until = valid_dates

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.create_promo_code(
            session,
            code="INVALID",
            discount_type="percentage",
            discount_value=-10.0,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    assert "positive" in exc_info.value.message


def test_create_promo_code_percentage_exceeds_100(session, valid_dates):
    """Test that percentage discounts over 100% are rejected."""
    valid_from, valid_until = valid_dates

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.create_promo_code(
            session,
            code="TOOBIG",
            discount_type="percentage",
            discount_value=150.0,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    assert "100%" in exc_info.value.message


def test_validate_promo_code_valid(session, valid_dates):
    """Test validating an active, non-expired promo code."""
    valid_from, valid_until = valid_dates
    promo_svc.create_promo_code(
        session,
        code="VALID",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    promo = promo_svc.validate_promo_code(session, "VALID")

    assert promo.code == "VALID"
    assert promo.is_active is True


def test_validate_promo_code_not_found(session):
    """Test validating a non-existent promo code."""
    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.validate_promo_code(session, "NONEXISTENT")

    assert "not found" in exc_info.value.message


def test_validate_promo_code_inactive(session, valid_dates):
    """Test validating an inactive promo code."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="INACTIVE",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    promo.is_active = False
    session.commit()

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.validate_promo_code(session, "INACTIVE")

    assert "not active" in exc_info.value.message


def test_validate_promo_code_not_yet_valid(session):
    """Test validating a promo code that hasn't started yet."""
    now = datetime.now()
    valid_from = now + timedelta(days=7)
    valid_until = now + timedelta(days=37)

    promo_svc.create_promo_code(
        session,
        code="FUTURE",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.validate_promo_code(session, "FUTURE")

    assert "not yet active" in exc_info.value.message


def test_validate_promo_code_expired(session):
    """Test validating an expired promo code."""
    now = datetime.now()
    valid_from = now - timedelta(days=37)
    valid_until = now - timedelta(days=7)

    promo_svc.create_promo_code(
        session,
        code="EXPIRED",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.validate_promo_code(session, "EXPIRED")

    assert "expired" in exc_info.value.message


def test_validate_promo_code_limit_reached(session, valid_dates):
    """Test validating a promo code that has reached its usage limit."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="EXHAUSTED",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        max_uses=1,
    )
    session.commit()

    # Use up the limit
    promo.current_uses = 1
    session.commit()

    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.validate_promo_code(session, "EXHAUSTED")

    assert "limit" in exc_info.value.message


def test_calculate_discount_percentage(session, valid_dates):
    """Test discount calculation for percentage-based codes."""
    valid_from, valid_until = valid_dates
    code = unique_code("PERCENT")
    promo = promo_svc.create_promo_code(
        session,
        code=code,
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    amount, message = promo_svc.calculate_discount(promo, 100.0)

    assert amount == 20.0
    assert "20" in message and "%" in message


def test_calculate_discount_fixed(session, valid_dates):
    """Test discount calculation for fixed EGP codes."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="FIXED",
        discount_type="fixed",
        discount_value=50.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    amount, message = promo_svc.calculate_discount(promo, 100.0)

    assert amount == 50.0
    assert "50" in message


def test_calculate_discount_fixed_caps_to_invoice_total(session, valid_dates):
    """Test that fixed discount doesn't exceed invoice total."""
    valid_from, valid_until = valid_dates
    code = unique_code("FIXED")
    promo = promo_svc.create_promo_code(
        session,
        code=code,
        discount_type="fixed",
        discount_value=100.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    amount, message = promo_svc.calculate_discount(promo, 50.0)

    assert amount == 50.0  # Capped to invoice total


def test_redeem_promo_code(session, valid_dates):
    """Test redeeming a promo code (incrementing usage)."""
    valid_from, valid_until = valid_dates
    promo_svc.create_promo_code(
        session,
        code="REDEEM",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    promo = promo_svc.redeem_promo_code(session, "REDEEM")
    session.commit()

    assert promo.current_uses == 1

    # Redeem again
    promo = promo_svc.redeem_promo_code(session, "REDEEM")
    session.commit()

    assert promo.current_uses == 2


def test_redeem_promo_code_validates_first(session):
    """Test that redeem fails if code doesn't validate."""
    with pytest.raises(promo_svc.PromoError):
        promo_svc.redeem_promo_code(session, "NONEXISTENT")


def test_deactivate_promo_code(session, valid_dates):
    """Test deactivating a promo code."""
    valid_from, valid_until = valid_dates
    promo_svc.create_promo_code(
        session,
        code="DEACTIVATE",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    promo = promo_svc.deactivate_promo_code(session, "DEACTIVATE")
    session.commit()

    assert promo.is_active is False


def test_deactivate_promo_code_not_found(session):
    """Test deactivating a code that doesn't exist."""
    with pytest.raises(promo_svc.PromoError) as exc_info:
        promo_svc.deactivate_promo_code(session, "NONEXISTENT")

    assert "not found" in exc_info.value.message


def test_get_active_promo_codes(session, valid_dates):
    """Test retrieving active, non-expired promo codes."""
    valid_from, valid_until = valid_dates

    # Create active code
    active_code = unique_code("ACTIVE")
    promo_svc.create_promo_code(
        session,
        code=active_code,
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )

    # Create future code
    future_from = datetime.now() + timedelta(days=7)
    future_until = datetime.now() + timedelta(days=37)
    future_code = unique_code("FUTURE")
    promo_svc.create_promo_code(
        session,
        code=future_code,
        discount_type="percentage",
        discount_value=15.0,
        valid_from=future_from,
        valid_until=future_until,
    )

    # Create expired code
    past_from = datetime.now() - timedelta(days=37)
    past_until = datetime.now() - timedelta(days=7)
    expired_code = unique_code("EXPIRED")
    promo_svc.create_promo_code(
        session,
        code=expired_code,
        discount_type="percentage",
        discount_value=10.0,
        valid_from=past_from,
        valid_until=past_until,
    )

    session.commit()

    active = promo_svc.get_active_promo_codes(session)

    assert len(active) >= 1
    active_codes = [c.code for c in active]
    assert active_code in active_codes
    assert future_code not in active_codes
    assert expired_code not in active_codes


def test_get_promo_usage_report_single_code(session, valid_dates):
    """Test usage report for a single promo code."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="REPORT",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        max_uses=100,
    )
    session.commit()

    # Increment usage
    promo.current_uses = 25
    session.commit()

    report = promo_svc.get_promo_usage_report(session, "REPORT")

    assert len(report) == 1
    assert report[0]["code"] == "REPORT"
    assert report[0]["current_uses"] == 25
    assert report[0]["max_uses"] == 100
    assert report[0]["remaining_uses"] == "75"


def test_get_promo_usage_report_unlimited_uses(session, valid_dates):
    """Test usage report for code with unlimited uses."""
    valid_from, valid_until = valid_dates
    promo = promo_svc.create_promo_code(
        session,
        code="UNLIMITED",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        max_uses=None,
    )
    session.commit()

    promo.current_uses = 999
    session.commit()

    report = promo_svc.get_promo_usage_report(session, "UNLIMITED")

    assert len(report) == 1
    assert report[0]["remaining_uses"] == "unlimited"


def test_get_promo_usage_report_all_codes(session, valid_dates):
    """Test usage report for all codes."""
    valid_from, valid_until = valid_dates
    promo_svc.create_promo_code(
        session,
        code="CODE1",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    promo_svc.create_promo_code(
        session,
        code="CODE2",
        discount_type="fixed",
        discount_value=50.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    report = promo_svc.get_promo_usage_report(session)

    assert len(report) >= 2
    codes = [r["code"] for r in report]
    assert "CODE1" in codes
    assert "CODE2" in codes


def test_get_promo_usage_report_status(session):
    """Test that promo usage report includes status field."""
    now = datetime.now()
    valid_from = now - timedelta(days=1)
    valid_until = now + timedelta(days=30)

    active = promo_svc.create_promo_code(
        session,
        code="ACTIVE",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.commit()

    report = promo_svc.get_promo_usage_report(session, "ACTIVE")

    assert len(report) == 1
    assert report[0]["status"] == "active"
