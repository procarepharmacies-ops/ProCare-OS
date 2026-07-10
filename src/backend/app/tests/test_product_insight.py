"""Dashboard product drill-down endpoint."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m


def test_product_insight_shape(client, session):
    product = session.scalars(select(m.Product)).first()
    r = client.get(f"/api/inventory/products/{product.product_id}/insight")
    assert r.status_code == 200
    body = r.json()
    assert body["product_id"] == product.product_id
    assert "on_hand_by_branch" in body
    assert "forecast_30d" in body
    assert "recent_sales" in body
    # Per-branch breakdown covers every branch.
    assert len(body["on_hand_by_branch"]) == session.scalar(
        select(m.func.count()).select_from(m.Branch)
    )


def test_top_products_carry_product_id(client):
    r = client.get("/api/dashboard/top-products")
    assert r.status_code == 200
    products = r.json()["products"]
    if products:
        assert "product_id" in products[0]


def test_product_insight_404(client):
    assert client.get("/api/inventory/products/999999/insight").status_code == 404
