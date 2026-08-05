"""Continuous eStock → ProCare sync (near-real-time mirror).

Keeps ProCare's own database in step with the live eStock source by running the
read-only mirror (``app.services.etl``) on a short interval. It activates only
when a read-only eStock login is configured; otherwise the system stays on its
own seeded data and the sync reports "idle".

  * Runs in a background daemon thread started from the FastAPI lifespan, so it
    never blocks request handling. Each cycle uses its own DB session.
  * ``SYNC_INTERVAL_SECONDS`` (env, default 30) controls cadence — set it low for
    a near-instant demo. The mirror is idempotent (full refresh) and applies all
    the data-quality rules; for very large live datasets a watermark/CDC
    incremental is the documented production upgrade (docs/06).
  * GUARDRAIL preserved: the source is opened read-only; ProCare never writes to
    eStock.

The work unit, ``run_once``, is decoupled from the thread so it can be tested
directly against a SQLite eStock-shaped source (see tests/test_sync.py).
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine

from app.config import settings
from app.db import models as m
from app.db.base import SessionLocal
from app.services import etl


def _record_cycle(source_name: str, mode: str) -> None:
    """Persist the cycle outcome so the incremental gate survives restarts.

    Fail-soft: bookkeeping must never fail a cycle that already mirrored fine.
    """
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with SessionLocal() as st:
            row = st.get(m.SyncState, source_name)
            if row is None:
                row = m.SyncState(source_name=source_name)
                st.add(row)
            if not mode.startswith("incremental"):
                row.full_synced_at = now
            row.last_cycle_at = now
            row.last_mode = mode or None
            st.commit()
    except Exception:  # noqa: BLE001
        pass

_DEFAULT_INTERVAL = 30

_state: dict = {
    "enabled": False,
    "running": False,
    "interval_seconds": _DEFAULT_INTERVAL,
    "runs": 0,
    "last_run_at": None,
    "last_status": "idle",
    "last_counts": None,
    "last_error": None,
}
_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()


def interval_seconds() -> int:
    try:
        return max(2, int(os.environ.get("SYNC_INTERVAL_SECONDS", _DEFAULT_INTERVAL)))
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL


def is_configured() -> bool:
    """True when at least one eStock source is configured to sync from."""
    return bool(settings.estock_sources())


def incremental_days() -> int:
    """Trailing re-pull window (days) for the incremental sync. Once a branch
    is filled, each cycle re-pulls only this window instead of all history —
    what makes a short cadence viable over the flaky Elsanta WAN and keeps
    SQL Server write transactions small. 0 disables (always full reload)."""
    try:
        return max(0, int(os.environ.get("SYNC_INCREMENTAL_DAYS", "7")))
    except (TypeError, ValueError):
        return 7


def is_enabled() -> bool:
    """Sync runs when explicitly enabled (SYNC_ENABLED) AND a source exists."""
    flag = str(os.environ.get("SYNC_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")
    return flag and is_configured()


def run_once(source_engine=None) -> dict:
    """One sync cycle: mirror EVERY configured eStock source → ProCare.

    Each source (one per branch server — e.g. Elsanta live + Mashala live)
    refreshes ONLY its own branches (``etl.mirror(branch_scoped=True)``), so the
    sources never wipe each other and imported branch history survives every
    cycle. One source failing (e.g. a LAN drop to one branch) does not block the
    others — its error is recorded and the cycle continues.

    ``source_engine`` lets tests pass a SQLite eStock-shaped source; in
    production engines are built from the configured source URLs.
    """
    if source_engine is not None:
        sources = [
            {
                "name": "source",
                "engine": source_engine,
                "store_branch_map": settings.estock_store_branch_map(),
                "own": False,
            }
        ]
    else:
        blocks = settings.estock_sources()
        if not blocks:
            with _lock:
                _state["last_status"] = "idle"
            return {"ran": False, "reason": "no eStock source configured"}
        sources = [
            {
                "name": b["name"],
                "engine": create_engine(b["url"], echo=False),
                "store_branch_map": b["store_branch_map"],
                "own": True,
            }
            for b in blocks
        ]

    all_counts: dict[str, dict] = {}
    errors: dict[str, str] = {}
    try:
        for s in sources:
            try:
                # Incremental only after this source has completed a FULL load
                # (recorded in sync_state) — a fresh/reset database, or demo
                # data sitting in the branch, must never suppress the initial
                # history pull.
                with SessionLocal() as st:
                    state = st.get(m.SyncState, s["name"])
                    inc = incremental_days() if (state and state.full_synced_at) else 0
                with SessionLocal() as dst:
                    counts = etl.mirror(
                        s["engine"], dst, s["store_branch_map"], branch_scoped=True,
                        incremental_days=inc or None,
                    )
                all_counts[s["name"]] = counts
                _record_cycle(s["name"], counts.get("sync_mode", ""))
            except Exception as e:  # noqa: BLE001 — soft-fail per source
                errors[s["name"]] = f"{type(e).__name__}: {e}"
        ok = not errors
        with _lock:
            _state.update(
                runs=_state["runs"] + 1,
                last_run_at=datetime.now(timezone.utc).isoformat(),
                last_status="ok" if ok else ("error" if not all_counts else "partial"),
                last_counts=all_counts or None,
                last_error="; ".join(f"{k}: {v}" for k, v in errors.items()) or None,
            )
        if all_counts:
            return {"ran": True, "counts": all_counts, **({"errors": errors} if errors else {})}
        return {"ran": False, "errors": errors}
    finally:
        for s in sources:
            if s["own"]:
                s["engine"].dispose()


def _loop() -> None:
    # First sync immediately, then every interval until stopped.
    while not _stop.is_set():
        run_once()
        _stop.wait(interval_seconds())


def start() -> dict:
    """Start the background sync thread if enabled and not already running."""
    global _thread
    if not is_enabled():
        with _lock:
            _state["enabled"] = False
        return {"started": False, "reason": "sync disabled or no eStock source"}
    with _lock:
        if _thread is not None and _thread.is_alive():
            return {"started": False, "reason": "already running"}
        _stop.clear()
        _state["enabled"] = True
        _state["running"] = True
        _state["interval_seconds"] = interval_seconds()
        _thread = threading.Thread(target=_loop, name="procare-sync", daemon=True)
        _thread.start()
    return {"started": True, "interval_seconds": interval_seconds()}


def stop() -> None:
    _stop.set()
    with _lock:
        _state["running"] = False


def status() -> dict:
    """Current sync status (safe to serialise; no secrets)."""
    with _lock:
        s = dict(_state)
    s["configured"] = is_configured()
    s["interval_seconds"] = interval_seconds()
    s["incremental_days"] = incremental_days()
    s["mode"] = "live read-only eStock mirror" if is_configured() else "offline (own seeded data)"
    return s
