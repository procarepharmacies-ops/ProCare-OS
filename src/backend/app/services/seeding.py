"""First-seed helpers: back up ProCare, then decide whether a full load is due.

Seeding ProCare on a branch server is a three-move sequence — back up what's
there, look at what's already mirrored, and only then run the (expensive) full
import. Getting the middle move wrong is what wastes an afternoon: the mirror's
incremental path in ``etl.mirror`` only engages once the branch ALREADY holds
sales, so on an empty branch every "quick sync" silently becomes a full load.
Operators can't see that from the outside, so this module reports it directly.

Everything here is fail-soft and read-only except :func:`backup`, which writes
one ``.bak`` file and never touches the eStock source.

CLI (from ``src/backend``)::

    python -m app.services.seeding --inspect
    python -m app.services.seeding --backup "F:\\backup\\ProCare_before_sync.bak"

``deploy/Seed-Elsanta.bat`` drives both.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.db import models as m
from app.db.base import IS_SQLITE, SessionLocal, engine

# Tables whose row counts tell an operator whether a mirror actually landed.
# Ordered the way the mirror fills them, so a partial-looking result reads
# top-to-bottom.
_COUNT_TABLES = (
    "products",
    "customers",
    "vendors",
    "employees",
    "stock_batches",
    "sales",
    "sale_lines",
    "purchases",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_readiness(sales_by_branch: dict[str, int], branch_code: str) -> dict:
    """Pure decision: does ``branch_code`` still need a full import?

    Split out from the I/O so the rule that actually drives the runbook is
    unit-testable on any platform. Mirrors the gate in ``etl.mirror``: a branch
    with **no** mirrored sales cannot sync incrementally — the ETL will run a
    full load whatever the caller asks for — so a fresh import is required.

    Returns ``{"needs_import", "sales", "reason"}``.
    """
    code = (branch_code or "").strip().upper()
    sales = int(sales_by_branch.get(code, 0) or 0)
    if sales > 0:
        return {
            "needs_import": False,
            "sales": sales,
            "reason": (
                f"{code} already holds {sales:,} mirrored "
                f"{'sale' if sales == 1 else 'sales'} — incremental sync will "
                "engage. Skip the full import."
            ),
        }
    return {
        "needs_import": True,
        "sales": 0,
        "reason": (
            f"{code} holds no mirrored sales. The ETL's incremental gate needs "
            "existing sales, so every cycle would run a FULL load — do the "
            "import once, deliberately."
        ),
    }


def inspect(branch_code: str = "ELSANTA") -> dict:
    """Row counts + per-branch sales + the import decision for ``branch_code``.

    Read-only. Never raises: a broken connection is reported as ``error`` so the
    batch driver can print it instead of dumping a traceback at the operator.
    """
    try:
        with SessionLocal() as s:
            counts: dict[str, int] = {}
            for table in _COUNT_TABLES:
                try:
                    counts[table] = int(
                        s.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                    )
                except Exception:  # noqa: BLE001 — table may predate a migration
                    counts[table] = -1

            sales_by_branch = {
                str(code): int(n or 0)
                for code, n in s.execute(
                    select(m.Branch.code, func.count(m.Sale.sale_id))
                    .select_from(m.Branch)
                    .outerjoin(m.Sale, m.Sale.branch_id == m.Branch.branch_id)
                    .group_by(m.Branch.code)
                ).all()
            }

        decision = evaluate_readiness(sales_by_branch, branch_code)
        return {
            "ok": True,
            "engine": "sqlite" if IS_SQLITE else "sqlserver",
            "branch": (branch_code or "").strip().upper(),
            "counts": counts,
            "sales_by_branch": sales_by_branch,
            "checked_at": _now_iso(),
            **decision,
        }
    except Exception as e:  # noqa: BLE001 — reported, never raised at an operator
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "checked_at": _now_iso()}


def backup(path: str) -> dict:
    """``BACKUP DATABASE`` ProCare to ``path``, then ``RESTORE VERIFYONLY`` it.

    A backup nobody verified is not a backup, so the verify is part of the same
    call — the caller gets one ``ok`` covering both. SQL Server only; on the
    SQLite dev database this is a no-op with a clear reason (copy the ``.db``
    file instead).

    ``BACKUP``/``RESTORE`` cannot run inside a transaction, hence AUTOCOMMIT.
    """
    if IS_SQLITE:
        return {
            "ok": False,
            "skipped": True,
            "reason": "ProCare is on SQLite (dev). Copy the .db file to back it up.",
        }
    if not (path or "").strip():
        return {"ok": False, "reason": "No backup path given."}

    try:
        # BACKUP DATABASE is not allowed inside a transaction.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            db_name = conn.execute(text("SELECT DB_NAME()")).scalar()
            # The path is an operator-supplied local filename, not user input from
            # a request; it still goes through a bound parameter on the VERIFY and
            # is quote-escaped on the BACKUP (T-SQL takes no parameter there).
            safe = str(path).replace("'", "''")
            conn.execute(text(f"BACKUP DATABASE [{db_name}] TO DISK = N'{safe}' WITH INIT"))
            conn.execute(text(f"RESTORE VERIFYONLY FROM DISK = N'{safe}'"))
        return {
            "ok": True,
            "database": db_name,
            "path": path,
            "verified": True,
            "backed_up_at": _now_iso(),
        }
    except Exception as e:  # noqa: BLE001 — reported so the .bat can stop cleanly
        return {"ok": False, "path": path, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    import json

    arg = sys.argv[1] if len(sys.argv) > 1 else "--inspect"
    if arg == "--backup":
        out = backup(sys.argv[2] if len(sys.argv) > 2 else "")
    elif arg == "--inspect":
        out = inspect(sys.argv[2] if len(sys.argv) > 2 else "ELSANTA")
    else:
        out = {"ok": False, "reason": "usage: --inspect [BRANCH] | --backup <path>"}

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    # Exit code drives deploy/Seed-Elsanta.bat, which cannot parse JSON:
    #   0 = ok, nothing further needed   1 = failed   2 = ok, a full import is due
    # (`if errorlevel N` in batch means ">= N", so 2 must outrank 1.)
    if not out.get("ok"):
        sys.exit(1)
    sys.exit(2 if out.get("needs_import") else 0)
