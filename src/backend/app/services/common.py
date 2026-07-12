"""Shared helpers for the service layer.

Data-quality rules from ``docs/05-data-quality-and-fixes.md`` are centralised
here so every query applies them consistently:
  * exclude returns from sales metrics (``is_return = 0``)
  * available stock = ``amount > 0`` AND not expired (or product has no expiry)
  * FEFO = order by ``exp_date`` ascending
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, and_, cast, func, or_
from sqlalchemy.orm import Query

from app.config import settings
from app.db import models as m
from app.db.base import IS_SQLITE

# The demo/seed dataset is anchored to a fixed "today" so offline dashboards
# and the test suite are stable and reproducible.
DEMO_TODAY = date(2026, 6, 26)


def today() -> date:
    """The business 'today'. Real clock when a live eStock mirror is
    configured; the demo anchor otherwise (offline demo + test suite —
    conftest pins the example config, so tests always get the anchor)."""
    if settings.estock_configured:
        return date.today()
    return DEMO_TODAY


def sql_day(col):
    """Dialect-portable "date part of a datetime column" for filters and
    GROUP BY. SQLite's ``date()`` is not a SQL Server function, and SQL
    Server's ``CAST(x AS DATE)`` degrades to a numeric cast on SQLite —
    so pick per dialect."""
    return func.date(col) if IS_SQLITE else cast(col, Date)


def available_stock_filter():
    """SQLAlchemy filter for sellable stock: positive and not expired."""
    return and_(
        m.StockBatch.amount > 0,
        or_(m.StockBatch.exp_date == None, m.StockBatch.exp_date > today()),  # noqa: E711
    )


def branch_filter(model, branch_id: int | None):
    """Optional branch scoping. ``None`` / 0 means consolidated (all branches)."""
    if branch_id:
        return model.branch_id == branch_id
    return True  # SQLAlchemy treats a bare True as "no constraint"


def money(value) -> float:
    """Coerce a Numeric/Decimal/None to a plain rounded float for JSON."""
    return round(float(value or 0), 2)
