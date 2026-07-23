"""Phase 7 tests: POS invoice depth — batch pick, note, nearest expiry."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.services import pos
from app.services.common import today


def _two_batches(session, branch_id=1):
    """A product with two sellable batches at a branch: an older-expiry one and
    a fresher one. Returns (product_id, older_batch_id, fresher_batch_id)."""
    p = m.Product(name_ar="عينة دفعتين", sell_price=10, buy_price=6, min_stock=0)
    session.add(p)
    session.flush()
    older = m.StockBatch(product_id=p.product_id, branch_id=branch_id, amount=5,
                         buy_price=6, sell_price=10, exp_date=today() + timedelta(days=30))
    fresher = m.StockBatch(product_id=p.product_id, branch_id=branch_id, amount=5,
                           buy_price=6, sell_price=10, exp_date=today() + timedelta(days=300))
    session.add_all([older, fresher])
    session.flush()
    return p.product_id, older.batch_id, fresher.batch_id


def _sellable(session, product_id, branch_id=1):
    return float(session.scalar(
        select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
            m.StockBatch.product_id == product_id, m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
        )
    ) or 0)


def test_pinned_batch_consumed_first(session):
    pid, older, fresher = _two_batches(session)
    session.commit()
    # Pin the FRESHER batch (customer wants the newer box) — 3 units.
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 3, batch_id=fresher)], cashier_id=1,
    )
    # Fresher batch drained by 3 (5 -> 2); older untouched (still 5).
    assert float(session.get(m.StockBatch, fresher).amount) == pytest.approx(2.0)
    assert float(session.get(m.StockBatch, older).amount) == pytest.approx(5.0)
    line = sale.lines[0]
    assert line.batch_id == fresher


def test_pinned_batch_spills_fefo_when_short(session):
    pid, older, fresher = _two_batches(session)
    session.commit()
    # Pin fresher (5 units) but ask for 7 → take 5 from fresher, spill 2 FEFO (older).
    pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 7, batch_id=fresher)], cashier_id=1)
    assert float(session.get(m.StockBatch, fresher).amount) == pytest.approx(0.0)
    assert float(session.get(m.StockBatch, older).amount) == pytest.approx(3.0)  # 5 - 2 spill


def test_bad_batch_pin_raises(session):
    pid, older, fresher = _two_batches(session)
    session.commit()
    with pytest.raises(pos.POSError) as ei:
        pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 1, batch_id=999999)], cashier_id=1)
    assert ei.value.code == "bad_batch"


def test_pinned_expired_batch_refused(session):
    p = m.Product(name_ar="منتهي مثبّت", sell_price=10, buy_price=6, min_stock=0)
    session.add(p)
    session.flush()
    expired = m.StockBatch(product_id=p.product_id, branch_id=1, amount=5, buy_price=6,
                           sell_price=10, exp_date=today() - timedelta(days=1))
    session.add(expired)
    session.commit()
    # An expired batch is not in the sellable set → pinning it is a bad_batch.
    with pytest.raises(pos.POSError) as ei:
        pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(p.product_id, 1, batch_id=expired.batch_id)], cashier_id=1)
    assert ei.value.code == "bad_batch"


def test_sale_note_round_trips(session):
    pid, older, fresher = _two_batches(session)
    session.commit()
    sale = pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)],
                           cashier_id=1, note="عميل يفضل بعد الأكل")
    assert sale.note == "عميل يفضل بعد الأكل"
    fetched = session.get(m.Sale, sale.sale_id)
    assert fetched.note == "عميل يفضل بعد الأكل"


def test_api_sale_note_and_detail_fields(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 1)
    r = client.post("/api/sales", json={
        "branch_id": 1, "cashier_id": 1, "note": "invoice note",
        "lines": [{"product_id": target["product_id"], "amount": 1}],
    })
    assert r.status_code == 200
    detail = client.get(f"/api/sales/{r.json()['sale_id']}").json()
    assert detail["note"] == "invoice note"
    assert "dosage_form" in detail["lines"][0] and "uses" in detail["lines"][0]


def test_products_list_exposes_nearest_expiry(client):
    body = client.get("/api/inventory/products?branch_id=1").json()
    assert "products" in body
    # Every row carries the key (value may be null for no-expiry stock).
    assert all("nearest_expiry" in p for p in body["products"])
