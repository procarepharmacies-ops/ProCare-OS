"""Round-3 parity: backups, product add/classify/filters, purchase plan, vendor account."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import backup


def test_backup_and_throttle(tmp_path):
    r = backup.backup_now("test")
    assert r["ok"] is True, r
    assert backup.last_backup_at() is not None
    # Fresh backup exists -> the throttled call skips (returns None).
    assert backup.backup_if_stale(6, "test-throttle") is None
    assert any(b["file"].startswith("procare-") for b in backup.list_backups())


def test_create_product_and_filters(client):
    r = client.post(
        "/api/inventory/products",
        json={
            "name_ar": "صنف جديد للاختبار",
            "scientific_name": "Testium",
            "sell_price": 50,
            "buy_price": 30,
            "unit_big": "علبة",
            "unit_small": "شريط",
            "unit_factor": 3,
            "dosage_form": "أقراص",
            "is_otc": True,
            "uses": "اختبار",
            "shelf_location": "T1",
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["product_id"]
    # Duplicate name refused.
    assert client.post("/api/inventory/products", json={"name_ar": "صنف جديد للاختبار"}).status_code == 422

    # Filters: only OTC أقراص in shelf T1 must include it.
    got = client.get("/api/inventory/products?dosage_form=أقراص&otc=true&location=T1").json()["products"]
    assert any(p["product_id"] == pid for p in got)
    # And a non-matching form excludes it.
    got = client.get("/api/inventory/products?dosage_form=شراب&location=T1").json()["products"]
    assert all(p["product_id"] != pid for p in got)

    # Filter values include the new form/location.
    fv = client.get("/api/inventory/filters").json()
    assert "أقراص" in fv["dosage_forms"] and "T1" in fv["locations"]

    # Price sorting is honored.
    prices = [p["sell_price"] for p in client.get("/api/inventory/products?sort=price_desc").json()["products"]]
    assert prices == sorted(prices, reverse=True)


def test_purchase_plan_priorities(client, session):
    plan = client.get("/api/purchasing/plan?branch_id=1").json()
    assert "rows" in plan and "budget" in plan
    priorities = [r["priority"] for r in plan["rows"]]
    assert priorities == sorted(priorities), "plan must be ordered by priority"
    for r in plan["rows"]:
        assert r["action"] in ("transfer", "buy")
        if r["action"] == "transfer":
            assert r["other_branches"], "transfer rows must say WHERE the stock is"

    cons = client.get("/api/purchasing/plan/consolidated").json()
    assert "rows" in cons and "total_cost" in cons
    for r in cons["rows"]:
        assert r["per_branch"], "consolidated rows carry per-branch needs"


def test_vendor_statement_and_payment(client, session):
    vendor = session.scalars(select(m.Vendor)).first()
    st = client.get(f"/api/vendors/{vendor.vendor_id}/statement").json()
    assert st["vendor_id"] == vendor.vendor_id and "rows" in st

    detail = client.get(f"/api/vendors/{vendor.vendor_id}").json()
    assert "avg_discount_pct" in detail

    # Vendor payment needs treasury cash — put some in first.
    client.post("/api/treasury/receive", json={"branch_id": 1, "amount": 500, "note": "test float"})
    before = float(session.get(m.Vendor, vendor.vendor_id).current_balance or 0)
    r = client.post(
        f"/api/vendors/{vendor.vendor_id}/pay",
        json={"branch_id": 1, "amount": 100, "note": "سداد اختبار"},
    )
    assert r.status_code == 200, r.text
    session.expire_all()
    after = float(session.get(m.Vendor, vendor.vendor_id).current_balance or 0)
    assert round(before - after, 2) == 100.0
    # The payment shows on the statement.
    st = client.get(f"/api/vendors/{vendor.vendor_id}/statement").json()
    assert any(row["kind"] == "سداد" and row["debit"] == 100 for row in st["rows"])
