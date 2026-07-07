"""Shared helpers for the service layer.

Data-quality rules from ``docs/05-data-quality-and-fixes.md`` are centralised
here so every query applies them consistently:
  * exclude returns from sales metrics (``is_return = 0``)
  * available stock = ``amount > 0`` AND not expired (or product has no expiry)
  * FEFO = order by ``exp_date`` ascending
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, and_, func, or_
from sqlalchemy.orm import Query

from app.db import models as m
from app.db.base import IS_SQLITE


def as_date(col):
    """Portable date-truncation of a datetime column.

    ``func.date()`` is a SQLite built-in; SQL Server has no ``date()`` function,
    so there we emit ``CAST(col AS DATE)`` — both truncate the time part. Every
    metric that compares against a calendar day must go through this so the same
    query runs on the dev SQLite DB and the production SQL Server unchanged.
    """
    return func.date(col) if IS_SQLITE else func.cast(col, Date)

# In production this is GETDATE(); the demo data is anchored to a fixed "today"
# so dashboards and tests are stable and reproducible.
TODAY = date(2026, 6, 26)


def available_stock_filter():
    """SQLAlchemy filter for sellable stock: positive and not expired."""
    return and_(
        m.StockBatch.amount > 0,
        or_(m.StockBatch.exp_date == None, m.StockBatch.exp_date > TODAY),  # noqa: E711
    )


def branch_filter(model, branch_id: int | None):
    """Optional branch scoping. ``None`` / 0 means consolidated (all branches)."""
    if branch_id:
        return model.branch_id == branch_id
    return True  # SQLAlchemy treats a bare True as "no constraint"


def money(value) -> float:
    """Coerce a Numeric/Decimal/None to a plain rounded float for JSON."""
    return round(float(value or 0), 2)
