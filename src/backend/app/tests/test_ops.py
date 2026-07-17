"""Tests for the operations batch: treasury, purchase returns, shortage sheet,
prescription records + doctor habits, predictive auto-purchasing budget,
dashboard month/branch/range views, invoice profit, and stock-report exports."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as m
from app.services import autopurchase, prescriptions as rx_svc, treasury
from app.services.pos import POSError


# --- treasury ----------------------------------------------------------------
def test_treasury_vouchers_and_balance(session):
    start = treasury.branch_balance(session, 1)
    treasury.receive_voucher(session, 1, 500.0, note="رأس مال", party="Owner")
    assert treasury.branch_balance(session, 1) == pytest.approx(start + 500.0)
    treasury.pay_voucher(session, 1, 120.0, note="كهرباء")
    assert treasury.branch_balance(session, 1) == pytest.approx(start + 380.0)


def test_treasury_pay_cannot_overdraw(session):
    bal = treasury.branch_balance(session, 2)
    with pytest.raises(POSError) as e:
        treasury.pay_voucher(session, 2, bal + 1_000_000)
    assert e.value.code == "insufficient_treasury"


def test_treasury_transfer_moves_between_branches(session):
    treasury.receive_voucher(session, 1, 300.0, note="seed for transfer")
    b1, b2 = treasury.branch_balance(session, 1), treasury.branch_balance(session, 2)
    out = treasury.transfer_money(session, 1, 2, 250.0, note="تغذية خزينة السنطه")
    assert out["amount"] == 250.0
    assert treasury.branch_balance(session, 1) == pytest.approx(b1 - 250.0)
    assert treasury.branch_balance(session, 2) == pytest.approx(b2 + 250.0)
    transfers = treasury.list_transfers(session, 2)
    assert any(t["transfer_id"] == out["transfer_id"] for t in transfers)


def test_treasury_adjust_requires_note(session):
    with pytest.raises(POSError):
        treasury.adjust_balance(session, 1, 10.0, note="  ")


def test_treasury_api_endpoints(client):
    r = client.get("/api/treasury/balances")
    assert r.status_code == 200
    assert {b["branch_id"] for b in r.json()["branches"]} >= {1, 2}
    r = client.post("/api/treasury/receive", json={"branch_id": 1, "amount": 75, "note": "test"})
    assert r.status_code == 200 and r.json()["kind"] == "receive"


# --- purchase returns ----------------------------------------------------------
def test_purchase_return_restores_vendor_balance_and_stock(client, session):
    vendor = session.scalars(select(m.Vendor)).first()
    product = session.scalars(select(m.Product)).first()
    create = client.post(
        "/api/purchasing/purchases",
        json={
            "branch_id": 1,
            "vendor_id": vendor.vendor_id,
            "lines": [{"product_id": product.product_id, "amount": 10, "buy_price": 5.0}],
        },
    )
    assert create.status_code == 200
    pid = create.json()["purchase_id"]
    session.expire_all()
    bal_after_buy = float(session.get(m.Vendor, vendor.vendor_id).current_balance)

    ret = client.post(
        f"/api/purchasing/purchases/{pid}/return",
        json={"lines": [{"product_id": product.product_id, "amount": 4}]},
    )
    assert ret.status_code == 200
    assert ret.json()["total_returned"] == pytest.approx(20.0)
    session.expire_all()
    assert float(session.get(m.Vendor, vendor.vendor_id).current_balance) == pytest.approx(bal_after_buy - 20.0)

    # Over-return is refused.
    too_much = client.post(
        f"/api/purchasing/purchases/{pid}/return",
        json={"lines": [{"product_id": product.product_id, "amount": 7}]},
    )
    assert too_much.status_code == 422


# --- shortage sheet -------------------------------------------------------------
def test_shortage_sheet_flow(client):
    created = client.post(
        "/api/shortages",
        json={"branch_id": 1, "product_name": "دواء مطلوب غير متوفر", "qty_requested": 3, "note": "عميل سأل عنه"},
    )
    assert created.status_code == 200
    sid = created.json()["shortage_id"]

    rows = client.get("/api/shortages", params={"branch_id": 1, "status": "open"}).json()["shortages"]
    assert any(s["shortage_id"] == sid for s in rows)

    updated = client.post(f"/api/shortages/{sid}/status", json={"status": "ordered"})
    assert updated.json()["status"] == "ordered"
    assert client.post(f"/api/shortages/{sid}/status", json={"status": "bogus"}).status_code == 422


def test_shortage_requires_product_or_name(client):
    assert client.post("/api/shortages", json={"branch_id": 1, "qty_requested": 1}).status_code == 422


# --- prescriptions ---------------------------------------------------------------
def test_prescription_manual_and_doctor_habits(client):
    for _ in range(2):
        r = client.post(
            "/api/prescriptions",
            json={
                "branch_id": 1,
                "doctor_name": "د. أحمد فؤاد",
                "doctor_specialty": "باطنة",
                "drugs": [{"name": "Augmentin 1g", "frequency": "كل 12 ساعة"}, {"name": "Panadol Extra"}],
            },
        )
        assert r.status_code == 200
    habits = client.get("/api/prescriptions/doctor-habits").json()["doctors"]
    doc = next(d for d in habits if d["doctor_name"] == "د. أحمد فؤاد")
    assert doc["prescriptions"] >= 2
    assert any(t["name"] == "Augmentin 1g" and t["count"] >= 2 for t in doc["top_drugs"])


def test_prescription_analyze_without_key_falls_back(client):
    r = client.post("/api/prescriptions/analyze", json={"image_b64": "aGVsbG8=", "branch_id": 1})
    body = r.json()
    # No Gemini key in CI — the reader reports manual fallback, never an error.
    assert r.status_code == 200
    assert body.get("ok") is False and body.get("needs_manual") is True


def test_prescription_demand_signal(session):
    counts = rx_svc.demand_signal(session)
    assert isinstance(counts, dict)


# --- predictive auto-purchasing ---------------------------------------------------
def test_purchasing_budget_is_pct_of_daily_sales(client):
    r = client.get("/api/purchasing/budget")
    assert r.status_code == 200
    body = r.json()
    assert body["budget_pct"] == pytest.approx(0.8)
    assert body["daily_budget"] == pytest.approx(body["avg_daily_sales"] * 0.8, abs=0.02)


def test_auto_proposal_respects_budget(client, session):
    plan = autopurchase.propose(session, 1)
    assert plan["proposed_cost"] <= plan["budget"]["remaining_today"] + 0.01


def test_auto_generate_writes_predictive_drafts(client, session):
    r = client.post("/api/purchasing/auto-generate", params={"branch_id": 1})
    assert r.status_code == 200
    body = r.json()
    drafts = session.scalars(
        select(m.PurchaseOrderDraft).where(
            m.PurchaseOrderDraft.reason == "predictive", m.PurchaseOrderDraft.branch_id == 1
        )
    ).all()
    assert len(drafts) == body["drafts_created"]


# --- dashboard month / branch / range views ------------------------------------
def test_dashboard_monthly_series(client):
    r = client.get("/api/dashboard/monthly", params={"months": 6})
    assert r.status_code == 200
    months = r.json()["months"]
    assert all({"month", "revenue", "bills", "profit", "discount"} <= set(mo) for mo in months)


def test_dashboard_by_branch_comparison(client):
    r = client.get("/api/dashboard/by-branch")
    assert r.status_code == 200
    rows = r.json()["branches"]
    assert {b["branch_id"] for b in rows} >= {1, 2}


def test_dashboard_range_summary(client):
    r = client.get(
        "/api/dashboard/range", params={"date_from": "2020-01-01", "date_to": "2030-01-01", "branch_id": 1}
    )
    assert r.status_code == 200
    assert r.json()["bills"] >= 0


# --- invoice discount + profit ---------------------------------------------------
def test_sale_detail_carries_discount_and_profit(client, session):
    product = session.scalars(select(m.Product).where(m.Product.sell_price > 0)).first()
    sale = client.post(
        "/api/sales",
        json={
            "branch_id": 1,
            "lines": [{"product_id": product.product_id, "amount": 1, "disc_money": 1.0}],
        },
    )
    assert sale.status_code == 200
    sale_id = sale.json()["sale_id"]
    detail = client.get(f"/api/sales/{sale_id}").json()
    assert detail["total_discount"] == pytest.approx(1.0)
    expected_profit = float(product.sell_price) - 1.0 - float(product.buy_price)
    assert detail["profit"] == pytest.approx(expected_profit, abs=0.02)
    assert all("profit" in ln and "disc_money" in ln for ln in detail["lines"])

    recent = client.get("/api/sales/recent", params={"branch_id": 1}).json()["sales"]
    assert all("profit" in s and "total_discount" in s for s in recent)


# --- substitutions with branch/expiry detail --------------------------------------
def test_substitutions_include_branch_and_expiry(client, session):
    # Find a product that has an in-stock alternative sharing an ingredient.
    from app.services import clinical

    products = session.scalars(select(m.Product)).all()
    hit = None
    for p in products:
        subs = clinical.substitutions(session, p.product_id, None)
        if subs:
            hit = subs
            break
    if hit is None:
        pytest.skip("seed catalogue has no in-stock substitution pair")
    alt = hit[0]
    assert "branches" in alt
    assert all({"branch_id", "branch_name", "qty", "nearest_expiry"} <= set(b) for b in alt["branches"])


# --- stock reports + CSV export ----------------------------------------------------
def test_stock_reports_json(client):
    for path, key in (
        ("/api/reports/stock", "products"),
        ("/api/reports/stock/batches", "batches"),
        ("/api/reports/stock/movements", "movements"),
        ("/api/reports/stock/valuation", "branches"),
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert key in r.json(), path


def test_stock_report_csv_export(client):
    r = client.get("/api/reports/stock", params={"format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.text.startswith("﻿")  # Excel-friendly BOM
    assert "name_ar" in r.text.splitlines()[0]
