"""Operations: database-size + disk-space health monitor.

SQL Server Express caps each database at 10 GB. The eStock mirror pulls tens of
thousands of products and hundreds of thousands of sale lines, and the
transaction log grows on top of that — so the DB can silently approach the cap
and one morning writes just start failing. This service measures:

  * the ProCare DB size (data + log) versus the cap, and
  * free disk space on the volume the DB / backups live on,

grades a severity, and feeds the hourly scheduled WhatsApp alert (80 / 90 / 95 %).
Everything is fail-soft: a monitoring error returns an ``error`` field, it never
raises into a request handler or the scheduler thread.

Scope note: from inside the backend container only the backend's own filesystem
and the DB *server* (over the connection) are visible. So disk space here is the
backend/backups volume; host-level ``df`` on the SQL Server data volume and OOM
detection are the shell watchdog's job (``deploy/procare-watchdog.sh``).
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.base import DATA_DIR, IS_SQLITE, engine

# SQL Server Express hard cap is 10 GB per database. Overridable for Standard/
# Enterprise editions or a differently-provisioned box via env.
DEFAULT_CAP_MB = float(os.environ.get("DB_SIZE_CAP_MB", "10240") or 10240)

_SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "critical": 3}

# Module state: the last severity we actually alerted on, so the hourly job
# notifies on an 80 → 90 → 95 escalation but does NOT re-send every hour while
# things sit at a steady level. Reset (ratcheted down) as conditions recover.
_last_alert_level = "ok"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate(
    db_mb: float,
    cap_mb: float,
    disk_free_pct: float | None,
    *,
    db_thresholds: tuple[float, float, float] = (80, 90, 95),
    disk_thresholds: tuple[float, float, float] = (20, 10, 5),
) -> dict:
    """Pure severity grader — no I/O, unit-testable on any platform/CI.

    ``db_thresholds`` = (info, warning, critical) as percent-of-cap.
    ``disk_thresholds`` = (info, warning, critical) as percent-free (lower is
    worse). Returns ``{"severity", "alerts": [str], "db_pct"}``.
    """
    alerts: list[str] = []
    severity = "ok"

    def _raise(level: str) -> None:
        nonlocal severity
        if _SEVERITY_ORDER[level] > _SEVERITY_ORDER[severity]:
            severity = level

    db_pct = round((db_mb / cap_mb) * 100, 1) if cap_mb else 0.0
    info_t, warn_t, crit_t = db_thresholds
    if db_pct >= crit_t:
        _raise("critical")
        alerts.append(f"حجم قاعدة البيانات وصل {db_pct}٪ من السعة القصوى — إجراء فوري مطلوب")
    elif db_pct >= warn_t:
        _raise("warning")
        alerts.append(f"حجم قاعدة البيانات {db_pct}٪ من السعة القصوى")
    elif db_pct >= info_t:
        _raise("info")
        alerts.append(f"حجم قاعدة البيانات {db_pct}٪ من السعة القصوى")

    if disk_free_pct is not None:
        d_info, d_warn, d_crit = disk_thresholds
        free = round(disk_free_pct, 1)
        if disk_free_pct < d_crit:
            _raise("critical")
            alerts.append(f"مساحة القرص الحرة {free}٪ فقط — خطر توقف الخدمة")
        elif disk_free_pct < d_warn:
            _raise("warning")
            alerts.append(f"مساحة القرص الحرة منخفضة: {free}٪")
        elif disk_free_pct < d_info:
            _raise("info")
            alerts.append(f"مساحة القرص الحرة: {free}٪")

    return {"severity": severity, "alerts": alerts, "db_pct": db_pct}


def database_size() -> dict:
    """Total DB size in MB, split data vs log. SQL Server reads
    ``sys.database_files`` (``size`` is in 8 KB pages); SQLite sums the file(s)
    on disk. Fail-soft — returns an ``error`` field instead of raising."""
    try:
        if IS_SQLITE:
            path = engine.url.database
            total = 0
            for suffix in ("", "-wal", "-shm"):
                f = f"{path}{suffix}"
                if path and os.path.exists(f):
                    total += os.path.getsize(f)
            mb = round(total / (1024 * 1024), 2)
            return {"engine": "sqlite", "data_mb": mb, "log_mb": 0.0, "total_mb": mb}
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT type_desc, SUM(size) * 8.0 / 1024 AS mb "
                    "FROM sys.database_files GROUP BY type_desc"
                )
            ).all()
        data_mb = log_mb = 0.0
        for type_desc, mb in rows:
            if str(type_desc).upper() == "LOG":
                log_mb += float(mb or 0)
            else:
                data_mb += float(mb or 0)
        return {
            "engine": "sqlserver",
            "data_mb": round(data_mb, 2),
            "log_mb": round(log_mb, 2),
            "total_mb": round(data_mb + log_mb, 2),
        }
    except Exception as exc:  # noqa: BLE001 — monitoring must never raise
        return {"engine": "unknown", "error": str(exc), "total_mb": None}


def _monitor_path() -> str:
    """The directory whose free space matters: the SQLite DB's folder, else the
    backend data/backups dir (where SQLite backups and app data live)."""
    if IS_SQLITE and engine.url.database:
        return os.path.dirname(engine.url.database) or "."
    return str(DATA_DIR)


def disk_usage(path: str | None = None) -> dict:
    """Free space on the volume holding the DB / backups. Fail-soft."""
    try:
        target = path or _monitor_path()
        usage = shutil.disk_usage(target)
        free_pct = round(usage.free / usage.total * 100, 1) if usage.total else 0.0
        return {
            "path": target,
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "free_pct": free_pct,
        }
    except Exception as exc:  # noqa: BLE001
        return {"path": path, "error": str(exc), "free_pct": None}


def ping() -> dict:
    """Cheap in-process liveness check: can we round-trip a query right now?
    Used by the scheduler's health self-ping (belt to the watchdog's suspenders)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        return {"ok": True, "engine": "sqlite" if IS_SQLITE else "sqlserver",
                "error": None, "checked_at": _now_iso()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "engine": "sqlite" if IS_SQLITE else "sqlserver",
                "error": str(exc), "checked_at": _now_iso()}


def check(cap_mb: float | None = None) -> dict:
    """Full health snapshot: DB size vs cap + disk free, graded to a severity."""
    cap = cap_mb if cap_mb is not None else DEFAULT_CAP_MB
    db = database_size()
    disk = disk_usage()
    total_mb = db.get("total_mb")
    graded = evaluate(total_mb or 0, cap, disk.get("free_pct"))
    db["cap_mb"] = cap
    db["pct_of_cap"] = graded["db_pct"]
    return {
        "severity": graded["severity"],
        "alerts": graded["alerts"],
        "db": db,
        "disk": disk,
        "checked_at": _now_iso(),
    }


def alert_if_worse(check_result: dict) -> bool:
    """Return True (advancing the remembered level) only when severity has RISEN
    since the last alert — so the hourly job fires on 80 → 90 → 95 transitions,
    not every hour at a steady state. Ratchets down silently as things recover so
    a later re-escalation alerts again."""
    global _last_alert_level
    sev = check_result.get("severity", "ok")
    cur = _SEVERITY_ORDER.get(sev, 0)
    last = _SEVERITY_ORDER.get(_last_alert_level, 0)
    if cur > last:
        _last_alert_level = sev
        return True
    if cur < last:
        _last_alert_level = sev  # recovered a notch — silent, but re-arm the alert
    return False
