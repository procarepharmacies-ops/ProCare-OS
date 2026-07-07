"""Tests for the automation scheduler (services.scheduler + /api/automation).

The jobs are shadow-safe: they compute and log against the seeded data and must
run without APScheduler installed (fireable on demand), never mutating anything.
"""
from __future__ import annotations

from app.services import scheduler


def test_run_now_jobs_compute_results():
    for job in ("expiry_alerts", "auto_purchase_order", "auto_reports"):
        out = scheduler.run_now(job)
        assert out["ran"] is True, job
        assert out["job"] == job
        assert out["result"] is not None, job


def test_run_now_unknown_job():
    out = scheduler.run_now("does_not_exist")
    assert out["ran"] is False
    assert "unknown job" in out["error"]


def test_jobs_overview_idle_when_not_started():
    # Not started in the test env (AUTOMATION_ENABLED unset) — reports cleanly.
    ov = scheduler.jobs_overview()
    assert ov["running"] is False
    assert ov["enabled"] is False
    assert isinstance(ov["jobs"], list)


def test_auto_purchase_is_shadow_safe(session):
    """The hourly reorder job computes drafts but must NOT write PurchaseOrderDraft
    rows (Phase-1 shadow mode) — a human approves in Phase 2."""
    from app.db import models as m

    before = session.query(m.PurchaseOrderDraft).count()
    scheduler.run_now("auto_purchase_order")
    session.expire_all()
    after = session.query(m.PurchaseOrderDraft).count()
    assert after == before


def test_api_status_and_run(client):
    r = client.get("/api/automation/status")
    assert r.status_code == 200
    assert "jobs" in r.json()

    r2 = client.post("/api/automation/run/expiry_alerts")
    assert r2.status_code == 200
    assert r2.json()["ran"] is True

    r3 = client.post("/api/automation/run/nope")
    assert r3.status_code == 404
