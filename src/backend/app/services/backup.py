"""Database backups (نسخة احتياطية) — never lose pharmacy data again.

SQLite: copies the .db file (plus -wal/-shm safety checkpoint) into
``data/backups/procare-<UTC timestamp>.db``. SQL Server: issues
``BACKUP DATABASE ... TO DISK`` next to the server's default backup folder.

Triggered from three places:
- startup (throttled to once per 24h) — every day the pharmacy opens, a fresh
  backup exists before anything else happens;
- immediately BEFORE any full-wipe mirror run (throttled 6h) — the wipe is the
  single most destructive operation in the system;
- on demand: ``POST /api/backup`` (CEO).

Fail-soft: a failed backup logs + reports but never blocks the pharmacy.
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

log = logging.getLogger("procare.backup")

KEEP_LAST = 30  # pruned oldest-first beyond this many backups


def _backup_dir() -> Path:
    from app.db.base import engine

    if engine.url.get_backend_name() == "sqlite" and engine.url.database:
        base = Path(engine.url.database).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2] / "data"
    d = base / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune(d: Path) -> None:
    files = sorted(d.glob("procare-*"), key=lambda p: p.name)
    for old in files[:-KEEP_LAST]:
        try:
            old.unlink()
        except OSError:
            pass


def backup_now(reason: str = "manual") -> dict:
    """Take a backup right now. Returns {ok, path|error, reason}."""
    from app.db.base import engine

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        if engine.url.get_backend_name() == "sqlite":
            src = Path(engine.url.database).resolve()
            if not src.exists():
                return {"ok": False, "error": f"db file not found: {src}", "reason": reason}
            dest = _backup_dir() / f"procare-{stamp}.db"
            # Flush the WAL so the copied file is complete on its own.
            with engine.connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            shutil.copy2(src, dest)
            _prune(dest.parent)
            return {"ok": True, "path": str(dest), "reason": reason}
        # SQL Server: server-side native backup (path is ON THE SERVER).
        dbname = engine.url.database
        dest = f"procare-{stamp}.bak"
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"BACKUP DATABASE [{dbname}] TO DISK = :d"), {"d": dest})
        return {"ok": True, "path": dest, "reason": reason}
    except Exception as e:  # noqa: BLE001 — fail-soft by contract
        log.exception("backup failed (%s)", reason)
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "reason": reason}


def last_backup_at() -> datetime | None:
    files = sorted(_backup_dir().glob("procare-*"), key=lambda p: p.name)
    if not files:
        return None
    try:
        stamp = files[-1].stem.replace("procare-", "")
        return datetime.strptime(stamp, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def backup_if_stale(hours: float, reason: str) -> dict | None:
    """Backup only if the newest one is older than ``hours`` (throttle so the
    30-second sync loop can call this safely). None = fresh enough, skipped."""
    last = last_backup_at()
    if last is not None:
        age = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        if age < hours:
            return None
    return backup_now(reason)


def list_backups() -> list[dict]:
    out = []
    for p in sorted(_backup_dir().glob("procare-*"), key=lambda p: p.name, reverse=True):
        st = p.stat()
        out.append({"file": p.name, "size_mb": round(st.st_size / 1048576, 2)})
    return out
