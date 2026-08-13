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


def _procare_db_name() -> str | None:
    """Plain database name for native ``BACKUP DATABASE`` / ``msdb`` lookups.

    NOT ``engine.url.database``: ProCare builds its SQL Server URL as a raw
    ``odbc_connect`` string, which leaves SQLAlchemy's ``url.database`` empty.
    Reading it from there yields "" — enough to make BACKUP DATABASE fail and
    an msdb.backupset lookup silently match nothing.
    """
    from app.config import settings
    from app.db.base import engine

    return settings.procare_database_name() or (engine.url.database or None)


def _backup_dir() -> Path:
    """Where backups are written.

    ``PROCARE_BACKUP_DIR`` overrides the default — point it at the volume that
    already holds the pharmacy's backups (e.g. ``F:\\backup``). On SQL Server
    the path is resolved BY THE SERVER, so it must be writable by the SQL
    Server service account, not just by the ProCare process.
    """
    from app.db.base import engine

    override = os.environ.get("PROCARE_BACKUP_DIR")
    if override:
        d = Path(override)
        d.mkdir(parents=True, exist_ok=True)
        return d

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
        # A bare filename lands in the instance's default backup folder, which
        # last_backup_at() cannot see — set PROCARE_BACKUP_DIR to a path both
        # the server and ProCare can read so the throttle below works.
        dbname = _procare_db_name()
        if not dbname:
            return {"ok": False, "error": "no ProCare database name configured", "reason": reason}
        dest = f"procare-{stamp}.bak"
        if os.environ.get("PROCARE_BACKUP_DIR"):
            dest = str(_backup_dir() / dest)
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"BACKUP DATABASE [{dbname}] TO DISK = :d"), {"d": dest})
        return {"ok": True, "path": dest, "reason": reason}
    except Exception as e:  # noqa: BLE001 — fail-soft by contract
        log.exception("backup failed (%s)", reason)
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "reason": reason}


def last_backup_at() -> datetime | None:
    """When the newest backup was taken, or None if there is none.

    On SQL Server the authoritative record is ``msdb.dbo.backupset``, not the
    filesystem: a server-side ``BACKUP DATABASE`` writes to a path chosen by the
    SERVER, which ProCare often cannot see. Globbing a local folder therefore
    reported "no backup ever" on every call, so the throttle in
    ``backup_if_stale`` never engaged and a full backup ran on EVERY startup —
    minutes of blocked lifespan on a real pharmacy database.
    """
    from app.db.base import engine

    dbname = _procare_db_name()
    if engine.url.get_backend_name() != "sqlite" and dbname:
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT MAX(backup_finish_date) FROM msdb.dbo.backupset "
                        "WHERE database_name = :db AND type = 'D'"
                    ),
                    {"db": dbname},
                ).scalar()
            if row is not None:
                # backup_finish_date is server-local naive; treat as UTC-naive
                # for comparison against the UTC "now" used by backup_if_stale.
                return row if row.tzinfo else row.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001 — fall through to the file scan
            log.debug("msdb.backupset unreadable; falling back to file scan")

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
