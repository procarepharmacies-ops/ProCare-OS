"""Phase 2 tests: POS revenue engine — upsell/cross-sell, OTC incentives."""
from __future__ import annotations


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
    target = products[0]

    # Configure incentive.
    client.post(
        f"/api/incentives/products/{target['product_id']}/incentive-points",
        json={"incentive_points": 7.0},
    )

    # Make a sale.
    client.post(
        "/api/sales",
        json={
            "branch_id": 1,
            "cashier_id": 1,
            "lines": [{"product_id": target["product_id"], "amount": 1}],
        },
    )

    # Fetch history for the cashier (employee 1).
    r = client.get("/api/incentives/employee/1")
    assert r.status_code == 200
    body = r.json()
    assert body["employee_id"] == 1
    assert float(body["total_points"]) == 7.0
    assert len(body["entries"]) >= 1


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
