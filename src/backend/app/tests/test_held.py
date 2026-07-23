"""Phase 7 tests: hold/park invoice (parked carts — no stock touch)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import held as svc


@pytest.fixture(autouse=True)
def clean_held():
    s = SessionLocal()
    try:
        s.execute(delete(m.HeldInvoice))
        s.commit()
    finally:
        s.close()
    yield


def _a_product(session):
    return session.scalar(select(m.Product).where(m.Product.is_deleted == False))  # noqa: E712


def _branch_stock(session, branch_id=1):
    return float(session.scalar(
        select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(m.StockBatch.branch_id == branch_id)
    ) or 0)


def test_hold_saves_cart_and_touches_no_stock():
    s = SessionLocal()
    try:
        p = _a_product(s)
        before = _branch_stock(s, 1)
        out = svc.hold_invoice(
            s, 1, [{"product_id": p.product_id, "amount": 3, "sell_price": float(p.sell_price)}],
            cashier_id=1, note="stepped away",
        )
        assert out["lines"] == 1
        # Stock is completely untouched — a hold is just a saved cart.
        assert _branch_stock(s, 1) == pytest.approx(before)
        assert s.query(m.HeldInvoice).count() == 1
    finally:
        s.close()


def test_empty_hold_raises():
    from app.services.pos import POSError

    s = SessionLocal()
    try:
        with pytest.raises(POSError):
            svc.hold_invoice(s, 1, [])
    finally:
        s.close()


def test_list_purges_expired():
    s = SessionLocal()
    try:
        p = _a_product(s)
        svc.hold_invoice(s, 1, [{"product_id": p.product_id, "amount": 1}])
        # Force one hold to be already expired.
        stale = s.query(m.HeldInvoice).first()
        stale.expires_at = datetime.utcnow() - timedelta(days=1)
        s.commit()
        listed = svc.list_held(s, 1)
        assert listed["count"] == 0
        assert s.query(m.HeldInvoice).count() == 0  # purged
    finally:
        s.close()


def test_resume_flags_price_change_and_missing():
    s = SessionLocal()
    try:
        p = _a_product(s)
        # Store a price different from the current one → price_changed.
        held = svc.hold_invoice(s, 1, [
            {"product_id": p.product_id, "amount": 2, "sell_price": float(p.sell_price) + 5},
            {"product_id": 999999, "amount": 1, "sell_price": 10},  # missing product
        ])
        resumed = svc.resume_held(s, held["held_id"])
        by_pid = {l["product_id"]: l for l in resumed["lines"]}
        assert by_pid[p.product_id]["price_changed"] is True
        assert by_pid[p.product_id]["missing"] is False
        assert by_pid[999999]["missing"] is True
    finally:
        s.close()


def test_discard_removes_and_is_idempotent():
    s = SessionLocal()
    try:
        p = _a_product(s)
        held = svc.hold_invoice(s, 1, [{"product_id": p.product_id, "amount": 1}])
        assert svc.discard_held(s, held["held_id"]) is True
        assert svc.discard_held(s, held["held_id"]) is False  # already gone
    finally:
        s.close()


def test_api_hold_list_resume_discard(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    pid = products[0]["product_id"]

    h = client.post("/api/sales/hold", json={
        "branch_id": 1, "cashier_id": 1,
        "cart": [{"product_id": pid, "amount": 2, "sell_price": products[0]["sell_price"]}],
    })
    assert h.status_code == 200
    hid = h.json()["held_id"]

    listed = client.get("/api/sales/held", params={"branch_id": 1})
    assert any(x["held_id"] == hid for x in listed.json()["held"])

    resumed = client.get(f"/api/sales/held/{hid}/resume")
    assert resumed.status_code == 200 and resumed.json()["lines"][0]["product_id"] == pid

    d = client.post(f"/api/sales/held/{hid}/discard")
    assert d.status_code == 200 and d.json()["discarded"] is True
    assert client.get("/api/sales/held/999999/resume").status_code == 404
