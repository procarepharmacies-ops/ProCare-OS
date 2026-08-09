"""GS1 DataMatrix scanning during الجرد: batch pinning by encoded expiry.

Egyptian packs carry GTIN + expiry + lot under the EDA mandate. The expiry is
what makes this worth more than a plain EAN: count lines are per-batch, so the
scan lands on exactly one row.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import gs1, gtin_map, stocktaking

GTIN = "04006358001238"


def _branch_with_stock(session) -> int:
    return session.scalars(
        select(m.StockBatch.branch_id).where(m.StockBatch.amount > 0).limit(1)
    ).first()


def _clear_map(session, gtin=GTIN):
    for row in session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin)
    ).all():
        session.delete(row)
    session.commit()


def _count_with_dated_batch(session):
    """Open a count and return (count_id, line, batch) for a line whose batch
    carries an expiry — the case GS1 batch-pinning is about."""
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    rows = session.execute(
        select(m.StockCountLine, m.StockBatch)
        .join(m.StockBatch, m.StockBatch.batch_id == m.StockCountLine.batch_id)
        .where(m.StockCountLine.count_id == count_id, m.StockBatch.exp_date.is_not(None))
    ).all()
    assert rows, "seed must include at least one batch with an expiry date"
    line, batch = rows[0]
    return count_id, line, batch


def _payload(expiry=None, lot=None, gtin=GTIN):
    out = "01" + gtin
    if expiry:
        out += "17" + expiry.strftime("%y%m%d")
    if lot:
        out += "10" + lot
    return out


def test_gs1_scan_pins_the_exact_batch(session):
    count_id, line, batch = _count_with_dated_batch(session)
    _clear_map(session)
    gtin_map.learn(session, GTIN, line.product_id)
    try:
        r = stocktaking.scan_lookup(session, count_id, _payload(batch.exp_date, "LOT-A1"))
        assert r["result"] == "found"
        assert r["scan"]["kind"] == "gs1"
        assert r["scan"]["gtin"] == GTIN
        assert r["scan"]["lot"] == "LOT-A1"  # echoed; StockBatch has no lot column
        assert r["scan"]["expiry"] == batch.exp_date.isoformat()
        assert r["matched_line_id"] == line.line_id
        assert r["expiry_mismatch"] is False
        matched = [l for l in r["lines"] if l["batch_match"]]
        assert [l["line_id"] for l in matched] == [line.line_id]
    finally:
        _clear_map(session)


def test_gs1_expiry_with_no_booked_batch_still_finds_the_product(session):
    """An unbooked batch is a signal, never a block: result stays 'found'."""
    count_id, line, batch = _count_with_dated_batch(session)
    _clear_map(session)
    gtin_map.learn(session, GTIN, line.product_id)
    try:
        stray = batch.exp_date.replace(year=batch.exp_date.year + 5)
        r = stocktaking.scan_lookup(session, count_id, _payload(stray))
        assert r["result"] == "found"
        assert r["matched_line_id"] is None
        assert r["expiry_mismatch"] is True
        assert all(l["batch_match"] is False for l in r["lines"])
    finally:
        _clear_map(session)


def test_gs1_unknown_gtin_still_reports_the_scan(session):
    """The UI needs the parsed GTIN back so it can offer 'link this barcode'."""
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    _clear_map(session)
    r = stocktaking.scan_lookup(session, count_id, _payload())
    assert r["result"] == "unknown"
    assert r["scan"]["gtin"] == GTIN


def test_plain_code_scan_keeps_its_shape(session):
    """Backward compatibility: a plain code reports kind='plain', no batch pin."""
    count_id, line, _ = _count_with_dated_batch(session)
    product = session.get(m.Product, line.product_id)
    product.code = "PLAIN-COMPAT-1"
    session.commit()

    r = stocktaking.scan_lookup(session, count_id, "PLAIN-COMPAT-1")
    assert r["result"] == "found"
    assert r["scan"]["kind"] == "plain"
    assert r["scan"]["expiry"] is None
    assert r["matched_line_id"] is None
    assert r["expiry_mismatch"] is False


def test_scan_link_endpoint_is_idempotent(client, session):
    """POST /scan/link twice = one mapping. Safe to replay from an offline queue."""
    count_id, line, _ = _count_with_dated_batch(session)
    _clear_map(session)
    try:
        body = {"code": _payload(), "product_id": line.product_id}
        first = client.post(f"/api/stocktaking/{count_id}/scan/link", json=body)
        assert first.status_code == 200, first.text
        assert first.json()["created"] is True

        second = client.post(f"/api/stocktaking/{count_id}/scan/link", json=body)
        assert second.status_code == 200, second.text
        assert second.json()["created"] is False

        # And the barcode now resolves on scan.
        r = client.get(f"/api/stocktaking/{count_id}/scan", params={"code": _payload()})
        assert r.json()["result"] == "found"
    finally:
        _clear_map(session)


def test_scan_link_rejects_a_non_barcode(client, session):
    count_id, line, _ = _count_with_dated_batch(session)
    r = client.post(
        f"/api/stocktaking/{count_id}/scan/link",
        json={"code": "P1000", "product_id": line.product_id},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_gtin"


def test_gs1_helper_payload_round_trips():
    """Guard the test helper itself: what we build must parse back."""
    from datetime import date

    parsed = gs1.parse_gs1(_payload(date(2027, 3, 31), "L9"))
    assert parsed["gtin"] == GTIN
    assert parsed["expiry"] == date(2027, 3, 31)
    assert parsed["lot"] == "L9"
