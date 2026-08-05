"""Phase 6 tests: notification center + ticker (News_bar / Flag parity)."""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db import models as m
from app.db.base import SessionLocal
from app.services import notifications as svc


@pytest.fixture(autouse=True)
def clean_dismissals():
    """Start each test with an empty dismissal log."""
    s = SessionLocal()
    try:
        s.execute(delete(m.NotificationDismissal))
        s.commit()
    finally:
        s.close()
    yield


def test_center_groups_by_category():
    s = SessionLocal()
    try:
        center = svc.notification_center(s, branch_id=1)
        cats = {g["category"] for g in center["groups"]}
        assert cats == {"expiry", "low_stock", "shortage"}
        # total equals the sum of the per-category counts.
        assert center["total"] == sum(g["count"] for g in center["groups"])
        # every category carries a bilingual label.
        assert all(g["label_ar"] and g["label_en"] for g in center["groups"])
    finally:
        s.close()


def test_ticker_is_severity_ranked_and_counts_match():
    s = SessionLocal()
    try:
        tk = svc.ticker(s, branch_id=1, limit=50)
        ranks = [svc._SEVERITY_RANK[i["severity"]] for i in tk["items"]]
        assert ranks == sorted(ranks)  # critical first
        assert tk["critical"] == sum(1 for i in tk["items"] if i["severity"] == "critical")
    finally:
        s.close()


def test_dismiss_hides_event_and_is_idempotent():
    s = SessionLocal()
    try:
        before = svc.ticker(s, branch_id=1, limit=50)
        if not before["items"]:
            pytest.skip("seed produced no live notifications")
        key = before["items"][0]["key"]

        r1 = svc.dismiss(s, [key], branch_id=1, by=1)
        assert r1["dismissed"] == 1
        after = svc.ticker(s, branch_id=1, limit=50)
        assert all(i["key"] != key for i in after["items"])
        assert after["total"] == before["total"] - 1

        # Dismissing the same key again is a no-op (no duplicate row).
        r2 = svc.dismiss(s, [key], branch_id=1, by=1)
        assert r2["dismissed"] == 0 and r2["skipped"] == 1
        assert s.query(m.NotificationDismissal).filter_by(event_key=key).count() == 1
    finally:
        s.close()


def test_event_keys_are_stable_and_prefixed():
    s = SessionLocal()
    try:
        tk = svc.ticker(s, branch_id=1, limit=50)
        for item in tk["items"]:
            assert item["key"].split(":")[0] in ("expiry", "low_stock", "shortage")
            assert item["category"] in svc.CATEGORIES
    finally:
        s.close()


# ------------------------------------------------------------------ API ----

def test_api_center_ticker_dismiss(client):
    center = client.get("/api/notifications", params={"branch_id": 1})
    assert center.status_code == 200
    assert "groups" in center.json()

    tk = client.get("/api/notifications/ticker", params={"branch_id": 1, "limit": 50})
    assert tk.status_code == 200
    items = tk.json()["items"]
    if not items:
        pytest.skip("no live notifications to dismiss via API")

    key = items[0]["key"]
    d = client.post("/api/notifications/dismiss", json={"event_keys": [key], "branch_id": 1})
    assert d.status_code == 200 and d.json()["dismissed"] == 1

    after = client.get("/api/notifications/ticker", params={"branch_id": 1, "limit": 50})
    assert all(i["key"] != key for i in after.json()["items"])
