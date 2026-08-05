"""Phase 6 tests: change history — price log, stock log, login audit."""
from __future__ import annotations

import pytest
from sqlalchemy import delete, func, select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import changelog, inventory, pos
from app.services.common import today


def _a_product(session):
    return session.scalar(select(m.Product.product_id).where(m.Product.is_deleted == False))  # noqa: E712


def _product_with_live_stock(session, branch_id):
    row = session.execute(
        select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
        .where(
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
        )
        .group_by(m.StockBatch.product_id)
        .order_by(func.sum(m.StockBatch.amount).desc())
    ).first()
    return row[0], float(row[1])


def test_price_edit_logs_change_with_old_and_new(session):
    pid = _a_product(session)
    old = float(session.get(m.Product, pid).sell_price)
    new = round(old + 7.5, 2)

    out = inventory.update_product_pricing(session, pid, sell_price=new, employee_id=1)
    assert out["changed"] == [{"field": "sell_price", "old": round(old, 3), "new": round(new, 3)}]
    assert float(session.get(m.Product, pid).sell_price) == pytest.approx(new)

    changes = changelog.product_changes(session, product_id=pid, days=1)
    top = changes[0]
    assert top["field"] == "sell_price"
    assert top["old_value"] == pytest.approx(old)
    assert top["new_value"] == pytest.approx(new)
    assert top["employee_id"] == 1


def test_noop_price_edit_logs_nothing(session):
    pid = _a_product(session)
    same = float(session.get(m.Product, pid).sell_price)
    before = len(changelog.product_changes(session, product_id=pid, days=1))
    out = inventory.update_product_pricing(session, pid, sell_price=same, employee_id=1)
    assert out["changed"] == []
    assert len(changelog.product_changes(session, product_id=pid, days=1)) == before


def test_update_unknown_product_raises(session):
    with pytest.raises(pos.POSError):
        inventory.update_product_pricing(session, 999999, sell_price=10)


def test_stock_changes_reflect_a_sale(session):
    pid, _ = _product_with_live_stock(session, 1)
    pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)], cashier_id=1)

    rows = changelog.stock_changes(session, product_id=pid, branch_id=1, days=1)
    assert rows, "the sale should have written a stock movement"
    sale_mv = rows[0]
    assert sale_mv["reason"] == "sale"
    assert sale_mv["reason_ar"] and sale_mv["reason_en"]
    assert sale_mv["delta"] < 0  # a sale decrements stock


def test_login_history_returns_recent_events(session):
    session.add(m.AuthEvent(username="tester", event="login_ok", employee_id=1, ip="127.0.0.1"))
    session.commit()
    hist = changelog.login_history(session, days=1)
    assert any(e["username"] == "tester" and e["event"] == "login_ok" for e in hist)


# ------------------------------------------------------------------ API ----

def test_api_pricing_edit_and_change_history(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    pid = products[0]["product_id"]
    old = float(products[0]["sell_price"])

    r = client.post(f"/api/inventory/products/{pid}/pricing", json={"sell_price": old + 3, "employee_id": 1})
    assert r.status_code == 200
    assert r.json()["changed"][0]["field"] == "sell_price"

    hist = client.get("/api/audit/product-changes", params={"product_id": pid, "days": 1})
    assert hist.status_code == 200
    assert any(c["field"] == "sell_price" for c in hist.json()["changes"])


def test_api_stock_changes(client):
    r = client.get("/api/audit/stock-changes", params={"branch_id": 1, "days": 30})
    assert r.status_code == 200
    assert "changes" in r.json()
