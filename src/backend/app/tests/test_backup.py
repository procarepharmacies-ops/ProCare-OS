"""Backup destination and the startup throttle.

app/main.py runs backup.backup_if_stale(24, "startup-daily") synchronously in
the FastAPI lifespan, so a throttle that fails open blocks the pharmacy from
starting for as long as a full backup takes. These cover the destination
override and that the throttle actually engages.
"""
from __future__ import annotations

from app.services import backup


def test_backup_dir_override_is_honoured(tmp_path, monkeypatch, seeded_db):
    vault = tmp_path / "vault"
    monkeypatch.setenv("PROCARE_BACKUP_DIR", str(vault))

    res = backup.backup_now("test")

    assert res["ok"], res
    written = list(vault.glob("procare-*"))
    assert len(written) == 1, f"expected one backup in {vault}, got {written}"
    # The override directory is created on demand, not assumed to exist.
    assert vault.is_dir()


def test_backup_if_stale_skips_when_fresh(tmp_path, monkeypatch, seeded_db):
    """The regression that hung startup: a backup ran on EVERY boot because
    last_backup_at() looked somewhere the backup was never written."""
    monkeypatch.setenv("PROCARE_BACKUP_DIR", str(tmp_path / "vault"))

    assert backup.backup_now("first")["ok"]
    assert backup.last_backup_at() is not None

    # Fresh backup on disk -> the 24h window must SKIP rather than re-run.
    assert backup.backup_if_stale(24, "startup-daily") is None

    # A zero-length window always runs, so the throttle is the only thing
    # suppressing it above.
    forced = backup.backup_if_stale(0, "forced")
    assert forced is not None and forced["ok"]


def test_backup_reports_failure_without_raising(tmp_path, monkeypatch, seeded_db):
    """Fail-soft by contract: a broken backup must never take down startup."""
    monkeypatch.setenv("PROCARE_BACKUP_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(backup.shutil, "copy2", _boom)

    res = backup.backup_now("test")

    assert res["ok"] is False
    assert "error" in res and res["reason"] == "test"


def _boom(*_a, **_k):
    raise OSError("disk full")
