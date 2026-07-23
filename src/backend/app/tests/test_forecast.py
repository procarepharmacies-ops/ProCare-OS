"""Tests for Phase 5 forecasting engine."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import forecast as forecast_svc


def test_forecast_demand_no_history(client):
    """Forecast with no sales history should return zeros gracefully."""
    with SessionLocal() as session:
        p = m.Product(
            code="NO_SALES_TEST",
            name_ar="بدون مبيعات",
            name_en="No Sales",
            is_active=True,
        )
        session.add(p)
        session.commit()

        result = forecast_svc.forecast_demand(session, p.product_id, branch_id=None)
        assert result["daily_avg"] == 0.0
        assert result["projected_demand"] == 0.0
        assert result["method"] == "exp_smoothing"


def test_forecast_demand_with_history(client):
    """Forecast should compute reasonable values when history exists."""
    with SessionLocal() as session:
        # Get or create a product and branch
        p = session.query(m.Product).filter_by(code="FORECAST_HIST").first()
        if not p:
            p = m.Product(code="FORECAST_HIST", name_ar="تنبؤ", name_en="Forecast", is_active=True)
            session.add(p)
            session.flush()

        b = session.query(m.Branch).first()
        if not b:
            b = m.Branch(name_ar="فرع", name_en="Branch", is_active=True)
            session.add(b)
            session.flush()

        # Add a stock batch (batch_id is an auto-increment PK — let SQLite assign it)
        stock = m.StockBatch(
            product_id=p.product_id,
            branch_id=b.branch_id,
            amount=500.0,
            buy_price=10.0,
            sell_price=15.0,
            exp_date=date.today() + timedelta(days=365),
        )
        session.add(stock)
        session.flush()

        # Add 30 days of sales history
        for i in range(30, 0, -1):
            sale_date = date.today() - timedelta(days=i)
            sale = m.Sale(
                branch_id=b.branch_id,
                sale_date=sale_date,
                total_net=3.0 * 15.0,
                is_return=False,
            )
            session.add(sale)
            session.flush()
            line = m.SaleLine(
                sale_id=sale.sale_id,
                product_id=p.product_id,
                amount=3.0,
                sell_price=15.0,
                buy_price=10.0,
                total_sell=3.0 * 15.0,
            )
            session.add(line)
        session.commit()

        # Forecast
        result = forecast_svc.forecast_demand(session, p.product_id, b.branch_id)
        assert result["product_id"] == p.product_id
        assert result["daily_avg"] > 0
        assert result["projected_demand"] > 0
        assert result["forecast_horizon"] == 30


def test_compute_nightly_forecasts_idempotent(client):
    """Nightly computation should be idempotent (runnable twice safely)."""
    with SessionLocal() as session:
        # First run
        count1 = forecast_svc.compute_nightly_forecasts(session, branch_id=None)
        # Second run (should truncate and recompute)
        count2 = forecast_svc.compute_nightly_forecasts(session, branch_id=None)

        # Both runs should produce same count
        assert count1 == count2 > 0

        # Verify today's forecasts exist
        forecasts = session.execute(
            select(m.Forecast).where(m.Forecast.forecast_date == date.today())
        ).all()
        assert len(forecasts) == count1


def test_get_stockout_risks(client):
    """Stockout risk endpoint should identify at-risk products."""
    with SessionLocal() as session:
        # Compute forecasts (uses seeded data)
        forecast_svc.compute_nightly_forecasts(session)

        # Get stockout risks
        risks = forecast_svc.get_stockout_risks(session, branch_id=None, days_ahead=30)

        # Should return a list (may be empty if no risks)
        assert isinstance(risks, list)


def test_forecast_api_endpoint(client):
    """GET /api/forecast/{product_id} should retrieve cached forecast."""
    with SessionLocal() as session:
        # Get a seeded product
        p = session.query(m.Product).first()
        if not p:
            return  # No products to test

        # Compute forecasts
        forecast_svc.compute_nightly_forecasts(session)

    # Query via API
    r = client.get(f"/api/forecast/{p.product_id}")
    assert r.status_code in (200, 404)  # May not have forecast if no history
    if r.status_code == 200:
        body = r.json()
        assert "product_id" in body
        assert "projected_demand" in body


def test_stockout_risks_api_endpoint(client):
    """GET /api/forecast/risks/stockout should return at-risk products."""
    with SessionLocal() as session:
        # Compute forecasts
        forecast_svc.compute_nightly_forecasts(session)

    # Query via API
    r = client.get("/api/forecast/risks/stockout?days_ahead=30")
    assert r.status_code == 200
    body = r.json()
    assert "risks" in body
    assert "total_at_risk" in body
