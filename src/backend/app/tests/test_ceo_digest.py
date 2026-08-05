"""8am CEO digest: the yesterday-focused briefing pack, its WhatsApp message,
the top_products date-window override it relies on, and on-demand job firing."""
from __future__ import annotations

from datetime import timedelta

from app.services import dashboard, scheduler, whatsapp
from app.services.common import today


def test_ceo_digest_shape(session):
    data = dashboard.ceo_digest(session)
    assert set(data) >= {
        "as_of", "revenue_yesterday", "bills_yesterday", "top_sellers",
        "low_stock", "expiring_7d", "debtors_count", "debtors_over_limit_total",
    }
    # "yesterday" relative to the business clock.
    assert data["as_of"] == (today() - timedelta(days=1)).isoformat()
    assert isinstance(data["top_sellers"], list)
    assert len(data["top_sellers"]) <= 3
    assert isinstance(data["bills_yesterday"], int)
    assert data["low_stock"] >= 0


def test_ceo_digest_message_is_arabic_and_complete(session):
    data = dashboard.ceo_digest(session)
    msg = whatsapp.ceo_digest_message(data)
    assert isinstance(msg, str)
    assert "ملخص بروكير الصباحي" in msg          # header
    assert "مبيعات أمس" in msg                     # yesterday revenue line
    assert str(data["low_stock"]) in msg           # numbers actually rendered
    # Never raises on an empty day (no sellers / no debtors).
    empty = whatsapp.ceo_digest_message({"as_of": "2026-06-25"})
    assert isinstance(empty, str) and "ملخص بروكير الصباحي" in empty


def test_top_products_end_bound_limits_window(session):
    # Explicit start=end=yesterday must never return more than the wide window,
    # and must respect the limit.
    y = today() - timedelta(days=1)
    day_only = dashboard.top_products(session, start=y, end=y, limit=3)
    wide = dashboard.top_products(session, days=365, limit=50)
    assert len(day_only) <= 3
    assert len(day_only) <= len(wide)
    for row in day_only:
        assert {"product_id", "name_ar", "name_en", "units", "revenue"} <= set(row)


def test_top_products_default_behaviour_unchanged(session):
    # No start/end -> trailing-days behaviour, same as before the refactor.
    out = dashboard.top_products(session, days=30, limit=5)
    assert isinstance(out, list)
    assert len(out) <= 5


def test_run_now_ceo_digest_and_db_health(session):
    # Fires the jobs on demand (works without APScheduler running). notify_manager
    # self-gates with no phone/creds in the test env, so nothing is sent.
    r1 = scheduler.run_now("ceo_digest")
    assert r1["ran"] is True
    assert r1["result"] and "revenue_yesterday" in r1["result"]

    r2 = scheduler.run_now("db_health")
    assert r2["ran"] is True
    assert "severity" in r2["result"]

    r3 = scheduler.run_now("health_selfping")
    assert r3["ran"] is True
    assert r3["result"]["ok"] is True
