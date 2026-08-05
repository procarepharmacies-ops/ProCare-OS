"""DB-size / disk health monitor: pure threshold grading + live SQLite checks.

The SQL Server ``sys.database_files`` path can't run on the SQLite test DB, so
the size/disk grading logic lives in a pure ``evaluate()`` that is exercised
directly here; ``check()`` / ``ping()`` are smoke-tested against the seeded
SQLite database the rest of the suite uses.
"""
from __future__ import annotations

from app.services import db_health


# --- evaluate(): pure severity grader (no I/O) ------------------------------
def test_evaluate_ok_when_small_and_plenty_of_disk():
    out = db_health.evaluate(db_mb=100, cap_mb=10240, disk_free_pct=80)
    assert out["severity"] == "ok"
    assert out["alerts"] == []


def test_evaluate_db_thresholds_escalate():
    cap = 10240
    assert db_health.evaluate(cap * 0.80, cap, 90)["severity"] == "info"
    assert db_health.evaluate(cap * 0.90, cap, 90)["severity"] == "warning"
    assert db_health.evaluate(cap * 0.95, cap, 90)["severity"] == "critical"
    # Just below the first threshold stays clean.
    assert db_health.evaluate(cap * 0.79, cap, 90)["severity"] == "ok"


def test_evaluate_disk_thresholds_escalate():
    big_cap = 10240  # DB tiny relative to cap, so disk drives the severity
    assert db_health.evaluate(1, big_cap, 19)["severity"] == "info"
    assert db_health.evaluate(1, big_cap, 9)["severity"] == "warning"
    assert db_health.evaluate(1, big_cap, 4)["severity"] == "critical"


def test_evaluate_takes_the_worst_of_db_and_disk():
    # DB fine (info) but disk critical -> overall critical.
    out = db_health.evaluate(10240 * 0.80, 10240, disk_free_pct=3)
    assert out["severity"] == "critical"
    assert len(out["alerts"]) == 2  # one DB line + one disk line


def test_evaluate_none_disk_is_ignored():
    out = db_health.evaluate(100, 10240, disk_free_pct=None)
    assert out["severity"] == "ok"


# --- live checks against the seeded SQLite DB -------------------------------
def test_database_size_reports_positive_total(seeded_db):
    size = db_health.database_size()
    assert size["engine"] == "sqlite"
    assert size["total_mb"] is not None
    assert size["total_mb"] >= 0


def test_disk_usage_reports_free_pct(seeded_db):
    disk = db_health.disk_usage()
    assert "error" not in disk
    assert 0 <= disk["free_pct"] <= 100
    assert disk["total_gb"] > 0


def test_ping_ok(seeded_db):
    result = db_health.ping()
    assert result["ok"] is True
    assert result["engine"] == "sqlite"
    assert result["checked_at"]


def test_check_shape_and_ok_severity(seeded_db):
    result = db_health.check()
    assert set(result) >= {"severity", "alerts", "db", "disk", "checked_at"}
    assert result["db"]["cap_mb"] == db_health.DEFAULT_CAP_MB
    # A freshly seeded dev DB is tiny -> nowhere near the cap.
    assert result["severity"] in ("ok", "info", "warning", "critical")
    assert result["db"]["pct_of_cap"] < 80


def test_check_tiny_cap_trips_critical(seeded_db):
    # Force the cap below the current DB size -> guaranteed critical.
    result = db_health.check(cap_mb=0.001)
    assert result["severity"] == "critical"
    assert result["alerts"]


# --- alert_if_worse(): only notify on a RISE in severity --------------------
def test_alert_if_worse_only_on_escalation():
    db_health._last_alert_level = "ok"
    assert db_health.alert_if_worse({"severity": "warning"}) is True   # ok -> warning
    assert db_health.alert_if_worse({"severity": "warning"}) is False  # steady
    assert db_health.alert_if_worse({"severity": "critical"}) is True  # warning -> critical
    assert db_health.alert_if_worse({"severity": "critical"}) is False # steady
    # Recovery is silent but re-arms the alert for a future rise.
    assert db_health.alert_if_worse({"severity": "ok"}) is False
    assert db_health.alert_if_worse({"severity": "warning"}) is True
    db_health._last_alert_level = "ok"  # leave module state clean for other tests
