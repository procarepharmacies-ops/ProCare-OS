"""API-level tests for the marketing router (Phase 4).

The service layer is covered by test_social.py / test_promo.py; these tests
exercise the HTTP endpoints end-to-end through the FastAPI TestClient —
routing, dependency wiring (auth payload → employee id), serialization.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta


def _code(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000000) % 1000000}"


def test_promo_create_list_validate_deactivate(client):
    code = _code("API")
    r = client.post("/api/marketing/promo-codes", json={
        "code": code,
        "discount_type": "percentage",
        "discount_value": 15,
        "valid_from": (datetime.now() - timedelta(days=1)).isoformat(),
        "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
        "max_uses": 50,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == code
    assert body["is_active"] is True
    assert body["remaining_uses"] == "50"

    r = client.get("/api/marketing/promo-codes")
    assert r.status_code == 200
    assert any(c["code"] == code for c in r.json()["codes"])

    r = client.get("/api/marketing/promo-codes/active")
    assert r.status_code == 200
    assert any(c["code"] == code for c in r.json()["codes"])

    r = client.get(f"/api/marketing/promo-codes/{code}/validate", params={"invoice_total": 200})
    assert r.status_code == 200
    v = r.json()
    assert v["valid"] is True
    assert v["discount_amount"] == 30.0
    assert v["final_total"] == 170.0

    r = client.patch(f"/api/marketing/promo-codes/{code}/deactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r = client.get(f"/api/marketing/promo-codes/{code}/validate")
    assert r.status_code == 400


def test_post_lifecycle_via_api(client):
    # Generate copy (falls back to templates without an API key — never 500s).
    r = client.post("/api/marketing/posts/generate-copy", json={"context": {"offer_name": "Test"}})
    assert r.status_code == 200
    assert r.json()["body_ar"]

    scheduled = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    r = client.post("/api/marketing/posts", json={
        "channel": "ig",
        "body_ar": "منشور تجريبي عبر الواجهة",
        "body_en": "API test post",
        "title": "API Test",
        "scheduled_at": scheduled.isoformat(),
    })
    assert r.status_code == 200, r.text
    post = r.json()
    post_id = post["post_id"]
    assert post["status"] == "draft"

    # Bad channel rejected.
    r = client.post("/api/marketing/posts", json={"channel": "myspace", "body_ar": "x"})
    assert r.status_code == 400

    # Calendar shows it in this month.
    r = client.get("/api/marketing/calendar", params={"channel": "ig", "month": scheduled.month})
    assert r.status_code == 200
    cal = r.json()
    found = [p for posts in cal["posts_by_date"].values() for p in posts if p["post_id"] == post_id]
    assert found, cal

    # Approve → publish.
    r = client.patch(f"/api/marketing/posts/{post_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = client.post(f"/api/marketing/posts/{post_id}/publish")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None

    # Detail endpoint.
    r = client.get(f"/api/marketing/posts/{post_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "published"

    # Publishing a draft (not approved) is rejected.
    r = client.post("/api/marketing/posts", json={"channel": "fb", "body_ar": "مسودة"})
    draft_id = r.json()["post_id"]
    r = client.post(f"/api/marketing/posts/{draft_id}/publish")
    assert r.status_code == 400


def test_post_with_invalid_promo_rejected(client):
    r = client.post("/api/marketing/posts", json={
        "channel": "fb",
        "body_ar": "منشور بكود غير موجود",
        "promo_code": "NOSUCHCODE999",
    })
    assert r.status_code == 400
