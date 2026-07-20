"""Prescription capture -> review -> cart -> dispensed workflow."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import prescriptions as rx


def _branch(session):
    return session.scalars(select(m.Branch)).first().branch_id


def _stocked_product(session, branch_id):
    row = session.execute(
        select(m.Product).join(m.StockBatch, m.StockBatch.product_id == m.Product.product_id)
        .where(m.StockBatch.branch_id == branch_id, m.StockBatch.amount > 0)
    ).first()
    return row[0]


def test_capture_review_cart_dispense(session, client):
    branch = _branch(session)
    product = _stocked_product(session, branch)

    # 1) Capture (manual, as if OCR produced these free-text lines).
    r = client.post("", json={}) if False else client.post(
        "/api/prescriptions",
        json={
            "branch_id": branch,
            "doctor_name": "د. منى",
            "drugs": [{"name": product.name_ar}, {"name": "دواء غير موجود بالكتالوج"}],
        },
    )
    assert r.status_code == 200
    pid = r.json()["prescription_id"]

    # 2) Resolve: the first line should match the real product.
    res = client.get(f"/api/prescriptions/{pid}/resolve", params={"branch_id": branch})
    assert res.status_code == 200
    lines = res.json()["lines"]
    assert lines[0]["best_product_id"] == product.product_id

    # 3) Review: confirm the resolved product for line 1.
    rev = client.post(
        f"/api/prescriptions/{pid}/review",
        json={"drugs": [{"name": product.name_ar, "product_id": product.product_id, "qty": 2}]},
    )
    assert rev.status_code == 200 and rev.json()["status"] == "reviewed"

    # 4) Cart: the reviewed, in-stock line is POS-ready.
    cart = client.get(f"/api/prescriptions/{pid}/cart", params={"branch_id": branch})
    assert cart.status_code == 200
    ready = cart.json()["lines"]
    assert len(ready) == 1
    assert ready[0]["product_id"] == product.product_id
    assert ready[0]["amount"] == 2

    # 5) Dispensed.
    disp = client.post(f"/api/prescriptions/{pid}/dispensed")
    assert disp.status_code == 200 and disp.json()["status"] == "dispensed"


def test_resolve_missing_prescription_404(client):
    assert client.get("/api/prescriptions/999999/resolve").status_code == 404
