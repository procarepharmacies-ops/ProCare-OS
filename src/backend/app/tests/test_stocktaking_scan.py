"""Stocktaking scan (الجرد بالباركود): resolve a scanned code to a count line."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import stocktaking


def _branch_with_stock(session) -> int:
    return session.scalars(
        select(m.StockBatch.branch_id).where(m.StockBatch.amount > 0).limit(1)
    ).first()


def _first_line_product(session, count_id):
    line = session.scalars(
        select(m.StockCountLine).where(m.StockCountLine.count_id == count_id).limit(1)
    ).first()
    return line, session.get(m.Product, line.product_id)


def test_scan_found_jumps_to_line(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    line, product = _first_line_product(session, count_id)
    product.code = "SCAN-TEST-0001"
    session.commit()

    r = stocktaking.scan_lookup(session, count_id, "SCAN-TEST-0001")
    assert r["result"] == "found"
    assert r["product"]["product_id"] == product.product_id
    assert any(l["line_id"] == line.line_id for l in r["lines"])
    assert r["lines"][0]["expected_qty"] >= 0


def test_scan_matches_fast_code(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    _, product = _first_line_product(session, count_id)
    product.code = None
    product.fast_code = "FC99"
    session.commit()

    r = stocktaking.scan_lookup(session, count_id, "FC99")
    assert r["result"] == "found"
    assert r["product"]["product_id"] == product.product_id


def test_scan_unknown_code(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    assert stocktaking.scan_lookup(session, count_id, "NO-SUCH-BARCODE-ZZZ")["result"] == "unknown"


def test_scan_product_not_in_partial_count(session):
    """A product outside a partial count's scope resolves to not_in_count."""
    branch_id = _branch_with_stock(session)
    batches = session.scalars(
        select(m.StockBatch).where(m.StockBatch.branch_id == branch_id, m.StockBatch.amount > 0)
    ).all()
    product_ids = list({b.product_id for b in batches})
    if len(product_ids) < 2:
        return  # need two products to prove scope exclusion
    in_scope, out_scope = product_ids[0], product_ids[1]
    count_id = stocktaking.create_count(
        session, branch_id, "partial", product_ids=[in_scope]
    )["count_id"]
    other = session.get(m.Product, out_scope)
    other.code = "OUT-OF-SCOPE-01"
    session.commit()

    r = stocktaking.scan_lookup(session, count_id, "OUT-OF-SCOPE-01")
    assert r["result"] == "not_in_count"
    assert r["product"]["product_id"] == out_scope


def test_scan_api(client, session):
    branch_id = _branch_with_stock(session)
    r = client.post("/api/stocktaking", json={"branch_id": branch_id, "count_type": "full"})
    assert r.status_code == 200, r.text
    count_id = r.json()["count_id"]

    r = client.get(f"/api/stocktaking/{count_id}/scan", params={"code": "UNKNOWN-XYZ"})
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "unknown"


def test_recent_alerts_route_is_not_shadowed(client):
    """`/recent-alerts` must be declared above the `/{count_id}` catch-all.

    Registered after it, FastAPI tries to parse "recent-alerts" as an int and
    returns 422 — which is what happened before, so the dashboard alert banner
    never worked. This is the regression guard.
    """
    r = client.get("/api/stocktaking/recent-alerts")
    assert r.status_code == 200, r.text
    assert "alerts" in r.json()
