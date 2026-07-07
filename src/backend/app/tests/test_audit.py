"""Tests for the in-system cash-flow & inventory audit report."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m


def test_cash_report_shape_and_branches(client):
    r = client.get("/api/audit/cash-report")
    assert r.status_code == 200
    body = r.json()
    assert body["window_months"] == 3
    assert body["data_source"]["mode"] in ("live", "demo")
    # Dev environment: honest about running on demo data with a connect hint.
    assert body["data_source"]["mode"] == "demo"
    assert "connections.json" in (body["data_source"]["hint"] or "")
    assert len(body["branches"]) >= 2
    required = {
        "revenue", "gross_profit", "purchases_all_vendors", "purchases_to_sales_pct",
        "vendor_invoiced", "vendor_paid", "vendor_gap", "expenses_window",
        "treasury_balance", "cash_desk", "stock_cost", "stock_retail",
        "expired", "expiring_90d_cost", "dead_stock",
    }
    for b in body["branches"]:
        assert required <= set(b), b["code"]
    assert {"total", "over_limit", "debtors_over_limit"} <= set(body["receivables"])


def test_cash_report_vendor_focus_search(client, session):
    vendor = session.scalars(select(m.Vendor)).first()
    r = client.get("/api/audit/cash-report", params={"vendor": vendor.name_ar[:6]})
    assert r.status_code == 200
    assert r.json()["vendor_focus"]["vendor_id"] == vendor.vendor_id
    # Unknown query falls back to the biggest payable, never errors.
    r2 = client.get("/api/audit/cash-report", params={"vendor": "no-such-vendor-xyz"})
    assert r2.status_code == 200
    assert r2.json()["vendor_focus"] is not None


def test_cash_report_stock_and_ratio_consistency(client):
    body = client.get("/api/audit/cash-report").json()
    for b in body["branches"]:
        # Retail value should not be below cost value in the seeded catalogue.
        assert b["stock_retail"] >= b["stock_cost"] - 0.01
        # Ratio matches its inputs when sales exist.
        if b["revenue"] > 0 and b["purchases_to_sales_pct"] is not None:
            expected = round(b["purchases_all_vendors"] / b["revenue"] * 100, 1)
            assert abs(b["purchases_to_sales_pct"] - expected) < 0.2
