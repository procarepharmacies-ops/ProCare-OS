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
from app.db.base import SessionLocal
from app.services import etl

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
    """True when a read-only eStock source is configured to sync from."""
    return settings.estock_sqlalchemy_url() is not None


def is_enabled() -> bool:
    """Sync runs when explicitly enabled (SYNC_ENABLED) AND a source exists."""
    flag = str(os.environ.get("SYNC_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")
    return flag and is_configured()


def run_once(source_engine=None) -> dict:
    """One sync cycle: mirror eStock → ProCare. Returns a result dict.

    ``source_engine`` lets tests pass a SQLite eStock-shaped source; in
    production it's built from the configured read-only eStock URL.
    """
    own_engine = False
    eng = source_engine
    if eng is None:
        url = settings.estock_sqlalchemy_url()
        if not url:
            with _lock:
                _state["last_status"] = "idle"
            return {"ran": False, "reason": "no eStock source configured"}
        eng = create_engine(url, echo=False)
        own_engine = True
    try:
        store_map = settings.estock_store_branch_map()
        with SessionLocal() as dst:
            counts = etl.mirror(eng, dst, store_map)
        with _lock:
            _state.update(
                runs=_state["runs"] + 1,
                last_run_at=datetime.now(timezone.utc).isoformat(),
                last_status="ok",
                last_counts=counts,
                last_error=None,
            )
        return {"ran": True, "counts": counts}
    except Exception as e:  # noqa: BLE001
        with _lock:
            _state.update(
                last_run_at=datetime.now(timezone.utc).isoformat(),
                last_status="error",
                last_error=f"{type(e).__name__}: {e}",
            )
        return {"ran": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if own_engine:
            eng.dispose()


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
    s["mode"] = "live read-only eStock mirror" if is_configured() else "offline (own seeded data)"
    return s
