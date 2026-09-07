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
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.config import settings
from app.db import models as m
from app.db.base import IS_MSSQL, SessionLocal, engine
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
            # The cycle committed, so the mirror is whole again.
            row.cycle_started_at = None
            row.cycle_mode = None
            st.commit()
    except Exception:  # noqa: BLE001
        pass

def _mark_cycle_start(source_name: str, mode: str) -> None:
    """Record — durably, before the mirror is touched — that a cycle is running.

    etl.mirror() wipes the branch's rows and reloads them, but the loaders commit
    per chunk (SQL Server 2008 kills one gigantic transaction), so the wipe
    becomes durable long before the reload finishes. Kill the process in between
    and the mirror is left PARTIAL while every bookkeeping field still says the
    last full load succeeded — the dashboard then reports 0 sales as if it were
    fact. This marker is what tells the next cycle, and /api/sync/status, that
    the numbers cannot be trusted yet.
    """
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with SessionLocal() as st:
            row = st.get(m.SyncState, source_name)
            if row is None:
                row = m.SyncState(source_name=source_name)
                st.add(row)
            row.cycle_started_at = now
            row.cycle_mode = mode
            st.commit()
    except Exception:  # noqa: BLE001 — never let bookkeeping block a sync
        pass


def interrupted_sources() -> list[str]:
    """Sources whose last cycle never committed, so their mirror is partial."""
    try:
        with SessionLocal() as st:
            return [
                r.source_name
                for r in st.query(m.SyncState).filter(m.SyncState.cycle_started_at.isnot(None)).all()
            ]
    except Exception:  # noqa: BLE001
        return []


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
# True only while this process is actually inside a mirror cycle. The durable
# cycle_started_at marker is set during a HEALTHY run too, so this is what tells
# "a cycle is writing right now" apart from "a cycle died while writing".
_cycle_active = False


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


# --- Cross-process cycle guard -----------------------------------------------
#
# INC-2026-0829-B: the in-process ``threading.Lock`` below guards only the
# _state dict. It cannot see a SECOND PROCESS running a cycle -- and several do:
# the backend's own 5-minute thread, the 03:00 ProCare_RawMirror_OffpeakFill
# task, ``.local-run/sync_offpeak.py``, and any ad-hoc ``sync.run_once()`` an
# operator starts by hand. Two cycles against the same branch interleave
# ``_wipe_branch_sales_window()`` with another cycle's ``_load_sales()``, which
# both corrupts the load (FK violation on a parent row the other cycle just
# deleted) and, as seen on 2026-08-29, leaves them blocking each other on
# gl_accounts/estock_raw_watermark until someone kills a session by hand --
# 3h40m with no sync and no error reported.
#
# A SQL Server APPLICATION LOCK is visible to every process on the instance, so
# it is the guard that actually holds. ``@LockOwner='Session'`` (not the default
# 'Transaction') is required: a cycle commits many times, and a transaction-owned
# lock would be released at the first commit.
_APPLOCK_NAME = "ProCare_SyncCycle"


def applock_timeout_ms() -> int:
    """How long a cycle waits for the guard before giving up. 0 = skip at once,
    which is what the background loop wants: the next tick is only minutes away,
    so queueing cycles up behind each other only deepens the pile."""
    try:
        return max(0, int(os.environ.get("SYNC_APPLOCK_TIMEOUT_MS", "0")))
    except (TypeError, ValueError):
        return 0


def lock_timeout_ms() -> int:
    """SQL Server LOCK_TIMEOUT for the cycle's own connections (-1 = wait for
    ever, the SQL Server default and what hung the mirror). A bounded wait turns
    'blocked until a human notices' into a recorded, retried failure."""
    try:
        return int(os.environ.get("SYNC_LOCK_TIMEOUT_MS", "120000"))
    except (TypeError, ValueError):
        return 120000


@contextmanager
def _cycle_guard():
    """Hold the instance-wide sync guard for one cycle.

    Yields True when this process owns the cycle, False when another process is
    already running one (caller must then skip). A no-op that always yields True
    off SQL Server (SQLite dev/test is single-process by construction).
    """
    if not IS_MSSQL:
        yield True
        return
    conn = None
    acquired = False
    try:
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        rc = conn.exec_driver_sql(
            "DECLARE @rc int; "
            "EXEC @rc = sp_getapplock @Resource=?, @LockMode='Exclusive', "
            "@LockOwner='Session', @LockTimeout=?; SELECT @rc",
            (_APPLOCK_NAME, applock_timeout_ms()),
        ).scalar()
        acquired = rc is not None and int(rc) >= 0
        yield acquired
    except Exception:  # noqa: BLE001 — the guard must never be the thing that fails a cycle
        # Could not reach the guard at all: fall back to running, since refusing
        # to sync is worse than the race the guard protects against.
        yield True
    finally:
        if conn is not None:
            try:
                if acquired:
                    conn.exec_driver_sql(
                        "EXEC sp_releaseapplock @Resource=?, @LockOwner='Session'",
                        (_APPLOCK_NAME,),
                    )
            except Exception:  # noqa: BLE001
                pass
            try:
                conn.close()  # closing the session releases the lock regardless
            except Exception:  # noqa: BLE001
                pass


def _apply_lock_timeout(session) -> None:
    """Bound how long this cycle's writes wait on someone else's lock."""
    if not IS_MSSQL:
        return
    try:
        session.execute(text(f"SET LOCK_TIMEOUT {lock_timeout_ms()}"))
    except Exception:  # noqa: BLE001
        pass


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
                "sync_mode": b.get("sync_mode"),
                "own": True,
            }
            for b in blocks
        ]

    global _cycle_active
    all_counts: dict[str, dict] = {}
    errors: dict[str, str] = {}
    try:
        with _cycle_guard() as owned:
            if not owned:
                # Another process (offpeak fill, a hand-started run_once, a second
                # backend) is mid-cycle. Skipping is correct: cycles are idempotent
                # and the next tick is minutes away.
                with _lock:
                    _state["last_status"] = "skipped (another sync cycle is running)"
                return {"ran": False, "reason": "another sync cycle is already running"}
            for s in sources:
                try:
                    # Customers-only source: its operational data already arrives
                    # from the main server, so only the customer register is pulled.
                    if s.get("sync_mode") == "customers_only":
                        counts = etl.sync_customers_only(s["engine"])
                    else:
                        # Incremental only after this source has completed a FULL load
                        # (recorded in sync_state) — a fresh/reset database, or demo
                        # data sitting in the branch, must never suppress the initial
                        # history pull.
                        with SessionLocal() as st:
                            state = st.get(m.SyncState, s["name"])
                            # An interrupted FULL load wiped history it never
                            # finished restoring. full_synced_at still points at
                            # the earlier good run, so the plain gate would go
                            # incremental and repair only the last few days —
                            # leaving the older history missing for good. Force
                            # a full re-load until one actually completes.
                            broken_full = bool(
                                state
                                and state.cycle_started_at is not None
                                and not (state.cycle_mode or "").startswith("incremental")
                            )
                            inc = (
                                incremental_days()
                                if (state and state.full_synced_at and not broken_full)
                                else 0
                            )
                        _mark_cycle_start(
                            s["name"], f"incremental({inc}d)" if inc else "full"
                        )
                        _cycle_active = True
                        try:
                            with SessionLocal() as dst:
                                _apply_lock_timeout(dst)
                                counts = etl.mirror(
                                    s["engine"], dst, s["store_branch_map"], branch_scoped=True,
                                    incremental_days=inc or None,
                                )
                        finally:
                            _cycle_active = False
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
    #
    # run_once() soft-fails PER SOURCE, but anything raised OUTSIDE that inner
    # try (settings lookup, create_engine, a MemoryError) used to escape here and
    # kill this thread outright -- while _state["running"] stayed True for ever.
    # The mirror then silently stopped with status "ok" and no error, which is
    # exactly how a 3h40m outage went unnoticed on 2026-08-29. Never let the loop
    # die: record the failure, keep the cadence.
    while not _stop.is_set():
        try:
            run_once()
        except BaseException as e:  # noqa: BLE001 — a dead sync thread is worse
            with _lock:
                _state.update(
                    last_status="error",
                    last_error=f"sync loop: {type(e).__name__}: {e}",
                )
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
    """Current sync status (safe to serialise; no secrets).

    ``running`` used to be a flag set once at start() and never revisited, so a
    thread that had died or been blocked in SQL Server for hours still reported
    ``running: true, last_status: "ok"``. It now reflects the actual thread, and
    ``stalled`` / ``seconds_since_last_run`` make a wedged cycle visible without
    anyone having to compare timestamps by hand.
    """
    with _lock:
        s = dict(_state)
    alive = _thread is not None and _thread.is_alive()
    s["thread_alive"] = alive
    s["running"] = bool(s.get("running")) and alive
    s["configured"] = is_configured()
    s["interval_seconds"] = interval_seconds()
    s["incremental_days"] = incremental_days()
    s["mode"] = "live read-only eStock mirror" if is_configured() else "offline (own seeded data)"

    age = None
    last = s.get("last_run_at")
    if last:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        except (TypeError, ValueError):
            age = None
    s["seconds_since_last_run"] = None if age is None else round(age)
    # A cycle legitimately takes a while; three missed intervals is not a slow
    # cycle, it is a wedged one.
    s["stalled"] = bool(s["enabled"] and age is not None and age > max(600, 3 * interval_seconds()))
    if s["stalled"] and s.get("last_status") == "ok":
        s["last_status"] = "stalled"

    # A cycle that died between the wipe and its commit leaves the mirror
    # partial. Surfacing it matters more than any other field here: every other
    # field would happily report "ok" while the dashboard shows a day's sales as
    # zero. Suppressed while a cycle is genuinely in flight, since the marker is
    # set for the whole of a healthy run too.
    partial = [] if _cycle_active else interrupted_sources()
    s["mirror_partial"] = bool(partial)
    s["mirror_partial_sources"] = partial or None
    if partial and s.get("last_status") in ("ok", "idle"):
        s["last_status"] = "partial mirror (interrupted cycle; rebuilding)"
    return s
