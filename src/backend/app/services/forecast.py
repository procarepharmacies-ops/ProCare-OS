"""Demand forecasting engine (Phase 5): per-product, per-branch.

Uses Holt-style double exponential smoothing with day-of-week seasonality.
Nightly scheduler computes forecasts and caches in the forecasts table for
<500ms dashboard queries. Pure Python (no external libraries).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import available_stock_filter, money


def _avg_daily_consumption(
    session: Session, product_id: int, branch_id: int | None, window_days: int = 60
) -> float:
    """Average units sold per day for a product over a trailing window."""
    start = date.today() - timedelta(days=window_days)
    result = session.execute(
        select(func.sum(m.SaleLine.amount))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.SaleLine.product_id == product_id,
            m.Sale.is_return == False,  # noqa: E712
            m.Sale.sale_date >= start,
            *([] if branch_id is None else [m.Sale.branch_id == branch_id]),
        )
    ).scalar()
    total_sold = float(result or 0)
    return total_sold / window_days if window_days > 0 else 0.0


def _daily_consumption_series(
    session: Session, product_id: int, branch_id: int | None, window_days: int = 60
) -> dict[str, float]:
    """Per-day consumption for a product over a trailing window (keyed by date).
    Used for seasonality calculation (day-of-week patterns)."""
    start = date.today() - timedelta(days=window_days)
    rows = session.execute(
        select(
            func.date(m.Sale.sale_date).label("day"),
            func.sum(m.SaleLine.amount).label("qty"),
        )
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.SaleLine.product_id == product_id,
            m.Sale.is_return == False,  # noqa: E712
            func.date(m.Sale.sale_date) >= start,
            *([] if branch_id is None else [m.Sale.branch_id == branch_id]),
        )
        .group_by(func.date(m.Sale.sale_date))
    ).all()
    return {str(day): float(qty) for day, qty in rows}


def _seasonality_factor(series: dict[str, float], day_of_week: int) -> float:
    """Day-of-week seasonality: group by dow, compare avg to overall avg.
    day_of_week: 0=Monday, 6=Sunday."""
    if not series:
        return 1.0

    by_dow = {i: [] for i in range(7)}
    for date_str, qty in series.items():
        try:
            d = date.fromisoformat(date_str)
            by_dow[d.weekday()].append(qty)
        except (ValueError, AttributeError):
            pass

    overall_avg = mean(series.values()) if series else 1.0
    dow_avg = mean(by_dow[day_of_week]) if by_dow[day_of_week] else overall_avg

    return (dow_avg / overall_avg) if overall_avg > 0 else 1.0


def _holt_exponential_smoothing(
    series: list[float], alpha: float = 0.2, beta: float = 0.1, horizon: int = 30
) -> tuple[list[float], float, float]:
    """Holt's method: level + trend + forecast.

    Returns (forecast_values, level, trend) where:
    - forecast_values: horizon-day projection
    - level: smoothed level at end
    - trend: per-day slope at end
    """
    if not series or not any(series):
        return [0.0] * horizon, 0.0, 0.0

    level = series[0]
    trend = 0.0

    for i in range(1, len(series)):
        prev_level = level
        level = alpha * series[i] + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend

    forecast = [level + (i + 1) * trend for i in range(horizon)]
    forecast = [max(f, 0) for f in forecast]  # no negative demand
    return forecast, level, trend


def _current_stock(session: Session, product_id: int, branch_id: int | None) -> float:
    """Current on-hand stock for a product."""
    result = session.execute(
        select(func.sum(m.StockBatch.amount))
        .where(
            m.StockBatch.product_id == product_id,
            available_stock_filter(),
            *([] if branch_id is None else [m.StockBatch.branch_id == branch_id]),
        )
    ).scalar()
    return float(result or 0)


def forecast_demand(
    session: Session,
    product_id: int,
    branch_id: int | None = None,
    horizon_days: int = 30,
    window_days: int = 60,
) -> dict:
    """Compute demand forecast for a product×branch using Holt exponential smoothing.

    Args:
        product_id: Product to forecast
        branch_id: Branch scope (None = all branches)
        horizon_days: Number of days to forecast ahead
        window_days: Historical window for pattern extraction

    Returns:
        dict with daily_avg, trend, projected_demand, stockout_date, days_of_cover, etc.
    """
    # Get historical daily series
    series_dict = _daily_consumption_series(session, product_id, branch_id, window_days)
    series = [series_dict.get((date.today() - timedelta(days=i)).isoformat(), 0.0) for i in range(window_days, 0, -1)]

    # Holt smoothing
    forecast_values, level, trend = _holt_exponential_smoothing(series, alpha=0.2, beta=0.1, horizon=horizon_days)

    # Day-of-week seasonality
    today_dow = date.today().weekday()
    seasonality_factors = [
        _seasonality_factor(series_dict, (today_dow + i) % 7) for i in range(horizon_days)
    ]

    # Apply seasonality to forecast
    adjusted_forecast = [
        forecast_values[i] * seasonality_factors[i] for i in range(horizon_days)
    ]

    projected_demand = sum(adjusted_forecast)
    daily_avg = float(mean(series)) if any(series) else 0.0

    # Stockout date: when cumulative demand exceeds on-hand stock
    current_stock = _current_stock(session, product_id, branch_id)
    cumulative = 0.0
    stockout_date = None
    if current_stock > 0:
        for i, daily_demand in enumerate(adjusted_forecast):
            cumulative += daily_demand
            if cumulative >= current_stock:
                stockout_date = date.today() + timedelta(days=i + 1)
                break

    days_of_cover = (current_stock / daily_avg) if daily_avg > 0 else 999.9

    avg_seasonality = mean(seasonality_factors) if seasonality_factors else 1.0

    return {
        "product_id": product_id,
        "branch_id": branch_id,
        "forecast_date": date.today(),
        "forecast_horizon": horizon_days,
        "daily_avg": round(daily_avg, 2),
        "trend_per_day": round(trend, 4),
        "seasonality_factor": round(avg_seasonality, 2),
        "projected_demand": round(projected_demand, 1),
        "stockout_date": stockout_date,
        "days_of_cover": round(days_of_cover, 1),
        "method": "exp_smoothing",
        "current_stock": round(current_stock, 1),
    }


def compute_nightly_forecasts(session: Session, branch_id: int | None = None) -> int:
    """Compute and cache forecasts for all active products (nightly job).

    Idempotent: truncates today's forecasts and re-populates.
    Returns count of forecasts computed.
    """
    from app.services.common import today

    # Clear today's forecasts (for re-run safety)
    session.execute(
        delete(m.Forecast).where(m.Forecast.forecast_date == today())
    )
    session.flush()  # Ensure deletes are processed before inserts

    # Get all active products
    products = session.execute(
        select(m.Product.product_id)
        .where(m.Product.is_active == True, m.Product.is_deleted == False)  # noqa: E712
    ).all()

    count = 0
    for (product_id,) in products:
        # If branch-scoped, forecast only that branch; else forecast all branches
        if branch_id:
            forecast = forecast_demand(session, product_id, branch_id=branch_id)
            session.add(
                m.Forecast(
                    product_id=forecast["product_id"],
                    branch_id=forecast["branch_id"],
                    forecast_date=forecast["forecast_date"],
                    forecast_horizon=forecast["forecast_horizon"],
                    daily_avg=forecast["daily_avg"],
                    trend_per_day=forecast["trend_per_day"],
                    seasonality_factor=forecast["seasonality_factor"],
                    projected_demand=forecast["projected_demand"],
                    stockout_date=forecast["stockout_date"],
                    days_of_cover=forecast["days_of_cover"],
                    method=forecast["method"],
                )
            )
            count += 1
        else:
            # All branches
            branches = session.execute(
                select(m.Branch.branch_id).where(m.Branch.is_active == True)  # noqa: E712
            ).all()
            for (bid,) in branches:
                forecast = forecast_demand(session, product_id, branch_id=bid)
                session.add(
                    m.Forecast(
                        product_id=forecast["product_id"],
                        branch_id=forecast["branch_id"],
                        forecast_date=forecast["forecast_date"],
                        forecast_horizon=forecast["forecast_horizon"],
                        daily_avg=forecast["daily_avg"],
                        trend_per_day=forecast["trend_per_day"],
                        seasonality_factor=forecast["seasonality_factor"],
                        projected_demand=forecast["projected_demand"],
                        stockout_date=forecast["stockout_date"],
                        days_of_cover=forecast["days_of_cover"],
                        method=forecast["method"],
                    )
                )
                count += 1

    session.commit()
    return count


def get_stockout_risks(
    session: Session, branch_id: int | None = None, days_ahead: int = 7
) -> list[dict]:
    """Get products forecasted to stockout within N days."""
    cutoff = date.today() + timedelta(days=days_ahead)
    rows = session.execute(
        select(m.Forecast, m.Product)
        .join(m.Product, m.Product.product_id == m.Forecast.product_id)
        .where(
            m.Forecast.forecast_date == date.today(),
            m.Forecast.stockout_date != None,  # noqa: E711
            m.Forecast.stockout_date <= cutoff,
            *([] if branch_id is None else [m.Forecast.branch_id == branch_id]),
        )
        .order_by(m.Forecast.stockout_date.asc())
    ).all()

    return [
        {
            "product_id": p.product_id,
            "name_ar": p.name_ar,
            "name_en": p.name_en,
            "branch_id": f.branch_id,
            "stockout_date": f.stockout_date.isoformat(),
            "days_until_stockout": (f.stockout_date - date.today()).days,
            "current_stock": f.days_of_cover * f.daily_avg,
            "daily_avg": f.daily_avg,
        }
        for f, p in rows
    ]
