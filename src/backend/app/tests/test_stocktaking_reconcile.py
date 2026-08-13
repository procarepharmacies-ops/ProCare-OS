"""Offline-replay support: absolute-state writes, conflict reporting, scan index.

These are the properties the RX offline queue depends on. If they break, a
counter's numbers get silently lost or duplicated — so they are asserted
directly rather than inferred.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as m
from app.services import stocktaking
from app.services.pos import POSError


def _branch_with_stock(session) -> int:
    return session.scalars(
        select(m.StockBatch.branch_id).where(m.StockBatch.amount > 0).limit(1)
    ).first()


def _open_count(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    line = session.scalars(
        select(m.StockCountLine).where(m.StockCountLine.count_id == count_id).limit(1)
    ).first()
    return count_id, line


def test_replay_is_idempotent(session):
    """Replaying the same entry N times lands on the same number.

    This is the whole basis for queueing counts offline WITHOUT an
    idempotency key: the write is absolute state, not a delta.
    """
    count_id, line = _open_count(session)
    for _ in range(3):
        stocktaking.record_lines(
            session, count_id, [{"line_id": line.line_id, "counted_qty": 9}]
        )
    session.refresh(line)
    assert float(line.counted_qty) == pytest.approx(9)


def test_no_base_means_no_conflict_check(session):
    """The desktop sheet sends no base — it must never see conflicts."""
    count_id, line = _open_count(session)
    stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 4}])
    r = stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 7}])
    assert r["conflicts"] == []
    assert r["saved"] == 1


def test_stale_base_reports_conflict_but_still_applies(session):
    """A colleague counted the same shelf: warn, never block."""
    count_id, line = _open_count(session)
    # Someone else records 7.
    stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 7}])
    # Our phone replays a value based on the 5 it last saw.
    r = stocktaking.record_lines(
        session,
        count_id,
        [{"line_id": line.line_id, "counted_qty": 9, "base_counted_qty": 5}],
    )
    assert r["saved"] == 1
    assert len(r["conflicts"]) == 1
    conflict = r["conflicts"][0]
    assert conflict["reason"] == "overwritten"
    assert conflict["server_counted_qty"] == pytest.approx(7)
    # Last write wins — the count is never blocked mid-session.
    session.refresh(line)
    assert float(line.counted_qty) == pytest.approx(9)


def test_matching_base_is_not_a_conflict(session):
    count_id, line = _open_count(session)
    stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 6}])
    r = stocktaking.record_lines(
        session,
        count_id,
        [{"line_id": line.line_id, "counted_qty": 8, "base_counted_qty": 6}],
    )
    assert r["conflicts"] == []


def test_uncounted_base_null_matches(session):
    """A never-counted line has base null; that must not read as a conflict."""
    count_id, line = _open_count(session)
    r = stocktaking.record_lines(
        session,
        count_id,
        [{"line_id": line.line_id, "counted_qty": 3, "base_counted_qty": None}],
    )
    assert r["conflicts"] == []


def test_missing_line_is_reported_not_raised(session):
    count_id, _ = _open_count(session)
    r = stocktaking.record_lines(session, count_id, [{"line_id": 99999999, "counted_qty": 1}])
    assert r["saved"] == 0
    assert r["conflicts"][0]["reason"] == "line_missing"


def test_replay_into_a_posted_count_is_terminal(session):
    """The queue must classify this as terminal, not retry it forever."""
    count_id, line = _open_count(session)
    stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 2}])
    stocktaking.post_count(session, count_id)
    with pytest.raises(POSError) as exc:
        stocktaking.record_lines(session, count_id, [{"line_id": line.line_id, "counted_qty": 2}])
    assert exc.value.code == "count_closed"


# ---- scan index ----------------------------------------------------------

def test_scan_index_carries_codes_and_batches(session):
    count_id, line = _open_count(session)
    product = session.get(m.Product, line.product_id)
    product.code = "IDX-CODE-1"
    session.commit()

    idx = stocktaking.scan_index(session, count_id)
    assert idx["count_id"] == count_id
    assert idx["status"] == "open"
    item = next(i for i in idx["items"] if i["product_id"] == line.product_id)
    assert "IDX-CODE-1" in item["codes"]
    assert any(l["line_id"] == line.line_id for l in item["lines"])
    # One entry per product, batches nested — that is what the phone indexes on.
    assert len({i["product_id"] for i in idx["items"]}) == len(idx["items"])


def test_scan_index_includes_learned_gtins(session):
    """A GS1 scan must resolve offline, so learned barcodes ship in the index."""
    from app.services import gtin_map

    count_id, line = _open_count(session)
    gtin = "04006358001238"
    for row in session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin)
    ).all():
        session.delete(row)
    session.commit()
    gtin_map.learn(session, gtin, line.product_id)
    try:
        idx = stocktaking.scan_index(session, count_id)
        item = next(i for i in idx["items"] if i["product_id"] == line.product_id)
        assert gtin in item["codes"]
    finally:
        for row in session.scalars(
            select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin)
        ).all():
            session.delete(row)
        session.commit()


def test_scan_index_api(client, session):
    branch_id = _branch_with_stock(session)
    count_id = client.post(
        "/api/stocktaking", json={"branch_id": branch_id, "count_type": "full"}
    ).json()["count_id"]
    r = client.get(f"/api/stocktaking/{count_id}/scan-index")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] and "codes" in body["items"][0]


def test_record_api_passes_base_through(client, session):
    """The absent-vs-null distinction must survive the Pydantic layer."""
    branch_id = _branch_with_stock(session)
    count_id = client.post(
        "/api/stocktaking", json={"branch_id": branch_id, "count_type": "full"}
    ).json()["count_id"]
    sheet = client.get(f"/api/stocktaking/{count_id}").json()
    line_id = sheet["lines"][0]["line_id"]

    # No base -> no conflict, even though the value changes.
    client.post(f"/api/stocktaking/{count_id}/lines",
                json={"entries": [{"line_id": line_id, "counted_qty": 5}]})
    r = client.post(f"/api/stocktaking/{count_id}/lines",
                    json={"entries": [{"line_id": line_id, "counted_qty": 6}]})
    assert r.json()["conflicts"] == []

    # Stale base -> conflict reported, write still applied.
    r = client.post(
        f"/api/stocktaking/{count_id}/lines",
        json={"entries": [{"line_id": line_id, "counted_qty": 11, "base_counted_qty": 1}]},
    )
    body = r.json()
    assert body["saved"] == 1
    assert body["conflicts"][0]["reason"] == "overwritten"
