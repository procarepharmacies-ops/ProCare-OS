"""Stocktaking (الجرد): create → count → post applies adjustments atomically."""
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


def test_full_count_snapshot_and_post(session):
    branch_id = _branch_with_stock(session)
    r = stocktaking.create_count(session, branch_id, "full", note="جرد اختباري")
    count_id = r["count_id"]
    assert r["lines"] > 0 and r["status"] == "open"

    sheet = stocktaking.get_count(session, count_id)
    line = sheet["lines"][0]
    assert line["counted_qty"] is None and line["expected_qty"] >= 0

    # Count one line short by 1 (a shortage).
    physical = max(0.0, line["expected_qty"] - 1)
    stocktaking.record_lines(session, count_id, [{"line_id": line["line_id"], "counted_qty": physical}])
    sheet = stocktaking.get_count(session, count_id)
    counted = next(l for l in sheet["lines"] if l["line_id"] == line["line_id"])
    assert counted["counted_qty"] == physical
    assert counted["variance"] == pytest.approx(physical - line["expected_qty"])
    assert sheet["summary"]["counted_lines"] == 1

    posted = stocktaking.post_count(session, count_id, employee_id=None)
    assert posted["status"] == "posted"

    # The batch now sits exactly on the physical quantity...
    batch = session.get(m.StockBatch, line["batch_id"])
    assert float(batch.amount) == pytest.approx(physical)
    # ...and the adjustment is in the audit trail, tied to this count.
    move = session.scalars(
        select(m.StockMovement).where(
            m.StockMovement.reason == "adjust", m.StockMovement.ref_id == count_id
        )
    ).first()
    assert move is not None and float(move.delta) == pytest.approx(physical - line["expected_qty"])


def test_posted_count_is_closed(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "partial")["count_id"]
    line = stocktaking.get_count(session, count_id)["lines"][0]
    stocktaking.record_lines(session, count_id, [{"line_id": line["line_id"], "counted_qty": line["expected_qty"]}])
    stocktaking.post_count(session, count_id)
    with pytest.raises(POSError):
        stocktaking.record_lines(session, count_id, [{"line_id": line["line_id"], "counted_qty": 1}])
    with pytest.raises(POSError):
        stocktaking.post_count(session, count_id)


def test_post_requires_a_counted_line(session):
    branch_id = _branch_with_stock(session)
    count_id = stocktaking.create_count(session, branch_id, "full")["count_id"]
    with pytest.raises(POSError):
        stocktaking.post_count(session, count_id)
    assert stocktaking.cancel_count(session, count_id)["status"] == "cancelled"


def test_api_flow(client):
    counts = client.get("/api/stocktaking").json()["counts"]
    baseline = len(counts)
    branch_id = client.get("/api/dashboard/kpis").json().get("branch_id") or 1
    r = client.post("/api/stocktaking", json={"branch_id": 1, "count_type": "full"})
    assert r.status_code == 200, r.text
    count_id = r.json()["count_id"]
    assert len(client.get("/api/stocktaking").json()["counts"]) == baseline + 1

    sheet = client.get(f"/api/stocktaking/{count_id}").json()
    line = sheet["lines"][0]
    r = client.post(
        f"/api/stocktaking/{count_id}/lines",
        json={"entries": [{"line_id": line["line_id"], "counted_qty": line["expected_qty"] + 2}]},
    )
    assert r.status_code == 200 and r.json()["saved"] == 1

    r = client.post(f"/api/stocktaking/{count_id}/post", json={})
    assert r.status_code == 200 and r.json()["status"] == "posted"
    sheet = client.get(f"/api/stocktaking/{count_id}").json()
    assert sheet["status"] == "posted"
    assert sheet["summary"]["overage_qty"] == pytest.approx(2)


def test_search_prefix_ranked_first(client):
    # Any product's first letter must list prefix matches before contains-matches.
    products = client.get("/api/inventory/products").json()["products"]
    assert products, "seeded products expected"
    first_letter = products[0]["name_ar"][0]
    ranked = client.get(f"/api/inventory/products?search={first_letter}").json()["products"]
    assert ranked, "one letter must return suggestions"
    # Every leading block of results starts with the letter; once a
    # non-prefix (contains) match appears, no prefix match may follow it.
    seen_contains = False
    for p in ranked:
        is_prefix = (p["name_ar"] or "").startswith(first_letter) or (
            (p["name_en"] or "").lower().startswith(first_letter.lower())
        ) or ((p["code"] or "").startswith(first_letter))
        if not is_prefix:
            seen_contains = True
        else:
            assert not seen_contains, "prefix match ranked below a contains match"
