"""Item sales-movement report (eStock حركة مبيعات صنف في فترة).

Builds a controlled ledger for one throw-away product and asserts the per-day
purchases/sales/returns/adjustments and the running closing balance, including
the reconcile-to-live-on-hand invariant.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db import models as m
from app.db.base import SessionLocal
from app.services import reports
from app.services.common import today


@pytest.fixture
def ledger():
    """One product on branch 1 with: purchase +50 (D-5), sale -20 (D-3),
    customer return +5 (D-2), جرد adjust -3 (D-1), and live on-hand 32.

    Net flow over the window = 50 - 20 + 5 - 3 = 32, so opening = 0 and the
    final closing must reconcile to the 32 on-hand.
    """
    d0 = today()
    s = SessionLocal()
    try:
        prod = m.Product(code="ZZTEST-MOVE", name_ar="صنف اختبار الحركة",
                         name_en="Move Test Item", unit_big="علبة", buy_price=10, sell_price=15)
        s.add(prod)
        s.flush()
        batch = m.StockBatch(product_id=prod.product_id, branch_id=1, amount=32,
                             buy_price=10, sell_price=15)
        s.add(batch)
        s.flush()

        def at(days_ago: int) -> datetime:
            d = d0 - timedelta(days=days_ago)
            return datetime(d.year, d.month, d.day, 12, 0)

        # Purchase +50 at D-5
        pur = m.Purchase(branch_id=1, vendor_id=1, bill_date=(d0 - timedelta(days=5)),
                         is_return=False)
        s.add(pur)
        s.flush()
        s.add(m.PurchaseLine(purchase_id=pur.purchase_id, product_id=prod.product_id,
                             amount=48, bonus=2, buy_price=10, sell_price=15))
        # Sale -20 at D-3
        sale = m.Sale(branch_id=1, sale_date=at(3), total_net=300, is_return=False)
        s.add(sale)
        s.flush()
        s.add(m.SaleLine(sale_id=sale.sale_id, product_id=prod.product_id, amount=20,
                         sell_price=15, buy_price=10, total_sell=300))
        # Customer return +5 at D-2
        ret = m.Sale(branch_id=1, sale_date=at(2), total_net=75, is_return=True)
        s.add(ret)
        s.flush()
        s.add(m.SaleLine(sale_id=ret.sale_id, product_id=prod.product_id, amount=5,
                         sell_price=15, buy_price=10, total_sell=75, is_return=True))
        # جرد adjust -3 at D-1
        s.add(m.StockMovement(batch_id=batch.batch_id, branch_id=1, delta=-3,
                              reason="adjust", created_at=at(1)))
        s.commit()
        pid = prod.product_id
    finally:
        s.close()
    # Clean up so the session-scoped seeded DB stays pristine for other tests.
    try:
        yield pid
    finally:
        _cleanup()


def _cleanup():
    from sqlalchemy import delete, select

    s = SessionLocal()
    try:
        pid = s.scalar(select(m.Product.product_id).where(m.Product.code == "ZZTEST-MOVE"))
        if pid is None:
            return
        sale_ids = list(s.scalars(select(m.Sale.sale_id).join(
            m.SaleLine, m.SaleLine.sale_id == m.Sale.sale_id).where(
            m.SaleLine.product_id == pid)))
        pur_ids = list(s.scalars(select(m.Purchase.purchase_id).join(
            m.PurchaseLine, m.PurchaseLine.purchase_id == m.Purchase.purchase_id).where(
            m.PurchaseLine.product_id == pid)))
        batch_ids = list(s.scalars(select(m.StockBatch.batch_id).where(
            m.StockBatch.product_id == pid)))
        s.execute(delete(m.SaleLine).where(m.SaleLine.product_id == pid))
        s.execute(delete(m.PurchaseLine).where(m.PurchaseLine.product_id == pid))
        if sale_ids:
            s.execute(delete(m.Sale).where(m.Sale.sale_id.in_(sale_ids)))
        if pur_ids:
            s.execute(delete(m.Purchase).where(m.Purchase.purchase_id.in_(pur_ids)))
        if batch_ids:
            s.execute(delete(m.StockMovement).where(m.StockMovement.batch_id.in_(batch_ids)))
        s.execute(delete(m.StockBatch).where(m.StockBatch.product_id == pid))
        s.execute(delete(m.Product).where(m.Product.product_id == pid))
        s.commit()
    finally:
        s.close()


def test_item_movement_reconciles(ledger):
    pid = ledger
    with SessionLocal() as s:
        r = reports.item_movement(s, pid, today() - timedelta(days=7), today(), branch_id=1)

    assert r["product"]["code"] == "ZZTEST-MOVE"
    assert r["on_hand_now"] == 32
    # opening rolled back through every flow = 0
    assert r["opening"] == 0
    # totals across the window
    t = r["totals"]
    assert t["purchased"] == 50  # 48 + 2 bonus
    assert t["sold"] == 20
    assert t["sale_returned"] == 5
    assert t["adjusted"] == -3
    # last day's closing == live on-hand
    assert r["reconciles"] is True
    assert r["totals"]["closing"] == 32
    # only the 4 active days appear, in date order
    assert len(r["rows"]) == 4
    dates = [row["date"] for row in r["rows"]]
    assert dates == sorted(dates)


def test_item_movement_running_balance(ledger):
    pid = ledger
    with SessionLocal() as s:
        r = reports.item_movement(s, pid, today() - timedelta(days=7), today(), branch_id=1)
    by_date = {row["date"]: row for row in r["rows"]}
    d = today()
    # D-5 purchase: closing 0 + 50 = 50
    assert by_date[(d - timedelta(days=5)).isoformat()]["closing"] == 50
    # D-3 sale: 50 - 20 = 30
    assert by_date[(d - timedelta(days=3)).isoformat()]["closing"] == 30
    # D-2 return: 30 + 5 = 35
    assert by_date[(d - timedelta(days=2)).isoformat()]["closing"] == 35
    # D-1 adjust: 35 - 3 = 32
    assert by_date[(d - timedelta(days=1)).isoformat()]["closing"] == 32


def test_item_movement_unknown_product():
    from app.services.pos import POSError

    with SessionLocal() as s:
        with pytest.raises(POSError):
            reports.item_movement(s, 99999999, today() - timedelta(days=7), today())


def test_item_movement_api(client, ledger):
    pid = ledger
    res = client.get(f"/api/reports/item-movement?product_id={pid}&days=7&branch_id=1")
    assert res.status_code == 200
    body = res.json()
    assert body["reconciles"] is True
    assert body["totals"]["sold"] == 20
    # CSV export
    csv_res = client.get(f"/api/reports/item-movement?product_id={pid}&days=7&branch_id=1&format=csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
