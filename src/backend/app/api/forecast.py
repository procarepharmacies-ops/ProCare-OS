"""Forecast & decision briefing endpoints (Phase 5).

Endpoints for viewing demand forecasts, stockout risks, and daily decision cards.
All forecasts are pre-computed nightly by the scheduler and cached for <500ms queries.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import forecast as forecast_svc

router = APIRouter(prefix="/forecast", tags=["forecast"])


class ForecastOut(BaseModel):
    product_id: int
    branch_id: int | None
    forecast_date: str
    forecast_horizon: int
    daily_avg: float
    trend_per_day: float
    seasonality_factor: float
    projected_demand: float
    stockout_date: str | None
    days_of_cover: float
    method: str


class StockoutRiskOut(BaseModel):
    product_id: int
    name_ar: str
    name_en: str
    branch_id: int
    stockout_date: str
    days_until_stockout: int
    current_stock: float
    daily_avg: float


@router.get("/{product_id}", dependencies=[Depends(auth_guard())])
def get_forecast(
    product_id: int,
    branch_id: int | None = None,
    session: Session = Depends(get_session),
) -> ForecastOut:
    """Get cached forecast for a product (or all branches if unscoped).

    Forecasts are pre-computed nightly; this is a read-only cached query.
    Returns Holt-smoothed demand, stockout date, days of cover, etc.
    """
    from datetime import date
    from sqlalchemy import select
    from app.db import models as m

    result = session.execute(
        select(m.Forecast)
        .where(
            m.Forecast.product_id == product_id,
            m.Forecast.forecast_date == date.today(),
            *([] if branch_id is None else [m.Forecast.branch_id == branch_id]),
        )
    ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Forecast not found; forecasts computed nightly, check back after scheduler runs."
        )

    f = result[0]
    return ForecastOut(
        product_id=f.product_id,
        branch_id=f.branch_id,
        forecast_date=f.forecast_date.isoformat(),
        forecast_horizon=f.forecast_horizon,
        daily_avg=f.daily_avg,
        trend_per_day=f.trend_per_day,
        seasonality_factor=f.seasonality_factor,
        projected_demand=f.projected_demand,
        stockout_date=f.stockout_date.isoformat() if f.stockout_date else None,
        days_of_cover=f.days_of_cover,
        method=f.method,
    )


@router.get("/risks/stockout", dependencies=[Depends(auth_guard())])
def get_stockout_risks(
    branch_id: int | None = None,
    days_ahead: int = 7,
    session: Session = Depends(get_session),
) -> dict:
    """Get products forecasted to stockout within N days.

    Sorted by stockout_date (soonest first). Useful for
    auto-generating purchase/transfer decisions.
    """
    risks = forecast_svc.get_stockout_risks(session, branch_id, days_ahead)
    return {
        "horizon_days": days_ahead,
        "total_at_risk": len(risks),
        "risks": [StockoutRiskOut(**r) for r in risks],
    }
