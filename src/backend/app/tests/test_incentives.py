"""Phase 2 tests: POS revenue engine — upsell/cross-sell, OTC incentives."""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db import models as m
from app.db.base import SessionLocal


@pytest.fixture(autouse=True)
def clear_incentive_ledger():
    """Clear the incentive ledger before each test to ensure isolation."""
    session = SessionLocal()
    try:
        session.execute(delete(m.IncentiveLedger))
        session.commit()
    finally:
        session.close()
    yield


def test_incentive_points_tracking(client):
    """Selling an incentivized product credits the cashier's points."""
    # Set up: find a product with stock, configure incentive points.
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 2)
    product_id = target["product_id"]

    # Manager sets incentive points on the product (5 points per unit).
    r = client.post(
        f"/api/incentives/products/{product_id}/incentive-points",
        json={"incentive_points": 5.0},
    )
    assert r.status_code == 200
    assert float(r.json()["incentive_points"]) == 5.0

    # Create a sale of this product (2 units).
    sale_r = client.post(
        "/api/sales",
        json={
            "branch_id": 1,
            "cashier_id": 1,
            "lines": [{"product_id": product_id, "amount": 2}],
        },
    )
    assert sale_r.status_code == 200

    # Check the leaderboard: cashier should have 10 points (5 * 2 units).
    leaderboard_r = client.get("/api/incentives/leaderboard")
    assert leaderboard_r.status_code == 200
    body = leaderboard_r.json()
    entries = body["entries"]
    cashier_entry = next((e for e in entries if e["employee_id"] == 1), None)
    assert cashier_entry is not None
    assert float(cashier_entry["points"]) == 10.0


def test_incentive_points_clawback_on_return(client):
    """Returning an incentivized item claws back the cashier's points."""
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 2)
    product_id = target["product_id"]

    # Set up incentive: 3 points per unit.
    client.post(
        f"/api/incentives/products/{product_id}/incentive-points",
        json={"incentive_points": 3.0},
    )

    # Sale: 2 units = 6 points credited.
    sale_r = client.post(
        "/api/sales",
        json={
            "branch_id": 1,
            "cashier_id": 1,
            "lines": [{"product_id": product_id, "amount": 2}],
        },
    )
    sale_id = sale_r.json()["sale_id"]

    # Check points before return.
    leaderboard_before = client.get("/api/incentives/leaderboard").json()
    points_before = next(
        (e["points"] for e in leaderboard_before["entries"] if e["employee_id"] == 1),
        0,
    )

    # Return 1 unit (3 points clawed back).
    return_r = client.post(
        f"/api/sales/{sale_id}/return",
        json={"lines": [{"product_id": product_id, "amount": 1}], "cashier_id": 1},
    )
    assert return_r.status_code == 200

    # Check points after return: should be 3 (6 - 3).
    leaderboard_after = client.get("/api/incentives/leaderboard").json()
    points_after = next(
        (e["points"] for e in leaderboard_after["entries"] if e["employee_id"] == 1),
        0,
    )
    assert float(points_after) == 3.0


def test_incentive_products_list(client):
    """Listing incentivized products shows all products with points > 0."""
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target_ids = [products[0]["product_id"], products[1]["product_id"]]

    # Set incentive points on two products.
    for pid in target_ids:
        client.post(
            f"/api/incentives/products/{pid}/incentive-points",
            json={"incentive_points": float(pid % 5 + 1)},
        )

    # List incentivized products.
    r = client.get("/api/incentives/products")
    assert r.status_code == 200
    body = r.json()
    incentive_pids = {p["product_id"] for p in body["products"]}
    for pid in target_ids:
        assert pid in incentive_pids


def test_pos_suggestions_endpoint(client):
    """POS suggestions endpoint returns upsell recommendations."""
    # For now, affinity matrix is empty (Phase 2 pilot), so suggestions = [].
    # Later, nightly scheduler fills product_affinity from sales history.
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    cart_ids = ",".join(str(p["product_id"]) for p in products[:2])
    r = client.get(f"/api/sales/suggestions?branch_id=1&cart={cart_ids}")
    assert r.status_code == 200
    body = r.json()
    assert "suggestions" in body
    assert isinstance(body["suggestions"], list)
    # Empty for now; will populate once affinity job runs.


def test_employee_incentive_history(client):
    """Employee incentive history shows monthly totals + per-sale breakdown."""
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 1)

    # Configure incentive.
    client.post(
        f"/api/incentives/products/{target['product_id']}/incentive-points",
        json={"incentive_points": 7.0},
    )

    # Make a sale.
    sale_r = client.post(
        "/api/sales",
        json={
            "branch_id": 1,
            "cashier_id": 1,
            "lines": [{"product_id": target["product_id"], "amount": 1}],
        },
    )
    assert sale_r.status_code == 200

    # Fetch history for the cashier (employee 1).
    r = client.get("/api/incentives/employee/1")
    assert r.status_code == 200
    body = r.json()
    assert body["employee_id"] == 1
    assert float(body["total_points"]) == 7.0
    assert len(body["entries"]) >= 1


@pytest.fixture
def molecule():
    """Three brands of one active ingredient with distinct margins:
      A sell100/buy40 -> margin 60, 60.0%
      B sell200/buy130-> margin 70, 35.0%   (top by EGP margin)
      C sell80/buy24  -> margin 56, 70.0%   (top by margin %)
    """
    s = SessionLocal()
    ids = {}
    try:
        specs = {"A": (100, 40), "B": (200, 130), "C": (80, 24)}
        for tag, (sell, buy) in specs.items():
            p = m.Product(code=f"ZZMOL-{tag}", name_ar=f"صنف {tag}", name_en=f"Brand {tag}",
                          scientific_name="ZZTESTMOLECULE", sell_price=sell, buy_price=buy)
            s.add(p)
            s.flush()
            ids[tag] = p.product_id
        s.commit()
    finally:
        s.close()
    try:
        yield ids
    finally:
        s2 = SessionLocal()
        try:
            s2.execute(delete(m.Product).where(m.Product.code.like("ZZMOL-%")))
            s2.commit()
        finally:
            s2.close()


def test_incentive_candidates_ranks_and_toggles(client, molecule):
    # Default metric = egp_margin: B(70) > A(60) > C(56)
    r = client.get("/api/incentives/candidates?metric=egp_margin&top_n=3&branch_id=1")
    assert r.status_code == 200
    grp = next(g for g in r.json()["groups"] if g["ingredient"] == "ZZTESTMOLECULE")
    assert grp["brand_count"] == 3
    assert [b["code"] for b in grp["top"]] == ["ZZMOL-B", "ZZMOL-A", "ZZMOL-C"]
    # every brand carries all three metric values for live re-ranking
    assert set(("egp_margin", "margin_pct", "profit_volume")).issubset(grp["top"][0].keys())

    # Toggle to margin_pct: C(70%) > A(60%) > B(35%)
    r2 = client.get("/api/incentives/candidates?metric=margin_pct&top_n=3&branch_id=1")
    grp2 = next(g for g in r2.json()["groups"] if g["ingredient"] == "ZZTESTMOLECULE")
    assert [b["code"] for b in grp2["top"]] == ["ZZMOL-C", "ZZMOL-A", "ZZMOL-B"]


def test_incentive_apply_bulk(client, molecule):
    a, b = molecule["A"], molecule["B"]
    r = client.post("/api/incentives/apply", json={"items": [
        {"product_id": a, "points": 5}, {"product_id": b, "points": 3},
    ]})
    assert r.status_code == 200
    assert r.json()["set"] == 2
    listed = {p["product_id"]: p["incentive_points"] for p in client.get("/api/incentives/products").json()["products"]}
    assert listed.get(a) == 5 and listed.get(b) == 3
    # points 0 clears it
    client.post("/api/incentives/apply", json={"items": [{"product_id": a, "points": 0}]})
    listed2 = {p["product_id"] for p in client.get("/api/incentives/products").json()["products"]}
    assert a not in listed2 and b in listed2


def test_zero_incentive_removes_points(client):
    """Setting incentive_points to 0 removes the OTC incentive."""
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = products[0]

    # Set incentive.
    client.post(
        f"/api/incentives/products/{target['product_id']}/incentive-points",
        json={"incentive_points": 5.0},
    )

    # Verify it's listed.
    r1 = client.get("/api/incentives/products").json()
    assert any(p["product_id"] == target["product_id"] for p in r1["products"])

    # Clear incentive.
    client.post(
        f"/api/incentives/products/{target['product_id']}/incentive-points",
        json={"incentive_points": 0.0},
    )

    # Verify it's no longer listed.
    r2 = client.get("/api/incentives/products").json()
    assert not any(p["product_id"] == target["product_id"] for p in r2["products"])
