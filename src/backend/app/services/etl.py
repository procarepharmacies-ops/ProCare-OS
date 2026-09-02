"""Read-only eStock → ProCare mirror ETL (Phase 1).

Reads the live eStock SQL Server (``stock`` on 192.168.1.2) through a dedicated
READ-ONLY login and writes the *cleaned* rows into ProCare's own database,
applying every data-quality rule in ``docs/05-data-quality-and-fixes.md``:

  * ``sale_date = COALESCE(bill_date, insert_date)``  (eStock bill_date is often NULL)
  * returns flagged via ``back = 'Y'``  → ``is_return`` (kept, excluded from metrics)
  * eStock char(1) 'Y'/'N' flags → real BIT/bool
  * walk-in ``customer_id = 0`` → NULL

GUARDRAIL: ProCare NEVER writes to eStock. The source engine is opened read-only
and only SELECTed. The live mirror activates only when a real read-only login is
present in ``config/connections.json:estock_source``; otherwise the system runs
on its own seeded data (``app.db.seed``) so the stack is demonstrable offline.

Design notes
------------
* Column-resilient: the eStock column names are fixed by the 2026-06-23 audit
  (docs/02), but to tolerate minor variance across eStock builds the extractor
  introspects each source table and picks the first present candidate column.
  Tables/columns that genuinely aren't there are skipped, not invented.
* Dialect-agnostic: extraction is plain ``SELECT`` via SQLAlchemy ``text()`` so
  the exact same code runs against SQL Server (prod) and a SQLite eStock-shaped
  source (tests) — which is how the transformation is proven correct.
* ``store_id → branch_id`` mapping is operator config (eStock branch IDs are the
  one genuine per-site unknown the audit flags as TBD); a sensible default and a
  safe fallback to the first branch keep it runnable.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, create_engine, delete, func, insert, inspect, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.db.base import Base, SessionLocal, engine
from app.db.models import EstockRawMirror, EstockRawWatermark

# SQL Server 2008 hard-caps a single statement at 2100 parameters. A naive
# bulk insert of N rows x ~10 cols blows past that and the server TERMINATES
# the connection (pyodbc HY000 "Unspecified error... connection terminated"),
# which poisons the shared pool and takes the whole backend down. Chunk every
# bulk path well under the limit (200 rows x <=10 cols ~= 2000 params).
_BULK_CHUNK = 200


def _bulk_add(dst: Session, objs: list) -> None:
    """Chunked ORM bulk insert that stays inside SQL Server's 2100-param limit
    AND bounds transaction size — SQL Server 2008 kills one gigantic transaction
    ('08S01' connection drop), so we commit every chunk."""
    for i in range(0, len(objs), _BULK_CHUNK):
        dst.add_all(objs[i : i + _BULK_CHUNK])
        dst.flush()
        dst.commit()


def _bulk_insert(dst: Session, table, rows: list) -> None:
    """Chunked Core multi-row INSERT (same 2100-param + transaction-size rationale)."""
    if not rows:
        return
    for i in range(0, len(rows), _BULK_CHUNK):
        dst.execute(insert(table), rows[i : i + _BULK_CHUNK])
        dst.commit()

# eStock source table -> ProCare destination, with the cleaning rule applied.
# (Row counts are from the 2026-06-23 audit; see docs/02 and docs/06.)
MIRROR_PLAN = [
    ("Products (53,474)", "products", "bilingual names; product_drug->is_controlled; has_expire->has_expiry"),
    ("Customer (1,197)", "customers", "credit_limit, current_balance kept; limit enforced at POS"),
    ("Vendor (87)", "vendors", "balances kept"),
    ("Product_Amount (35,404)", "stock_batches", "per-batch stock; store_id->branch_id; FEFO by exp_date"),
    ("Sales_header (95,088)", "sales", "sale_date = COALESCE(bill_date, insert_date); back='Y' -> is_return"),
    ("Sales_details (183,906)", "sale_lines", "buy_price snapshot kept for profit"),
    ("Back_sales_header/details (4,359/4,212)", "sales/sale_lines", "is_return = 1"),
    ("Purchase_header/details (685/9,230)", "purchases/purchase_lines", "bonus + exp_date carried"),
]

# Tables not yet mirrored: their eStock column shapes (52-col Branches, the
# Gedo_* ledgers, Branch_order_* / Branch_money_*) are not fixed by the audit and
# are confirmed during the mirror phase — see docs/02 "What is still TBD".
DEFERRED_PLAN = [
    ("Gedo_* ledgers (93,925/88,359/2,878/9,271)", "ledger_entries", "column audit pending"),
    ("Branch_order_* (8,204/61,872)", "stock_transfers/_lines", "column audit pending"),
    ("Branch_money_* (1,102/1,098)", "cash_transfers", "column audit pending"),
]

# Every eStock SOURCE table this ETL reads (keep in sync with the _load_* funcs
# below). Used by tools/estock_schema_dump.py to report the coverage gap — which
# live eStock tables ProCare does NOT yet mirror. NB: this is the count that
# matters for "how much of eStock do we cover", not ProCare's own table count.
COVERED_SOURCE_TABLES = frozenset({
    "Products", "Customer", "Vendor", "Employee", "Jobs", "Product_Amount", "Branches_Product_Amount",
    "Sales_header", "Sales_details", "Branches_sales_header", "Branches_sales_details",
    "Back_sales_header", "Back_Sales_details", "Branches_back_sales_header", "Branches_back_sales_details",
    "Purchase_header", "Purchase_details", "Branches_purchase_header", "Branches_purchase_details",
    "Cash_depots", "Cash_disk_close", "Branches_Cash_disk_close",
    "Branch_order_header", "Branch_order_details",
    "Account_Tree", "Gedo_Financial", "Tuning_accounts",
    "Gedo_customers", "Gedo_Vendors", "Gedo_branches", "Gedo_employee", "Gedo_installment",
    "company_Owner", "Gedo_Dividends_paied",
    "Employee_salary", "Employee_cash_advance",
})


# Destination tables cleared (children first) before a full load. Branches and
# the reference/lookup seeds are kept; the mirror fills operational data.
_WIPE_ORDER = [
    m.LoyaltyTransaction,  # references sales + customers — must go first
    m.SaleLine, m.Sale, m.PurchaseLine, m.Purchase, m.StockMovement,
    m.StockTransferLine, m.StockTransfer, m.CashTransfer if hasattr(m, "CashTransfer") else None,
    m.OpeningStockLine if hasattr(m, "OpeningStockLine") else None,
    m.OpeningStock if hasattr(m, "OpeningStock") else None,
    m.StockAdjustment if hasattr(m, "StockAdjustment") else None,
    # ProductChange references products — must be cleared before Product.
    m.ProductChange if hasattr(m, "ProductChange") else None,
    # So do the derived/analytics tables. Leaving them out made a full wipe fail
    # with "FOREIGN KEY constraint failed ... DELETE FROM products" on any
    # database that had ever produced a decision card or a forecast — every
    # model carrying an FK to products has to be listed here, not just the
    # transactional ones.
    m.DecisionCard if hasattr(m, "DecisionCard") else None,
    m.Forecast if hasattr(m, "Forecast") else None,
    m.ProductAffinity if hasattr(m, "ProductAffinity") else None,
    m.IncentiveLedger if hasattr(m, "IncentiveLedger") else None,
    m.ShortageItem if hasattr(m, "ShortageItem") else None,
    m.BranchOrderLine if hasattr(m, "BranchOrderLine") else None,
    m.LedgerEntry, m.PurchaseOrderDraft, m.StockBatch, m.Product, m.Customer, m.Vendor,
]


def is_available() -> bool:
    """True only when a real read-only eStock login is configured."""
    return settings.estock_sqlalchemy_url() is not None


def status() -> dict:
    """Report whether the live mirror can run, and the planned table mappings."""
    available = is_available()
    return {
        "estock_source_configured": available,
        "mode": "live read-only mirror" if available else "offline (running on ProCare's own seeded data)",
        "guardrail": "ProCare NEVER writes to eStock — read-only ETL only.",
        "data_quality_rules": [
            "sale_date = COALESCE(bill_date, insert_date)",
            "exclude returns (back <> 'Y')",
            "available stock = amount > 0 AND not expired",
            "FEFO = ORDER BY exp_date ASC",
        ],
        "mirror_plan": [{"source": s, "destination": d, "rule": r} for s, d, r in MIRROR_PLAN],
        "deferred_pending_column_audit": [
            {"source": s, "destination": d, "note": r} for s, d, r in DEFERRED_PLAN
        ],
        "tbd": [
            "read-only eStock login name/permissions",
            "store_id -> branch_id map (estock_source.store_branch_map)",
            "incremental-sync watermark column for delta loads",
            "Titan/Drug-Eye schema at D:\\Labirdo",
        ],
    }


# --- extraction helpers -----------------------------------------------------
def _pick(cols: set[str], *candidates: str) -> str | None:
    """First candidate column present (case-insensitive) — returns the
    column's REAL casing from ``cols``, not the candidate as typed.

    SQL Server preserves declared casing, and row-mapping ``.get()`` lookups
    are case-SENSITIVE, so returning the candidate verbatim silently breaks
    every downstream ``r.get(picked)`` when the source's actual casing
    differs (confirmed on the Elsanta schema dump: ``Gedo_employee.flag`` is
    lowercase while every sibling Gedo_* table uses ``Flag``)."""
    by_lower = {c.lower(): c for c in cols}
    for cand in candidates:
        real = by_lower.get(cand.lower())
        if real is not None:
            return real
    return None


def _b(value) -> bool:
    """eStock char(1) 'Y'/'N' (or 1/0/'1') -> bool."""
    if value is None:
        return False
    s = str(value).strip().upper()
    return s in ("Y", "1", "TRUE", "T")


def _product_deleted(value) -> bool:
    """eStock ``Products.deleted`` is INVERTED relative to its name.

    Audited on both live branch DBs (2026-07): the ~53,400 products that sell
    every day carry ``deleted='1'`` and the ~90 truly removed ones carry
    ``deleted='0'`` (paired with ``active=0``, zero sales). Mirroring the flag
    literally marked 99.7%% of the catalogue deleted, which hid it from POS,
    inventory, prescriptions and the clinical layer. ``Customer.deleted`` has
    normal semantics — this helper is for Products ONLY. 'Y' (the audit's
    original Y/N reading) is still honoured as deleted in case an eStock
    install uses that convention.
    """
    if value is None:
        return False
    return str(value).strip().upper() in ("0", "Y")


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # SQLite returns ISO strings.
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _as_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _int_or_none(value) -> int | None:
    """Coerce a source key to int, or None when it is missing/not a number."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str(value) -> str | None:
    """Coerce a raw eStock source value to a SQLite-safe string.

    pyodbc hands back some columns (e.g. ``product_unit1`` -> unit_big/unit_small,
    which ProCare stores as ``String``) as ``decimal.Decimal``. SQLAlchemy's
    SQLite dialect cannot bind a ``Decimal`` into a text column, so the whole
    products load aborts with ``type 'decimal.Decimal' is not supported`` — even
    though SQL Server (prod) binds it natively and never trips this. Stringifying
    here keeps the unit name intact and makes the mirror dialect-agnostic.
    """
    if value is None:
        return None
    return str(value)


def _price(value) -> float:
    """A price/amount sanitised to be non-negative. eStock's product master
    carries dirty rows (e.g. buy_price = -57.2) that violate ProCare's
    CK_products_prices constraint and would abort the whole atomic product load
    — clamp them to 0 so one bad row never blocks the mirror."""
    return max(0.0, _num(value))


def _ar(raw_ar, raw_en=None, placeholder: str = "بدون اسم") -> str:
    """Arabic display name: the source Arabic value, else the English name, else
    a clear Arabic placeholder. Never a bare ``"?"`` — that reads on screen as a
    font/encoding failure rather than what it actually is (a missing name)."""
    if raw_ar is not None and str(raw_ar).strip():
        return str(raw_ar).strip()
    if raw_en is not None and str(raw_en).strip():
        return str(raw_en).strip()
    return placeholder


# --- flaky-WAN resilience ----------------------------------------------------
# The Elsanta source is reached over a WAN that drops long-lived connections
# (pyodbc 10054 / 08S01 "Communication link failure" at ~6 minutes). Two
# defences make the mirror survive it:
#   1. `_ResilientSource` retries any SELECT whose connection died, on a FRESH
#      connection (the old pool is disposed — a dead pooled socket must never be
#      handed out again).
#   2. `_iter_rows` pages the huge tables (Sales_details is 313K rows on
#      Elsanta) by key range so each query finishes well before the WAN drops
#      it, instead of one giant SELECT that can never complete.
# Retrying is safe: the source is only ever SELECTed, and a re-fetched chunk is
# transformed/inserted only after the fetch fully succeeds.

_CHUNK_ROWS = int(os.environ.get("SYNC_CHUNK_ROWS", "20000") or 20000)
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2.0

_COMM_MARKERS = (
    "10054",            # WSAECONNRESET — connection forcibly closed
    "10060",            # WSAETIMEDOUT
    "08s01",            # ODBC communication-link-failure SQLSTATE
    "communication link failure",
    "forcibly closed",
    "connection reset",
    "tcp provider",
    "semaphore timeout",
)


def _is_comm_error(exc: BaseException) -> bool:
    """True when the exception looks like a dropped network connection (the
    retryable class), as opposed to a real SQL/data error (never retried)."""
    msg = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in msg for marker in _COMM_MARKERS)


class _ResilientSource:
    """A read-only source connection that survives WAN drops.

    ``execute`` fetches the ENTIRE result inside the retry boundary (via
    ``Result.freeze``) — with pyodbc the 10054 typically fires mid-``fetchall``,
    not at ``execute`` time, so a lazy result would escape the retry. On a
    communication failure the whole engine pool is disposed and the statement
    re-runs on a brand-new connection, with linear backoff. Non-network errors
    propagate immediately.
    """

    def __init__(self, engine):
        self._engine = engine
        self._conn = engine.connect()

    def execute(self, statement, parameters=None):
        attempts = _RETRY_ATTEMPTS
        for attempt in range(1, attempts + 1):
            try:
                result = self._conn.execute(statement, parameters or {})
                return result.freeze()()  # fully fetched; re-iterable
            except Exception as e:  # noqa: BLE001 — classified below
                if not _is_comm_error(e) or attempt == attempts:
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                self._reconnect()
        raise RuntimeError("unreachable")  # pragma: no cover

    def _reconnect(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001 — the socket is already dead
            pass
        self._engine.dispose()  # drop every pooled (possibly dead) connection
        self._conn = self._engine.connect()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass


def _iter_rows(src, tbl: str, key: str | None, bounds: tuple[int, int] | None = None):
    """Yield ``tbl``'s rows as mapping-lists, one key-range chunk at a time.

    Paging by ``WHERE key BETWEEN lo AND hi`` (not OFFSET) keeps each query
    cheap and single-pass on the source. Without a usable integer key the whole
    table is fetched in one (retried) query — correct, just not chunked.
    ``bounds`` restricts the scan to a known (lo, hi) key range — the
    incremental cycle uses it to fetch only the window's detail rows.
    """
    if key is None:
        yield src.execute(text(f"SELECT * FROM {tbl}")).mappings().all()
        return
    if bounds is not None:
        lo, hi = bounds
    else:
        lo, hi = src.execute(text(f"SELECT MIN({key}), MAX({key}) FROM {tbl}")).one()
    if lo is None or hi is None:
        return  # empty table
    try:
        lo, hi = int(lo), int(hi)
    except (TypeError, ValueError):
        yield src.execute(text(f"SELECT * FROM {tbl}")).mappings().all()
        return
    chunk = max(1, _CHUNK_ROWS)
    for start in range(lo, hi + 1, chunk):
        rows = src.execute(
            text(f"SELECT * FROM {tbl} WHERE {key} BETWEEN :lo AND :hi"),
            {"lo": start, "hi": min(start + chunk - 1, hi)},
        ).mappings().all()
        if rows:
            yield rows


# --- the mirror core (testable: pass an explicit source + dest) -------------
def mirror(
    source_engine,
    dst: Session,
    store_branch_map: dict | None = None,
    *,
    wipe: bool = True,
    branch_scoped: bool = False,
    force_branch_code: str | None = None,
    dedup: bool | None = None,
    incremental_days: int | None = None,
) -> dict:
    """Run the read-only mirror from ``source_engine`` into ProCare (``dst``).

    Default (``wipe=True``): a full refresh — clears ProCare's operational and
    catalogue tables, then reloads from a single eStock source. This is the
    Phase-1 live mirror behaviour.

    Multi-source sync (``branch_scoped=True``): refresh ONLY the branches this
    source maps to — its transactional rows (stock, sales, purchases) are cleared
    and reloaded, while every other branch (the other live server, imported
    history) is left untouched. The shared catalogue / customers / vendors are
    matched instead of duplicated AND updated in place, so owner data-cleaning on
    eStock (e.g. scientific names) and live customer balances flow through on
    every cycle. This is how two branch servers sync into one ProCare database.

    Multi-branch consolidation (``wipe=False`` + ``force_branch_code``): APPEND a
    restored branch backup (e.g. Elsanta, then Mashala) into ProCare WITHOUT
    clearing what's already there, mapping ALL of that source's rows to the named
    branch. Append implies ``dedup`` so the shared drug catalogue, customers and
    vendors are matched (by code / mobile / name) instead of duplicated across
    branches — run each backup once. Returns per-table row counts (rows added).

    Incremental (``branch_scoped=True`` + ``incremental_days=N``): once the
    branch is already filled, each cycle re-pulls ONLY the last N days of
    sales/purchases (a trailing window — returns mutate recent source rows, so
    append alone would drift) plus the small live-state tables (catalogue,
    customers, vendors, employees, stock, treasury). This is what makes a
    short cadence viable over a slow WAN and on SQL Server: history never
    crosses the wire again. An empty branch automatically gets the full load.
    """
    dedup = (branch_scoped or not wipe) if dedup is None else dedup
    update_on_match = branch_scoped
    insp = inspect(source_engine)

    # Not a plain `engine.connect()`: the wrapper retries dropped-connection
    # errors (flaky Elsanta WAN) on a fresh connection — see _ResilientSource.
    src = _ResilientSource(source_engine)
    try:
        if force_branch_code:
            # Every row from this single-branch backup belongs to one branch.
            default_branch = _ensure_branch_code(dst, force_branch_code)
            branch_map: dict[int, int] = {}
        else:
            # Discover the branches that actually exist on the source and ensure a
            # ProCare branch for each, so no branch's data is merged into another
            # (the remote server may carry Elsanta, Mashala, ...).
            store_ids = _distinct_store_ids(insp, src)
            branch_map = _resolve_branch_map(dst, store_branch_map, store_ids)
            default_branch = next(iter(branch_map.values()))

        # Incremental gate: only once the branch already holds mirrored sales —
        # an empty branch (first run, or after a reset) needs the full history.
        window_cutoff: date | None = None
        if branch_scoped and incremental_days and incremental_days > 0:
            scope_ids = [int(b) for b in (set(branch_map.values()) | {default_branch})]
            has_sales = dst.execute(
                select(m.Sale.sale_id).where(m.Sale.branch_id.in_(scope_ids)).limit(1)
            ).first()
            if has_sales:
                window_cutoff = date.today() - timedelta(days=incremental_days)

        if branch_scoped:
            if window_cutoff is not None:
                _wipe_branch_sales_window(
                    dst, set(branch_map.values()) | {default_branch}, window_cutoff
                )
            else:
                _wipe_branch_rows(dst, set(branch_map.values()) | {default_branch})
        elif wipe:
            _wipe_destination(dst)
        counts: dict = {}
        counts["sync_mode"] = (
            f"incremental({incremental_days}d)" if window_cutoff is not None
            else ("branch_full" if branch_scoped else "full")
        )

        product_map = _load_products(insp, src, dst, counts, dedup=dedup, update_on_match=update_on_match)
        customer_map = _load_customers(insp, src, dst, counts, dedup=dedup, update_on_match=update_on_match)
        _load_vendors(insp, src, dst, counts, dedup=dedup)
        # Job titles before employees: the employee pass resolves each row's
        # source job_id through this map.
        job_map = _load_jobs(insp, src, dst, counts)
        _load_employees(insp, src, dst, counts, job_map)
        # Product_Amount and Branches_Product_Amount overlap the same way the
        # sales tables do — one identity set spans both so a batch is mirrored
        # once, under the branch that actually holds it.
        seen_stock: set = set()
        _load_stock(insp, src, dst, counts, product_map, branch_map, default_branch,
                    seen=seen_stock)
        _load_branch_product_amount(insp, src, dst, counts, product_map, branch_map,
                                    default_branch, seen=seen_stock)

        # Cashier attribution: eStock stores the cashier as a username on each
        # sale; map it to the ProCare employee so per-cashier reports work.
        # (_load_employees ran first, so EVERY eStock cashier resolves — not
        # only the seeded roster.)
        employee_map = {
            (u or "").strip().lower(): eid
            for eid, u in dst.execute(select(m.Employee.employee_id, m.Employee.username)).all()
            if u
        }

        # eStock splits transactions across the head-office table AND the branch
        # ("Branches_*") table — a head-office DB can hold MORE rows in the branch
        # table than the main one. Mirror BOTH so totals match eStock's reports.
        # (missing tables are skipped inside _load_sales / _load_purchases.)
        sales_tables = [
            ("Sales_header", "Sales_details", False, "sales"),
            ("Branches_sales_header", "Branches_sales_details", False, "sales"),
            ("Back_sales_header", "Back_Sales_details", True, "returns"),
            ("Branches_back_sales_header", "Branches_back_sales_details", True, "returns"),
        ]
        # ...but the two tables OVERLAP: the branch table repeats every
        # head-office row under branch_id = 1 and adds the other branch's rows
        # on top. One identity set per stream (shared across that stream's
        # tables) keeps each bill exactly once — see _load_sales.
        seen_sales: dict[str, set] = {"sales": set(), "returns": set()}
        for h, d, ret, ck in sales_tables:
            _load_sales(
                insp, src, dst, counts, product_map, customer_map, branch_map,
                default_branch, employee_map, header_tbl=h, detail_tbl=d, returns=ret, count_key=ck,
                window_cutoff=window_cutoff, seen=seen_sales[ck],
            )

        seen_purchases: set = set()
        for h, d in [
            ("Purchase_header", "Purchase_details"),
            ("Branches_purchase_header", "Branches_purchase_details"),
        ]:
            _load_purchases(insp, src, dst, counts, product_map, branch_map, default_branch,
                            header_tbl=h, detail_tbl=d, window_cutoff=window_cutoff,
                            seen=seen_purchases)

        # Mirror high-value uncovered tables (Phase 7).
        _load_cash_shift_closes(insp, src, dst, counts, branch_map, default_branch)
        _load_branch_orders(insp, src, dst, counts, product_map, branch_map, default_branch)
        # GL verbatim mirror: chart of accounts + central journal + manual adjustments
        # (optional, upsert by source id).
        _load_gl_accounts(insp, src, dst, counts)
        _load_gl_journal(insp, src, dst, counts)
        _load_gl_adjustments(insp, src, dst, counts)
        _load_gl_subledgers(insp, src, dst, counts)

        _load_treasury(insp, src, dst, counts, branch_map, default_branch)
        # Shareholders + dividends (optional, upsert by source id).
        _load_shareholders(insp, src, dst, counts)
        # Payroll depth (optional, upsert by source salary id).
        _load_payroll(insp, src, dst, counts)
        # Salary advances ledger (optional, upsert by source id).
        _load_salary_advances(insp, src, dst, counts)

        # 100% eStock coverage: mirror all remaining source tables verbatim into
        # the generic EstockRawMirror table (~84 tables in one pass).  Read-only
        # SELECT on eStock, never a write.
        _load_uncovered_tables(insp, src, dst, counts, branch_map, default_branch)

        dst.commit()
    finally:
        src.close()

    # A full load deletes and recreates every product row, so the learned
    # barcode map's product_id values go stale. product_code survives (it is
    # what this mirror dedupes on), so re-resolve from it. Fail-soft by
    # construction — bookkeeping must never fail a cycle that mirrored fine.
    from app.services import gtin_map

    counts["barcodes_relinked"] = gtin_map.relink(dst).get("relinked", 0)
    return counts


def _ensure_branch_code(dst: Session, code: str, name_ar: str | None = None, name_en: str | None = None) -> int:
    """Return the branch_id for ``code``, creating the branch if it's new."""
    code = code.strip().upper()
    existing = dst.scalars(select(m.Branch).where(m.Branch.code == code)).first()
    if existing:
        return existing.branch_id
    b = m.Branch(code=code, name_ar=name_ar or code, name_en=name_en or code)
    dst.add(b)
    dst.flush()
    return b.branch_id


def _distinct_store_ids(insp, src) -> set[int]:
    """Every branch key present on the source, across the branch-bearing tables.

    Both discriminators feed the one map: ``store_id`` on the head-office tables
    and ``branch_id`` on the ``Branches_*`` ones (see ``_row_branch``). Without
    the branch_id half a branch that appears ONLY in the Branches_* tables is
    never discovered — Mas-hala's rows all carry store_id 1 — so it silently
    inherits the default branch instead of getting one of its own.
    """
    ids: set[int] = set()
    sources = (
        ("Product_Amount", "store_id"),
        ("Sales_header", "store_id"),
        ("Back_sales_header", "store_id"),
        ("Purchase_header", "store_id"),
        ("Branches_Product_amount", "branch_id"),
        ("Branches_sales_header", "branch_id"),
        ("Branches_purchase_header", "branch_id"),
    )
    for tbl, col in sources:
        if not insp.has_table(tbl):
            continue
        cols = {c["name"].lower() for c in insp.get_columns(tbl)}
        if col not in cols:
            continue
        for (v,) in src.execute(text(f"SELECT DISTINCT {col} FROM {tbl}")):
            if v is not None:
                ids.add(int(v))
    return ids


def _resolve_branch_map(
    dst: Session, store_branch_map: dict | None, store_ids: set[int] | None = None
) -> dict[int, int]:
    """eStock branch key -> branch_id (ProCare).

    The key is whichever discriminator the source table carries: ``store_id`` on
    the head-office tables, ``branch_id`` on the ``Branches_*`` ones. They share
    one numbering here — 1 = Elsanta, 2 = Mas-hala — so one map serves both; see
    ``_row_branch``.

    Honours an operator-provided map ({key: 'CODE'} or {key: branch_id}),
    creating any named ProCare branch that doesn't exist yet. Any key seen on
    the source but not mapped gets its own auto-created branch, so a new branch
    (e.g. Mashal) never silently merges into another.
    """
    branches = {b.code: b for b in dst.scalars(select(m.Branch)).all()}
    if not branches:
        raise RuntimeError("ProCare branches not seeded — run schema/seed first.")
    by_code = {code: b.branch_id for code, b in branches.items()}

    # Proper bilingual display names for the branch codes we know, so an
    # auto-created branch never shows its raw code in the Arabic UI.
    known = {
        "ELSANTA": ("السنطه", "Elsanta"),
        "MASHALA": ("مسهله", "Mas-hala"),
    }

    def ensure_branch(code: str, name_ar: str | None = None, name_en: str | None = None) -> int:
        code = code.strip().upper()
        if code in by_code:
            return by_code[code]
        default_ar, default_en = known.get(code, (code, code))
        b = m.Branch(code=code, name_ar=name_ar or default_ar, name_en=name_en or default_en)
        dst.add(b)
        dst.flush()
        by_code[code] = b.branch_id
        return b.branch_id

    out: dict[int, int] = {}
    if store_branch_map:
        # {store_id: 'CODE'} (config — create if missing) or {store_id: id} (tests).
        for k, v in store_branch_map.items():
            out[int(k)] = ensure_branch(v) if isinstance(v, str) else int(v)
    else:
        # Default (owner-confirmed): store_id 1 = Elsanta السنطه, 2 = Mas-hala
        # مسهله. Procare has exactly these two pharmacies.
        if "ELSANTA" in by_code:
            out[1] = by_code["ELSANTA"]
        if "MASHALA" in by_code:
            out[2] = by_code["MASHALA"]

    # Auto-create a branch for any source store_id we don't have a mapping for.
    for sid in sorted(store_ids or []):
        if sid not in out:
            out[sid] = ensure_branch(f"STORE{sid}", name_ar=f"فرع {sid}", name_en=f"Store {sid}")

    return out or {1: next(iter(by_code.values()))}


def _row_branch(row, *, branch_col, store_col, branch_map, default_branch) -> int:
    """Resolve one source row's ProCare branch.

    eStock keeps the real branch discriminator in ``branch_id`` on its
    ``Branches_*`` tables. ``store_id`` is the till number and is 1 on EVERY row
    of this schema — including Mas-hala's — so resolving a Branches_* row on
    store_id collapses both pharmacies onto one branch. Prefer branch_id
    wherever the table carries it; fall back to store_id for the head-office
    tables that don't.
    """
    col = branch_col or store_col
    if col and row.get(col) is not None:
        return branch_map.get(int(row[col])) or default_branch
    return default_branch


def _wipe_destination(dst: Session) -> None:
    # The full wipe is the single most destructive operation in the system —
    # make sure a recent backup exists first (throttled; fail-soft).
    from app.services import backup

    backup.backup_if_stale(6, "pre-sync-wipe")
    for model in _WIPE_ORDER:
        if model is not None:
            dst.execute(text(f"DELETE FROM {model.__tablename__}"))
    dst.flush()


def _wipe_branch_rows(dst: Session, branch_ids: set[int]) -> None:
    """Clear only ``branch_ids``' mirrored transactional rows (children first).

    The shared catalogue (products/customers/vendors) stays — it is matched and
    refreshed by the dedup loaders — and every other branch's rows survive, so
    two live sources and the imported history can coexist in one database.
    """
    ids = [int(b) for b in branch_ids if b is not None]
    if not ids:
        return
    sale_ids = select(m.Sale.sale_id).where(m.Sale.branch_id.in_(ids))
    dst.execute(delete(m.LoyaltyTransaction).where(m.LoyaltyTransaction.sale_id.in_(sale_ids)))
    # incentive_ledger points at sale_lines.line_id, so it has to go before the
    # lines do — otherwise the branch wipe (every sync cycle) dies on
    # "FOREIGN KEY constraint failed ... DELETE FROM sale_lines" as soon as one
    # cashier has earned points on a mirrored sale.
    if hasattr(m, "IncentiveLedger"):
        dst.execute(delete(m.IncentiveLedger).where(m.IncentiveLedger.sale_id.in_(sale_ids)))
    dst.execute(delete(m.SaleLine).where(m.SaleLine.sale_id.in_(sale_ids)))
    # Returns first (self-FK sales.original_sale_id), then the originals.
    dst.execute(
        delete(m.Sale).where(m.Sale.branch_id.in_(ids), m.Sale.original_sale_id.is_not(None))
    )
    dst.execute(delete(m.Sale).where(m.Sale.branch_id.in_(ids)))
    purchase_ids = select(m.Purchase.purchase_id).where(m.Purchase.branch_id.in_(ids))
    dst.execute(delete(m.PurchaseLine).where(m.PurchaseLine.purchase_id.in_(purchase_ids)))
    dst.execute(delete(m.Purchase).where(m.Purchase.branch_id.in_(ids)))
    _wipe_branch_stock(dst, ids)
    dst.flush()


def _wipe_branch_stock(dst: Session, ids: list[int]) -> None:
    """Clear ``ids``' stock rows (batches + movements + transfers touching them).

    Runs on EVERY sync cycle — ``Product_Amount`` is current-state, so stock is
    always a full per-branch refresh even when sales sync incrementally.
    """
    batch_ids = select(m.StockBatch.batch_id).where(m.StockBatch.branch_id.in_(ids))
    # Transfers touch batches on BOTH ends — any line touching a wiped batch
    # goes, then every transfer with a wiped endpoint branch. Lines are matched
    # by parent transfer too, not only by batch: a *requested* (not yet
    # approved) transfer's lines have NULL batch ids and would otherwise
    # survive, failing the parent delete with a FK error and killing the whole
    # sync cycle.
    dying_transfers = select(m.StockTransfer.transfer_id).where(
        m.StockTransfer.from_branch_id.in_(ids) | m.StockTransfer.to_branch_id.in_(ids)
    )
    dst.execute(
        delete(m.StockTransferLine).where(
            m.StockTransferLine.from_batch_id.in_(batch_ids)
            | m.StockTransferLine.to_batch_id.in_(batch_ids)
            | m.StockTransferLine.transfer_id.in_(dying_transfers)
        )
    )
    dst.execute(
        delete(m.StockTransfer).where(
            m.StockTransfer.from_branch_id.in_(ids) | m.StockTransfer.to_branch_id.in_(ids)
        )
    )
    dst.execute(
        delete(m.StockMovement).where(
            m.StockMovement.branch_id.in_(ids) | m.StockMovement.batch_id.in_(batch_ids)
        )
    )
    dst.execute(delete(m.StockBatch).where(m.StockBatch.branch_id.in_(ids)))


def _wipe_branch_sales_window(dst: Session, branch_ids: set[int], cutoff: date) -> None:
    """Clear only ``branch_ids``' sales/purchases dated ``cutoff`` or later.

    The incremental cycle re-pulls just this trailing window (returns and
    same-day edits mutate RECENT source rows, so pure append would drift);
    everything older is immutable history and survives untouched. Self-FK
    safety: a return is always dated at/after its original sale, so an
    original inside the window can never leave a referencing return outside
    it — the returns-first delete order below covers every case.
    """
    ids = [int(b) for b in branch_ids if b is not None]
    if not ids:
        return
    sale_ids = select(m.Sale.sale_id).where(
        m.Sale.branch_id.in_(ids), m.Sale.sale_date >= cutoff
    )
    dst.execute(delete(m.LoyaltyTransaction).where(m.LoyaltyTransaction.sale_id.in_(sale_ids)))
    # See _wipe_branch_rows: incentive_ledger references sale_lines.line_id and
    # has to be cleared before the lines it points at.
    if hasattr(m, "IncentiveLedger"):
        dst.execute(delete(m.IncentiveLedger).where(m.IncentiveLedger.sale_id.in_(sale_ids)))
    dst.execute(delete(m.SaleLine).where(m.SaleLine.sale_id.in_(sale_ids)))
    dst.execute(
        delete(m.Sale).where(
            m.Sale.branch_id.in_(ids), m.Sale.sale_date >= cutoff,
            m.Sale.original_sale_id.is_not(None),
        )
    )
    dst.execute(delete(m.Sale).where(m.Sale.branch_id.in_(ids), m.Sale.sale_date >= cutoff))
    purchase_ids = select(m.Purchase.purchase_id).where(
        m.Purchase.branch_id.in_(ids), m.Purchase.bill_date >= cutoff
    )
    dst.execute(delete(m.PurchaseLine).where(m.PurchaseLine.purchase_id.in_(purchase_ids)))
    dst.execute(
        delete(m.Purchase).where(m.Purchase.branch_id.in_(ids), m.Purchase.bill_date >= cutoff)
    )
    _wipe_branch_stock(dst, ids)
    dst.flush()


def _load_products(insp, src, dst, counts, dedup: bool = False, update_on_match: bool = False) -> dict[int, int]:
    """Returns src product_id -> dst product_id. With ``dedup`` (append mode),
    a product whose code already exists in ProCare is reused, not duplicated.
    With ``update_on_match`` (continuous sync) a matched product's names, prices
    and flags are refreshed from the source so owner edits on eStock (e.g.
    scientific-name cleanups) propagate on every cycle."""
    cols = {c["name"] for c in insp.get_columns("Products")}
    pid = _pick(cols, "product_id")
    name_ar = _pick(cols, "product_name_ar", "name_ar")
    name_en = _pick(cols, "product_name_en", "name_en")
    sci = _pick(cols, "product_scientific_name", "scientific_name")
    code = _pick(cols, "product_code", "code")
    fast = _pick(cols, "product_fast_code", "fast_code")
    drug = _pick(cols, "product_drug")
    has_exp = _pick(cols, "product_has_expire")
    sell = _pick(cols, "sell_price")
    buy = _pick(cols, "buy_price")
    tax = _pick(cols, "tax_price")
    deleted = _pick(cols, "deleted")
    active = _pick(cols, "active")
    # Units (وحدة كبرى/صغرى): eStock column names vary by version — try the
    # known spellings; absent columns just leave the defaults (factor 1).
    unit_big = _pick(cols, "product_unit1", "unit1", "product_unit", "unit_name", "product_unit_ar")
    unit_small = _pick(cols, "product_unit2", "unit2", "sub_unit", "product_sub_unit")
    unit_factor = _pick(
        cols, "product_no2per1", "no2per1", "unit2_per_unit1", "product_unit2_count", "unit_factor"
    )

    def _factor(r) -> float:
        f = _num(r.get(unit_factor), 1) if unit_factor else 1
        return f if f and f > 0 else 1

    def _pkey(code_val, nm):
        # Codeless products fall back to the display name, otherwise a repeated
        # branch-scoped sync (which never wipes the catalogue) would re-insert
        # them on every cycle.
        if code_val is not None and str(code_val).strip():
            return "c:" + str(code_val).strip()
        if nm and str(nm).strip():
            return "n:" + str(nm).strip()
        return None

    existing: dict[str, int] = {}
    if dedup:
        rows_ex = dst.execute(select(m.Product.product_id, m.Product.code, m.Product.name_ar)).all()
        for ex_pid, ex_code, ex_name in rows_ex:
            key = _pkey(ex_code, ex_name)
            if key and key not in existing:
                existing[key] = ex_pid

    rows = src.execute(text("SELECT * FROM Products")).mappings().all()
    mapping: dict[int, int] = {}
    pairs = []  # (row, obj) for products we actually create
    updates = []  # bulk field refresh for matched products (update_on_match)
    for r in rows:
        code_val = _pkey(
            r.get(code) if code else None,
            _ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None),
        )
        if dedup and code_val is not None and code_val in existing:
            if pid and r.get(pid) is not None:
                mapping[int(r[pid])] = existing[code_val]
            if update_on_match:
                src_sci = r.get(sci) if sci else None
                updates.append(
                    {
                        "b_pid": existing[code_val],
                        "b_name_ar": _ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None),
                        "b_name_en": r.get(name_en) if name_en else None,
                        # NULL when the source field is blank so the COALESCE
                        # in the update keeps ProCare's own value — otherwise
                        # every sync cycle would wipe the Titan/Drug-Eye
                        # scientific-name enrichment (docs/03 §4).
                        "b_sci": src_sci if src_sci and str(src_sci).strip() else None,
                        "b_sell": _price(r.get(sell)) if sell else 0,
                        "b_buy": _price(r.get(buy)) if buy else 0,
                        "b_tax": _price(r.get(tax)) if tax else 0,
                        "b_unit_big": _str(r.get(unit_big)) if unit_big else None,
                        "b_unit_small": _str(r.get(unit_small)) if unit_small else None,
                        "b_unit_factor": _factor(r),
                        "b_active": _b(r.get(active)) if active else True,
                        "b_deleted": _product_deleted(r.get(deleted)) if deleted else False,
                    }
                )
            continue
        pairs.append((
            r,
            m.Product(
                code=r.get(code) if code else None,
                fast_code=r.get(fast) if fast else None,
                name_ar=_ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None),
                name_en=r.get(name_en) if name_en else None,
                scientific_name=r.get(sci) if sci else None,
                is_controlled=_b(r.get(drug)) if drug else False,
                has_expiry=_b(r.get(has_exp)) if has_exp else True,
                sell_price=_price(r.get(sell)) if sell else 0,
                buy_price=_price(r.get(buy)) if buy else 0,
                tax_price=_price(r.get(tax)) if tax else 0,
                unit_big=_str(r.get(unit_big)) if unit_big else None,
                unit_small=_str(r.get(unit_small)) if unit_small else None,
                unit_factor=_factor(r),
                is_active=_b(r.get(active)) if active else True,
                is_deleted=_product_deleted(r.get(deleted)) if deleted else False,
            ),
        ))
    dst.add_all([obj for _, obj in pairs])
    if updates:
        stmt = (
            m.Product.__table__.update()
            .where(m.Product.product_id == bindparam("b_pid"))
            .values(
                name_ar=bindparam("b_name_ar"),
                name_en=bindparam("b_name_en"),
                # Keep ProCare's enrichment when eStock has no scientific name.
                scientific_name=func.coalesce(bindparam("b_sci"), m.Product.scientific_name),
                sell_price=bindparam("b_sell"),
                buy_price=bindparam("b_buy"),
                tax_price=bindparam("b_tax"),
                unit_big=bindparam("b_unit_big"),
                unit_small=bindparam("b_unit_small"),
                unit_factor=bindparam("b_unit_factor"),
                is_active=bindparam("b_active"),
                is_deleted=bindparam("b_deleted"),
            )
        )
        dst.execute(stmt, updates)
    dst.flush()
    for r, obj in pairs:
        if pid and r.get(pid) is not None:
            mapping[int(r[pid])] = obj.product_id
        cv = _pkey(r.get(code) if code else None, obj.name_ar)
        if dedup and cv is not None:
            existing[cv] = obj.product_id
    counts["products"] = len(pairs)
    counts["products_updated"] = len(updates)
    return mapping


def _load_customers(insp, src, dst, counts, dedup: bool = False, update_on_match: bool = False) -> dict[int, int]:
    cols = {c["name"] for c in insp.get_columns("Customer")}
    cid = _pick(cols, "customer_id")
    name_ar = _pick(cols, "customer_name_ar", "name_ar")
    name_en = _pick(cols, "customer_name_en", "name_en")
    mobile = _pick(cols, "mobile")
    limit = _pick(cols, "customer_max_money")
    balance = _pick(cols, "customer_current_money")
    opening = _pick(cols, "customer_start_money")
    deleted = _pick(cols, "deleted")
    active = _pick(cols, "active")

    def _ckey(mob, nm):
        if mob and str(mob).strip():
            return "m:" + str(mob).strip()
        if nm and str(nm).strip():
            return "n:" + str(nm).strip()
        return None

    existing: dict[str, int] = {}
    if dedup:
        for ex in dst.scalars(select(m.Customer)).all():
            key = _ckey(ex.mobile, ex.name_ar)
            if key and key not in existing:
                existing[key] = ex.customer_id

    rows = src.execute(text("SELECT * FROM Customer")).mappings().all()
    mapping: dict[int, int] = {}
    pairs = []
    updates = []  # refresh matched customers' balances/limits (update_on_match)
    for r in rows:
        mob = r.get(mobile) if mobile else None
        nm = _ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None)
        key = _ckey(mob, nm)
        if dedup and key is not None and key in existing:
            if cid and r.get(cid) is not None:
                mapping[int(r[cid])] = existing[key]
            if update_on_match:
                updates.append(
                    {
                        "customer_id": existing[key],
                        "credit_limit": _num(r.get(limit)) if limit else 0,
                        "current_balance": _num(r.get(balance)) if balance else 0,
                        "is_active": _b(r.get(active)) if active else True,
                        "is_deleted": _b(r.get(deleted)) if deleted else False,
                    }
                )
            continue
        pairs.append((
            r,
            m.Customer(
                name_ar=nm,
                name_en=r.get(name_en) if name_en else None,
                mobile=mob,
                credit_limit=_num(r.get(limit)) if limit else 0,
                current_balance=_num(r.get(balance)) if balance else 0,
                opening_balance=_num(r.get(opening)) if opening else 0,
                is_active=_b(r.get(active)) if active else True,
                is_deleted=_b(r.get(deleted)) if deleted else False,
            ),
        ))
    dst.add_all([obj for _, obj in pairs])
    if updates:
        stmt = m.Customer.__table__.update().where(m.Customer.customer_id == bindparam("b_cid"))
        dst.execute(stmt, [dict(u, b_cid=u.pop("customer_id")) for u in updates])
    dst.flush()
    for r, obj in pairs:
        if cid and r.get(cid) is not None:
            mapping[int(r[cid])] = obj.customer_id
        key = _ckey(
            r.get(mobile) if mobile else None,
            _ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None),
        )
        if dedup and key is not None:
            existing[key] = obj.customer_id
    counts["customers"] = len(pairs)
    counts["customers_updated"] = len(updates)
    return mapping


def _load_vendors(insp, src, dst, counts, dedup: bool = False) -> None:
    cols = {c["name"] for c in insp.get_columns("Vendor")}
    name_ar = _pick(cols, "vendor_name_ar", "name_ar")
    name_en = _pick(cols, "vendor_name_en", "name_en")
    tel = _pick(cols, "tel")
    mobile = _pick(cols, "mobile")
    limit = _pick(cols, "vendor_max_money")
    balance = _pick(cols, "vendor_current_money")

    existing: set[str] = set()
    if dedup:
        for (nm,) in dst.execute(select(m.Vendor.name_ar)).all():
            if nm:
                existing.add(str(nm).strip())

    rows = src.execute(text("SELECT * FROM Vendor")).mappings().all()
    objs = []
    for r in rows:
        nm = _ar(r.get(name_ar) if name_ar else None, r.get(name_en) if name_en else None)
        if dedup and str(nm).strip() in existing:
            continue  # vendor already known — don't duplicate across branches
        existing.add(str(nm).strip())
        objs.append(
            m.Vendor(
                name_ar=nm,
                name_en=r.get(name_en) if name_en else None,
                tel=r.get(tel) if tel else None,
                mobile=r.get(mobile) if mobile else None,
                credit_limit=_num(r.get(limit)) if limit else 0,
                current_balance=_num(r.get(balance)) if balance else 0,
            )
        )
    dst.add_all(objs)
    dst.flush()
    counts["vendors"] = len(objs)


def _load_jobs(insp, src, dst, counts) -> dict[int, int]:
    """Mirror eStock's ``Jobs`` master (job titles / المسمى الوظيفي).

    Returns ``{source job_id -> ProCare job_id}`` so ``_load_employees`` can
    resolve each employee's title. Absent source table -> empty map (the
    employee loader then simply leaves ``job_id`` untouched).

    Matching is by ``source_id`` first, then by Arabic name — the name fallback
    is what stops the mirror from duplicating the job titles already created by
    the seed (which carry no source id). Titles are a tiny company-wide master
    and are NOT in ``_WIPE_ORDER``: employees are never wiped, so their titles
    must survive a full refresh too.
    """
    counts["jobs"] = 0
    counts["jobs_updated"] = 0
    if not insp.has_table("Jobs"):
        return {}
    cols = {c["name"] for c in insp.get_columns("Jobs")}
    jid = _pick(cols, "job_id")
    if jid is None:
        return {}  # without the source key there is nothing to attribute
    code = _pick(cols, "job_code", "code")
    name_ar = _pick(cols, "job_name_ar", "name_ar")
    name_en = _pick(cols, "job_name_en", "name_en")

    by_source: dict[int, int] = {}
    by_name: dict[str, int] = {}
    for j in dst.scalars(select(m.Job)).all():
        if j.source_id is not None:
            by_source[int(j.source_id)] = j.job_id
        key = (j.name_ar or "").strip()
        if key and key not in by_name:
            by_name[key] = j.job_id

    mapping: dict[int, int] = {}
    created = updated = 0
    for r in src.execute(text("SELECT * FROM Jobs")).mappings().all():
        if r.get(jid) is None:
            continue
        source_id = int(r[jid])
        title_ar = _ar(
            r.get(name_ar) if name_ar else None,
            r.get(name_en) if name_en else None,
            placeholder=f"وظيفة {source_id}",
        )
        fields = {
            "source_id": source_id,
            "code": (_str(r.get(code)) or None) if code else None,
            "name_ar": title_ar,
            "name_en": r.get(name_en) if name_en else None,
        }
        existing_id = by_source.get(source_id) or by_name.get(title_ar.strip())
        if existing_id is not None:
            dst.execute(
                m.Job.__table__.update()
                .where(m.Job.__table__.c.job_id == existing_id)
                .values(**fields)
            )
            updated += 1
        else:
            obj = m.Job(**fields)
            dst.add(obj)
            # Flush per new title to get its id: Jobs is a handful of rows, and
            # the map must be complete before the employee pass runs.
            dst.flush()
            existing_id = obj.job_id
            created += 1
        by_source[source_id] = existing_id
        by_name.setdefault(title_ar.strip(), existing_id)
        mapping[source_id] = existing_id
    dst.flush()
    counts["jobs"] = created
    counts["jobs_updated"] = updated
    return mapping


def _load_employees(insp, src, dst, counts, job_map: dict[int, int] | None = None) -> None:
    """Mirror eStock's Employee master (the POS users) into ProCare.

    eStock keeps the per-cashier permission flags ON the Employee row
    (``emp_edit_sell_price``, ``allaw_sale_credit``, ``allaw_r_sale``,
    ``allaw_un_sale``, ``emp_change_cash_disk``, ``emp_show_money``,
    ``max_disc_per``) — they map 1:1 onto ProCare's Employee flags, so POS
    discount limits and permissions survive the mirror. Matching is by username
    (eStock's ``Sales_header.cashier_id`` IS that username, so loading
    employees BEFORE the sales pass makes cashier attribution cover every
    eStock cashier, not just the seeded roster).

    SECURITY: eStock stores plaintext passwords — they are NEVER imported. A
    new mirrored employee gets an unusable sentinel hash (``verify_password``
    only matches ``sha256$…`` values) and the most restrictive role until an
    admin grants real ProCare access; a matched employee's ProCare
    password/role/branch are never touched, only display fields and flags.
    """
    if not insp.has_table("Employee"):
        counts["employees"] = 0
        return
    cols = {c["name"] for c in insp.get_columns("Employee")}
    username = _pick(cols, "username")
    if username is None:
        counts["employees"] = 0
        return
    name_ar = _pick(cols, "emp_name_ar", "name_ar")
    name_en = _pick(cols, "emp_name_en", "name_en")
    mobile = _pick(cols, "mobile")
    salary = _pick(cols, "basic_salary")
    max_disc = _pick(cols, "max_disc_per")
    edit_price = _pick(cols, "emp_edit_sell_price")
    sale_credit = _pick(cols, "allaw_sale_credit")
    allow_ret = _pick(cols, "allaw_r_sale")
    allow_void = _pick(cols, "allaw_un_sale")
    change_shift = _pick(cols, "emp_change_cash_disk")
    show_money = _pick(cols, "emp_show_money")
    active = _pick(cols, "active")
    deleted = _pick(cols, "deleted")
    source_job = _pick(cols, "job_id")

    existing = {
        (u or "").strip().lower(): (eid, ph)
        for eid, u, ph in dst.execute(
            select(m.Employee.employee_id, m.Employee.username, m.Employee.password_hash)
        ).all()
        if u
    }
    created = updated = 0
    for r in src.execute(text("SELECT * FROM Employee")).mappings().all():
        uname = str(r.get(username) or "").strip()
        if not uname:
            continue  # no username = not a POS user — nothing to attribute
        is_active = (_b(r.get(active)) if active else True) and not (
            _b(r.get(deleted)) if deleted else False
        )
        fields = dict(
            name_ar=_ar(r.get(name_ar) if name_ar else None,
                        r.get(name_en) if name_en else None, placeholder=uname),
            name_en=r.get(name_en) if name_en else None,
            phone=(_str(r.get(mobile)) or "")[:20] or None if mobile else None,
            basic_salary=_num(r.get(salary)) if salary else 0,
            max_disc_per=_num(r.get(max_disc)) if max_disc else 0,
            can_edit_sell_price=_b(r.get(edit_price)) if edit_price else False,
            can_sale_credit=_b(r.get(sale_credit)) if sale_credit else False,
            can_return=_b(r.get(allow_ret)) if allow_ret else False,
            can_void=_b(r.get(allow_void)) if allow_void else False,
            can_change_shift=_b(r.get(change_shift)) if change_shift else False,
            can_see_buy_price=_b(r.get(show_money)) if show_money else False,
            is_active=is_active,
        )
        # Job title (المسمى الوظيفي). Only set when the source id resolves to a
        # mirrored title — an unknown/absent job_id must leave the field alone
        # rather than write a dangling FK.
        if source_job and job_map:
            resolved = job_map.get(_int_or_none(r.get(source_job)))
            if resolved is not None:
                fields["job_id"] = resolved
        eid, cur_hash = existing.get(uname.lower(), (None, None))
        if eid is not None:
            # A usable ProCare password marks a REAL ProCare login (roster or
            # admin-granted). eStock's active/deleted state must never disable
            # it — otherwise a stale source employee row locks the owner out on
            # every sync cycle. Only the mirror sentinel (``!estock-mirror``,
            # any ``!``-prefixed unusable hash) follows the source. NB: a real
            # hash may be ``sha256$…`` OR ``pbkdf2$…`` — the login path upgrades
            # sha256 → pbkdf2 in place — so gate on "not a sentinel", never on a
            # specific algorithm prefix (that was the original lockout bug).
            if cur_hash and not cur_hash.startswith("!"):
                fields.pop("is_active")
            dst.execute(
                m.Employee.__table__.update()
                .where(m.Employee.__table__.c.employee_id == eid)
                .values(**fields)
            )
            updated += 1
        else:
            # Two eStock rows can carry the same username — the source has no
            # unique index on it — while ProCare's `username` IS unique.
            # `existing` is built once BEFORE this loop, so a new row must be
            # registered here as it is created; otherwise the second source row
            # falls into this branch too and queues a SECOND insert. That
            # duplicate does not fail here — it fails at the post-loop flush, as
            # a unique violation. And because the mirror is a single transaction
            # (one commit at the end of `mirror`), that violation rolls back
            # EVERY table already loaded, not just this employee.
            #
            # Flushing per new employee to obtain the id is affordable: Employee
            # is a small master table (staff), not one of the 100K-row tables.
            #
            # Deliberately NOT wrapped in `dst.begin_nested()`. A SAVEPOINT would
            # look like a tidier guard, but pysqlite does not emit BEGIN properly,
            # so on SQLite (dev/demo) the savepoint's work escapes the enclosing
            # transaction and survives a rollback — quietly breaking the
            # all-or-nothing property the mirror depends on. Deduplicating here
            # needs no savepoint and behaves identically on SQLite and SQL Server.
            obj = m.Employee(
                username=uname, password_hash="!estock-mirror", role="assistant", **fields
            )
            dst.add(obj)
            dst.flush()
            existing[uname.lower()] = (obj.employee_id, obj.password_hash)
            created += 1
    dst.flush()
    counts["employees"] = created
    counts["employees_updated"] = updated


def _load_stock(insp, src, dst, counts, product_map, branch_map, default_branch,
                seen: set | None = None) -> None:
    """Mirror the head-office ``Product_Amount`` (current per-batch stock).

    ``seen`` collects this load's ``(branch, pa_id)`` batches so
    ``_load_branch_product_amount`` can skip the copies of them that
    ``Branches_Product_Amount`` repeats — see _load_sales for the same overlap
    on the transactional tables.

    The identity is ``pa_id``, the table's own row id, and NEVER ``counter_id``:
    counter_id is the shelf/counter number and takes just 77 distinct values
    across 67,447 batches, so keying on it collapses the entire stock table onto
    77 rows. A source with no pa_id simply skips the dedup — mirroring a batch
    twice is recoverable, dropping 99.9% of them is not.
    """
    if not insp.has_table("Product_Amount"):
        counts["stock_batches"] = 0
        return
    cols = {c["name"] for c in insp.get_columns("Product_Amount")}
    pid = _pick(cols, "product_id")
    store = _pick(cols, "store_id")
    branch_col = _pick(cols, "branch_id")
    counter = _pick(cols, "counter_id")
    ident = _pick(cols, "pa_id")          # the row id — see the docstring
    amount = _pick(cols, "amount")
    buy = _pick(cols, "buy_price")
    sell = _pick(cols, "sell_price")
    tax = _pick(cols, "tax_price")
    exp = _pick(cols, "exp_date")

    rows = src.execute(text("SELECT * FROM Product_Amount")).mappings().all()
    n = 0
    batch_objs = []
    for r in rows:
        src_pid = int(r[pid]) if pid and r.get(pid) is not None else None
        dst_pid = product_map.get(src_pid)
        if dst_pid is None:
            continue  # orphan batch (no matching product) — skip, don't invent
        branch_id = _row_branch(
            r, branch_col=branch_col, store_col=store,
            branch_map=branch_map, default_branch=default_branch,
        )
        if seen is not None and ident and r.get(ident) is not None:
            seen.add((branch_id, int(r[ident])))
        batch_objs.append(
            m.StockBatch(
                product_id=dst_pid,
                branch_id=branch_id,
                source_counter=int(r[counter]) if counter and r.get(counter) is not None else None,
                amount=max(_num(r.get(amount)), 0),  # CK_stock_amount: never negative
                buy_price=_num(r.get(buy)) if buy else 0,
                sell_price=_num(r.get(sell)) if sell else 0,
                tax_price=_num(r.get(tax)) if tax else 0,
                exp_date=_as_date(r.get(exp)) if exp else None,
            )
        )
        n += 1
    _bulk_add(dst, batch_objs)
    counts["stock_batches"] = n


def _load_branch_product_amount(insp, src, dst, counts, product_map, branch_map, default_branch,
                                seen: set | None = None) -> None:
    """Mirror eStock's Branches_Product_Amount (per-branch batch stock).

    This table REPEATS every head-office ``Product_Amount`` batch under its own
    branch and adds the other branch's batches on top (measured 2026-08-31:
    67,447 head-office + 67,434 the same again under branch 1 + 55,957 that are
    branch 2's alone = the 190,838 rows ProCare was holding, every one of them
    stamped branch 1). ``seen`` carries the head-office load's
    ``(branch, pa_id)`` batches so the repeats are skipped instead of doubling
    Elsanta's stock, and the branch is read from ``branch_id`` — never
    ``store_id``, which is 1 on every row here.

    Columns (confirmed against Elsanta 2026-08-31):
    - product_id, amount, buy_price, sell_price, tax_price, exp_date (like Product_Amount)
    - pa_id — the row id, and the ONLY safe dedup key (see _load_stock)
    - counter_id — the shelf number, kept as StockBatch.source_counter
    - branch_id — the branch; store_id is 1 on every row and must not be used
    """
    if not insp.has_table("Branches_Product_Amount"):
        return
    cols = {c["name"] for c in insp.get_columns("Branches_Product_Amount")}
    pid = _pick(cols, "product_id")
    store = _pick(cols, "store_id")
    branch_col = _pick(cols, "branch_id")
    counter = _pick(cols, "counter_id", "pa_id")  # try counter_id first, fallback to pa_id
    ident = _pick(cols, "pa_id")                  # the row id — see _load_stock
    amount = _pick(cols, "amount")
    buy = _pick(cols, "buy_price")
    sell = _pick(cols, "sell_price")
    tax = _pick(cols, "tax_price")
    exp = _pick(cols, "exp_date")

    rows = src.execute(text("SELECT * FROM Branches_Product_Amount")).mappings().all()
    n = 0
    n_dupes = 0
    batch_objs = []
    for r in rows:
        src_pid = int(r[pid]) if pid and r.get(pid) is not None else None
        dst_pid = product_map.get(src_pid)
        if dst_pid is None:
            continue
        branch_id = _row_branch(
            r, branch_col=branch_col, store_col=store,
            branch_map=branch_map, default_branch=default_branch,
        )
        if seen is not None and ident and r.get(ident) is not None:
            key = (branch_id, int(r[ident]))
            if key in seen:
                n_dupes += 1
                continue
            seen.add(key)
        batch_objs.append(
            m.StockBatch(
                product_id=dst_pid,
                branch_id=branch_id,
                source_counter=int(r[counter]) if counter and r.get(counter) is not None else None,
                amount=max(_num(r.get(amount)), 0),
                buy_price=_num(r.get(buy)) if buy else 0,
                sell_price=_num(r.get(sell)) if sell else 0,
                tax_price=_num(r.get(tax)) if tax else 0,
                exp_date=_as_date(r.get(exp)) if exp else None,
            )
        )
        n += 1
    counts["stock_batches_duplicates_skipped"] = (
        counts.get("stock_batches_duplicates_skipped", 0) + n_dupes
    )
    if batch_objs:
        counts.setdefault("stock_batches", 0)
        counts["stock_batches"] += n
        _bulk_add(dst, batch_objs)
        dst.flush()


def _load_cash_shift_closes(insp, src, dst, counts, branch_map, default_branch) -> None:
    """Mirror eStock's Cash_disk_close / Branches_Cash_disk_close (shift history).

    Reads both the centralized and branch-specific versions, accumulating shift records.
    Inferred columns: cdc_id, cdc_emp_id, cdc_shift_start_time, cdc_start_cash,
    cdc_curr_cash, cdc_act_cash, cdc_to_emp_id, cdc_trans_value, cdc_notice, branch_id.
    Only Branches_Cash_disk_close carries a branch_id; Cash_disk_close defaults to default_branch.
    """
    n = 0
    n_dupes = 0
    shift_objs = []
    # cash_shift_closes is never wiped between cycles and eStock ships the FULL
    # shift history on every read, so without an identity check each 5-minute
    # sync appended another complete copy — 26,558,791 rows for 3,625 real
    # shifts (7,327 copies) by 2026-09-01. Seed from what is already mirrored
    # and skip anything we hold: the loader becomes idempotent.
    seen: set[tuple[int, int]] = {
        (b, sid_)
        for b, sid_ in dst.execute(
            select(m.CashShiftClose.branch_id, m.CashShiftClose.source_shift_id)
        ).all()
        if sid_ is not None
    }
    for tbl in ("Cash_disk_close", "Branches_Cash_disk_close"):
        if not insp.has_table(tbl):
            continue
        cols = {c["name"] for c in insp.get_columns(tbl)}
        shift_id = _pick(cols, "cdc_id")
        emp_id = _pick(cols, "cdc_emp_id", "emp_id")
        cash_depot = _pick(cols, "cdc_cash_id")
        start_time = _pick(cols, "cdc_shift_start_time", "shift_start_time")
        start_cash = _pick(cols, "cdc_start_cash", "start_cash")
        current_cash = _pick(cols, "cdc_curr_cash", "current_cash")
        actual_cash = _pick(cols, "cdc_act_cash", "actual_cash")
        to_emp = _pick(cols, "cdc_to_emp_id")
        trans_val = _pick(cols, "cdc_trans_value", "trans_value")
        notice = _pick(cols, "cdc_notice", "notice")
        branch = _pick(cols, "branch_id")

        rows = src.execute(text(f"SELECT * FROM {tbl}")).mappings().all()
        for r in rows:
            branch_id = branch_map.get(int(r[branch])) if branch and r.get(branch) is not None else default_branch
            branch_id = branch_id or default_branch
            src_shift = int(r[shift_id]) if shift_id and r.get(shift_id) is not None else None
            if src_shift is not None:
                key = (branch_id, src_shift)
                if key in seen:
                    n_dupes += 1
                    continue
                seen.add(key)
            shift_objs.append(
                m.CashShiftClose(
                    branch_id=branch_id,
                    source_shift_id=src_shift,
                    employee_id=None,  # would need employee_map to resolve username
                    cash_depot_id=int(r[cash_depot]) if cash_depot and r.get(cash_depot) is not None else None,
                    shift_start_time=_as_dt(r.get(start_time)) if start_time else None,
                    start_cash=_num(r.get(start_cash)) if start_cash else 0,
                    current_cash=_num(r.get(current_cash)) if current_cash else 0,
                    actual_cash=_num(r.get(actual_cash)) if actual_cash else 0,
                    transfer_amount=_num(r.get(trans_val)) if trans_val else 0,
                    note=str(r.get(notice)).strip() if notice and r.get(notice) else None,
                )
            )
            n += 1
    counts["shift_closes"] = n
    counts["shift_closes_duplicates_skipped"] = n_dupes
    if shift_objs:
        dst.add_all(shift_objs)
        dst.flush()


def _load_branch_orders(insp, src, dst, counts, product_map, branch_map, default_branch) -> None:
    """Mirror eStock's Branch_order_header/details (inter-branch transfers).

    Inferred columns (header): bo_id, from_store_id, to_store_id, order_date, received_date, status
    Inferred columns (details): bol_id, bo_id (FK), product_id, qty, received_qty
    """
    if not insp.has_table("Branch_order_header"):
        counts["branch_orders"] = 0
        return

    # Load headers
    h_cols = {c["name"] for c in insp.get_columns("Branch_order_header")}
    h_id = _pick(h_cols, "bo_id")
    h_from_store = _pick(h_cols, "from_store_id", "from_branch_id")
    h_to_store = _pick(h_cols, "to_store_id", "to_branch_id")
    h_order_date = _pick(h_cols, "order_date")
    h_received_date = _pick(h_cols, "received_date")
    h_status = _pick(h_cols, "status")
    h_notice = _pick(h_cols, "notice")

    h_rows = src.execute(text("SELECT * FROM Branch_order_header")).mappings().all()
    # branch_order_headers is never wiped between cycles (its child
    # branch_order_lines IS), so re-inserting the full header set every
    # 5-minute sync grew it to 20,522,124 rows by 2026-09-01. Start from the
    # headers already mirrored and reuse them by source id.
    h_map: dict[int, int] = {
        int(sid_): oid
        for sid_, oid in dst.execute(
            select(m.BranchOrderHeader.source_order_id, m.BranchOrderHeader.order_id)
        ).all()
        if sid_ is not None
    }
    n_dupes = 0
    header_objs = []
    pending: list[tuple[int, object]] = []  # (source id, new header), resolved after flush
    for r in h_rows:
        src_order_id = int(r[h_id]) if h_id and r.get(h_id) is not None else None
        if src_order_id is not None and src_order_id in h_map:
            n_dupes += 1
            continue
        from_branch = branch_map.get(int(r[h_from_store])) if h_from_store and r.get(h_from_store) is not None else default_branch
        to_branch = branch_map.get(int(r[h_to_store])) if h_to_store and r.get(h_to_store) is not None else default_branch
        header = m.BranchOrderHeader(
            source_order_id=src_order_id,
            from_branch_id=from_branch or default_branch,
            to_branch_id=to_branch or default_branch,
            order_date=_as_date(r.get(h_order_date)) if h_order_date else None,
            received_date=_as_date(r.get(h_received_date)) if h_received_date else None,
            status=str(r.get(h_status)).lower().strip() if h_status and r.get(h_status) else "pending",
            note=str(r.get(h_notice)).strip() if h_notice and r.get(h_notice) else None,
        )
        header_objs.append(header)
        if src_order_id is not None:
            pending.append((src_order_id, header))

    if header_objs:
        dst.add_all(header_objs)
        dst.flush()
        # Map each source id to ITS OWN header. The previous
        # zip(h_map.keys(), header_objs) walked two differently-filtered lists —
        # h_map skipped headers without a source id, header_objs kept them — so
        # one such header shifted every later pairing and attached that order's
        # lines to the wrong header.
        for src_id_, obj in pending:
            h_map[src_id_] = obj.order_id

    # Load details if available
    if not insp.has_table("Branch_order_details"):
        counts["branch_orders"] = len(header_objs)
        return

    d_cols = {c["name"] for c in insp.get_columns("Branch_order_details")}
    d_id = _pick(d_cols, "bol_id")
    d_order_id = _pick(d_cols, "bo_id")
    d_product_id = _pick(d_cols, "product_id")
    d_qty = _pick(d_cols, "qty", "quantity")
    d_received_qty = _pick(d_cols, "received_qty")
    d_notice = _pick(d_cols, "notice")

    d_rows = src.execute(text("SELECT * FROM Branch_order_details")).mappings().all()
    line_objs = []
    for r in d_rows:
        src_order_id = int(r[d_order_id]) if d_order_id and r.get(d_order_id) is not None else None
        order_id = h_map.get(src_order_id)
        if not order_id:
            continue  # orphan line (no matching header)
        src_pid = int(r[d_product_id]) if d_product_id and r.get(d_product_id) is not None else None
        dst_pid = product_map.get(src_pid)
        if not dst_pid:
            continue  # orphan product
        line_objs.append(
            m.BranchOrderLine(
                order_id=order_id,
                product_id=dst_pid,
                quantity=max(_num(r.get(d_qty)), 0),
                received_qty=max(_num(r.get(d_received_qty)), 0) if d_received_qty else 0,
                note=str(r.get(d_notice)).strip() if d_notice and r.get(d_notice) else None,
            )
        )

    if line_objs:
        dst.add_all(line_objs)
        dst.flush()

    counts["branch_orders"] = len(header_objs)
    counts["branch_orders_duplicates_skipped"] = n_dupes


def _load_sales(
    insp, src, dst, counts, product_map, customer_map, branch_map, default_branch,
    employee_map=None, *, header_tbl, detail_tbl, returns: bool, count_key: str,
    window_cutoff: date | None = None, seen: set | None = None,
) -> None:
    """Mirror one sales header/detail table pair into ProCare.

    Called once per source table so the FULL eStock picture is captured: the
    head-office ``Sales_header`` AND the branch ``Branches_sales_header`` (which
    can hold MORE rows than the main table), plus the ``Back_*`` return variants.
    Counts ACCUMULATE across calls under ``count_key`` (sales / returns).

    ``seen`` is the caller's cross-table identity set. eStock ships every
    head-office bill TWICE — once in ``Sales_header`` and again in
    ``Branches_sales_header`` tagged ``branch_id = 1`` — while Mas-hala's bills
    exist ONLY in the Branches_* table. Mirroring both tables blindly therefore
    double-counted every Elsanta sale (measured 2026-08-31: 173 mirrored rows
    for a day that held 104 real bills, inflating revenue by the duplicated
    half). A bill is identified by ``(branch, source id)`` and never by the id
    alone — each branch numbers its bills from 1, so the two branches' id ranges
    overlap almost completely.
    """
    employee_map = employee_map or {}
    if not insp.has_table(header_tbl):
        counts.setdefault(count_key, 0)
        return

    hcols = {c["name"] for c in insp.get_columns(header_tbl)}
    sid = _pick(hcols, "sales_id")
    store = _pick(hcols, "store_id")
    branch_col = _pick(hcols, "branch_id")
    # Identity for the cross-table dedup: this header's OWN row id. For the
    # sales tables that is sales_id; Back_sales_header numbers its rows with
    # back_sales_id and carries sales_id only as the bill being returned, so
    # two returns against one bill must stay two rows.
    ident = _pick(hcols, "back_sales_id") or sid
    cust = _pick(hcols, "customer_id")
    cashier = _pick(hcols, "cashier_id")
    bill_date = _pick(hcols, "bill_date")
    insert_date = _pick(hcols, "insert_date")
    gross = _pick(hcols, "total_bill")
    net = _pick(hcols, "total_bill_net")
    disc = _pick(hcols, "total_disc_money")
    cash = _pick(hcols, "bill_cash")
    card = _pick(hcols, "network_money")
    change = _pick(hcols, "money_change")
    back = _pick(hcols, "back")

    # Chunked by sales_id range: the 313K-row Elsanta tables can't survive one
    # giant SELECT over the flaky WAN — each chunk fetch is retried on its own.
    # Incremental window: only the trailing N days cross the wire (a single
    # small retried query), matching what _wipe_branch_sales_window cleared.
    if window_cutoff is not None:
        date_cols = [c for c in (bill_date, insert_date) if c]
        if date_cols:
            date_expr = f"COALESCE({', '.join(date_cols)})" if len(date_cols) > 1 else date_cols[0]
            header_chunks = iter([
                src.execute(
                    text(f"SELECT * FROM {header_tbl} WHERE {date_expr} >= :cutoff"),
                    {"cutoff": window_cutoff},
                ).mappings().all()
            ])
        else:  # no date column to window on — fall back to the full pull
            header_chunks = _iter_rows(src, header_tbl, sid)
    else:
        header_chunks = _iter_rows(src, header_tbl, sid)

    # Keyed (branch, source sales_id): the id alone is ambiguous across branches.
    sale_id_map: dict[tuple[int, int], int] = {}
    # Detail tables with no branch column of their own (the head-office
    # Sales_details) can only be matched on the source id, so keep an
    # unambiguous-id fallback — an id this call mapped onto exactly one branch.
    by_src_id: dict[int, int | None] = {}
    n_headers = 0
    n_dupes = 0
    for hrows in header_chunks:
        pairs = []  # (src row, Sale) — only the rows actually kept
        for r in hrows:
            is_ret = returns or (_b(r.get(back)) if back else False)
            src_cust = int(r[cust]) if cust and r.get(cust) not in (None, 0) else None
            sale_dt = _as_dt(r.get(bill_date) if bill_date else None) or _as_dt(
                r.get(insert_date) if insert_date else None
            ) or datetime.now()
            # Window guard in Python too: if the table had no date column to
            # filter on server-side, the full fetch must NOT re-insert history
            # the window wipe didn't clear.
            if window_cutoff is not None and sale_dt.date() < window_cutoff:
                continue
            branch_id = _row_branch(
                r, branch_col=branch_col, store_col=store,
                branch_map=branch_map, default_branch=default_branch,
            )
            # Already mirrored from the other table of the pair — same branch,
            # same bill. Skip rather than insert the twin.
            if seen is not None and ident and r.get(ident) is not None:
                key = (branch_id, int(r[ident]))
                if key in seen:
                    n_dupes += 1
                    continue
                seen.add(key)
            # eStock cashier_id is a username (varchar) -> map to a ProCare employee.
            cashier_id = None
            if cashier and r.get(cashier) not in (None, "", 0):
                cashier_id = employee_map.get(str(r[cashier]).strip().lower())
            pairs.append((
                r,
                m.Sale(
                    branch_id=branch_id,
                    customer_id=customer_map.get(src_cust) if src_cust else None,
                    cashier_id=cashier_id,
                    sale_date=sale_dt,
                    total_gross=_num(r.get(gross)) if gross else 0,
                    total_discount=_num(r.get(disc)) if disc else 0,
                    total_net=_num(r.get(net)) if net else 0,
                    cash_paid=_num(r.get(cash)) if cash else 0,
                    card_paid=_num(r.get(card)) if card else 0,
                    change_given=_num(r.get(change)) if change else 0,
                    is_return=is_ret,
                ),
            ))
        dst.add_all([obj for _, obj in pairs])
        dst.flush()
        for r, obj in pairs:
            if sid and r.get(sid) is not None:
                src_id = int(r[sid])
                sale_id_map[(obj.branch_id, src_id)] = obj.sale_id
                # Second sighting of an id means a second branch: mark it
                # ambiguous so a branchless detail row is dropped rather than
                # attached to the wrong pharmacy's bill.
                by_src_id[src_id] = None if src_id in by_src_id else obj.sale_id
        n_headers += len(pairs)
    counts[count_key] = counts.get(count_key, 0) + n_headers
    counts[count_key + "_duplicates_skipped"] = (
        counts.get(count_key + "_duplicates_skipped", 0) + n_dupes
    )

    # Lines
    if not insp.has_table(detail_tbl):
        counts.setdefault(count_key + "_lines", 0)
        return
    dcols = {c["name"] for c in insp.get_columns(detail_tbl)}
    d_sid = _pick(dcols, "sales_id")
    d_branch = _pick(dcols, "branch_id")
    d_store = _pick(dcols, "store_id")
    d_pid = _pick(dcols, "product_id")
    d_amount = _pick(dcols, "amount", "back_amount")
    d_sell = _pick(dcols, "sell_price", "back_price")
    d_buy = _pick(dcols, "buy_price")
    d_disc = _pick(dcols, "disc_money")
    d_total = _pick(dcols, "total_sell")
    d_back = _pick(dcols, "back")

    # Window mode: scan only the window headers' id range — rows for ids that
    # happen to fall inside the range but aren't in the map are skipped below.
    detail_bounds = None
    if window_cutoff is not None:
        if not by_src_id:
            counts[count_key + "_lines"] = counts.get(count_key + "_lines", 0)
            return
        detail_bounds = (min(by_src_id), max(by_src_id))

    n_lines = 0
    for drows in _iter_rows(src, detail_tbl, d_sid, bounds=detail_bounds):
        line_rows = []
        for r in drows:
            sale_pk = None
            if d_sid and r.get(d_sid) is not None:
                src_id = int(r[d_sid])
                if d_branch or d_store:
                    # The detail row names its own branch — match it exactly.
                    # No fallback to the id-only map here: this table's twin
                    # headers were skipped as duplicates, and the same id in
                    # the OTHER branch would silently steal the line.
                    sale_pk = sale_id_map.get((
                        _row_branch(
                            r, branch_col=d_branch, store_col=d_store,
                            branch_map=branch_map, default_branch=default_branch,
                        ),
                        src_id,
                    ))
                else:
                    sale_pk = by_src_id.get(src_id)
            dst_pid = product_map.get(int(r[d_pid])) if d_pid and r.get(d_pid) is not None else None
            if sale_pk is None or dst_pid is None:
                continue
            qty = _num(r.get(d_amount))
            if qty <= 0:
                continue  # CK_saleline_amount: positive only
            sell_price = _num(r.get(d_sell)) if d_sell else 0
            total = _num(r.get(d_total)) if d_total else round(sell_price * qty, 2)
            line_rows.append(
                {
                    "sale_id": sale_pk,
                    "product_id": dst_pid,
                    "amount": qty,
                    "sell_price": sell_price,
                    "buy_price": _num(r.get(d_buy)) if d_buy else 0,
                    "disc_money": _num(r.get(d_disc)) if d_disc else 0,
                    "total_sell": total,
                    "is_return": returns or (_b(r.get(d_back)) if d_back else False),
                }
            )
        if line_rows:
            _bulk_insert(dst, m.SaleLine, line_rows)
        n_lines += len(line_rows)
    counts[count_key + "_lines"] = counts.get(count_key + "_lines", 0) + n_lines


def _load_purchases(
    insp, src, dst, counts, product_map, branch_map, default_branch,
    vendor_map=None, *, header_tbl="Purchase_header", detail_tbl="Purchase_details",
    window_cutoff: date | None = None, seen: set | None = None,
) -> None:
    """Mirror one purchase header/detail table pair. Called for both the
    head-office ``Purchase_header`` and the branch ``Branches_purchase_header``
    so purchase totals match eStock. Counts accumulate.

    Carries the same ``(branch, source id)`` dedup as ``_load_sales`` — the two
    tables overlap exactly the same way (measured 2026-08-31: 12,822 head-office
    bills, the identical 12,822 again under branch 1, plus 12,510 that are
    Mas-hala's alone), so mirroring both blindly double-counted every Elsanta
    purchase.
    """
    vendor_map = vendor_map or {}
    if not insp.has_table(header_tbl):
        counts.setdefault("purchases", 0)
        return
    hcols = {c["name"] for c in insp.get_columns(header_tbl)}
    pid = _pick(hcols, "purchase_id")
    vendor = _pick(hcols, "vendor_id")
    store = _pick(hcols, "store_id")
    branch_col = _pick(hcols, "branch_id")
    bill_date = _pick(hcols, "bill_date")
    bill_num = _pick(hcols, "bill_number")
    gross = _pick(hcols, "total_bill")
    disc = _pick(hcols, "bill_disc_money")
    tax = _pick(hcols, "bill_tax")
    back = _pick(hcols, "back")

    # Resolve the real vendor per row from the mapping; fall back to the first
    # vendor only when a row's vendor can't be resolved (keeps the FK valid).
    any_vendor = dst.scalars(select(m.Vendor.vendor_id)).first()
    if any_vendor is None:
        counts.setdefault("purchases", 0)
        return

    # Chunked by purchase_id range + retried per chunk (flaky-WAN safety).
    # Incremental window: only the trailing N days cross the wire.
    if window_cutoff is not None and bill_date:
        header_chunks = iter([
            src.execute(
                text(f"SELECT * FROM {header_tbl} WHERE {bill_date} >= :cutoff"),
                {"cutoff": window_cutoff},
            ).mappings().all()
        ])
    else:
        header_chunks = _iter_rows(src, header_tbl, pid)

    # Keyed (branch, source purchase_id) — see _load_sales for why the id alone
    # is not an identity — with an unambiguous-id fallback for the head-office
    # Purchase_details, which carries no branch column.
    purch_map: dict[tuple[int, int], int] = {}
    by_src_id: dict[int, int | None] = {}
    n_headers = 0
    n_dupes = 0
    for hrows in header_chunks:
        pairs = []  # (src row, Purchase) — only the rows actually kept
        for r in hrows:
            bd = (_as_date(r.get(bill_date)) if bill_date else None) or date.today()
            # Python-side window guard (see _load_sales): a dateless fallback
            # fetch must not re-insert history the window wipe didn't clear.
            if window_cutoff is not None and bd < window_cutoff:
                continue
            branch_id = _row_branch(
                r, branch_col=branch_col, store_col=store,
                branch_map=branch_map, default_branch=default_branch,
            )
            if seen is not None and pid and r.get(pid) is not None:
                key = (branch_id, int(r[pid]))
                if key in seen:
                    n_dupes += 1
                    continue
                seen.add(key)
            src_vendor = int(r[vendor]) if vendor and r.get(vendor) not in (None, 0) else None
            pairs.append((
                r,
                m.Purchase(
                    branch_id=branch_id,
                    vendor_id=vendor_map.get(src_vendor, any_vendor) if src_vendor else any_vendor,
                    bill_date=bd,
                    bill_number=r.get(bill_num) if bill_num else None,
                    total_gross=_num(r.get(gross)) if gross else 0,
                    total_discount=_num(r.get(disc)) if disc else 0,
                    total_tax=_num(r.get(tax)) if tax else 0,
                    is_return=_b(r.get(back)) if back else False,
                ),
            ))
        dst.add_all([obj for _, obj in pairs])
        dst.flush()
        for r, obj in pairs:
            if pid and r.get(pid) is not None:
                src_id = int(r[pid])
                purch_map[(obj.branch_id, src_id)] = obj.purchase_id
                by_src_id[src_id] = None if src_id in by_src_id else obj.purchase_id
        n_headers += len(pairs)
    counts["purchases"] = counts.get("purchases", 0) + n_headers
    counts["purchases_duplicates_skipped"] = (
        counts.get("purchases_duplicates_skipped", 0) + n_dupes
    )

    if not insp.has_table(detail_tbl):
        counts.setdefault("purchase_lines", 0)
        return
    dcols = {c["name"] for c in insp.get_columns(detail_tbl)}
    d_pid = _pick(dcols, "purchase_id")
    d_branch = _pick(dcols, "branch_id")
    d_store = _pick(dcols, "store_id")
    d_prod = _pick(dcols, "product_id")
    d_amount = _pick(dcols, "amount")
    d_bonus = _pick(dcols, "bouns", "bonus")
    d_buy = _pick(dcols, "buy_price")
    d_sell = _pick(dcols, "sell_price")
    d_exp = _pick(dcols, "exp_date")

    detail_bounds = None
    if window_cutoff is not None:
        if not by_src_id:
            counts["purchase_lines"] = counts.get("purchase_lines", 0)
            return
        detail_bounds = (min(by_src_id), max(by_src_id))

    n_lines = 0
    for drows in _iter_rows(src, detail_tbl, d_pid, bounds=detail_bounds):
        line_rows = []
        for r in drows:
            purch_pk = None
            if d_pid and r.get(d_pid) is not None:
                src_id = int(r[d_pid])
                if d_branch or d_store:
                    purch_pk = purch_map.get((
                        _row_branch(
                            r, branch_col=d_branch, store_col=d_store,
                            branch_map=branch_map, default_branch=default_branch,
                        ),
                        src_id,
                    ))
                else:
                    purch_pk = by_src_id.get(src_id)
            dst_prod = product_map.get(int(r[d_prod])) if d_prod and r.get(d_prod) is not None else None
            qty = _num(r.get(d_amount))
            if purch_pk is None or dst_prod is None or qty <= 0:
                continue
            line_rows.append(
                {
                    "purchase_id": purch_pk,
                    "product_id": dst_prod,
                    "amount": qty,
                    "bonus": _num(r.get(d_bonus)) if d_bonus else 0,
                    "buy_price": _num(r.get(d_buy)) if d_buy else 0,
                    "sell_price": _num(r.get(d_sell)) if d_sell else 0,
                    "exp_date": _as_date(r.get(d_exp)) if d_exp else None,
                }
            )
        if line_rows:
            _bulk_insert(dst, m.PurchaseLine, line_rows)
        n_lines += len(line_rows)
    counts["purchase_lines"] = counts.get("purchase_lines", 0) + n_lines


def _load_gl_accounts(insp, src, dst, counts) -> None:
    """Mirror eStock's ``Account_Tree`` (chart of accounts, شجرة الحسابات) verbatim.

    Read-only, upserted by source_id (account_id) so re-syncing never
    duplicates. ``account_major`` (parent) is kept as a loose source-id
    reference — no PK resolution needed for a read-only mirror. Columns are
    INFERRED from docs/CLAUDE_CODE_ESTOCK_STRUCTURE.md pending schema-dump
    confirmation from Elsanta; ``_pick`` tolerates the real names once known.
    Optional — absent source table = skipped, never an error."""
    if not insp.has_table("Account_Tree"):
        return
    cols = {c["name"] for c in insp.get_columns("Account_Tree")}
    a_id = _pick(cols, "account_id")
    a_code = _pick(cols, "account_code")
    a_ar = _pick(cols, "account_name_ar", "account_name")
    a_en = _pick(cols, "account_name_en")
    a_major = _pick(cols, "account_major")
    a_start = _pick(cols, "account_start_money")

    by_src = {a.source_id: a for a in dst.scalars(select(m.GlAccount)).all() if a.source_id is not None}
    n = 0
    for r in src.execute(text("SELECT * FROM Account_Tree")).mappings().all():
        sid = int(r.get(a_id)) if a_id and r.get(a_id) is not None else None
        obj = by_src.get(sid)
        if obj is None:
            obj = m.GlAccount(source_id=sid, name_ar="")
            dst.add(obj)
        obj.code = _str(r.get(a_code)) if a_code else obj.code
        obj.name_ar = _ar(r.get(a_ar) if a_ar else None, r.get(a_en) if a_en else None)
        obj.name_en = _str(r.get(a_en)) if a_en else None
        obj.parent_source_id = int(r[a_major]) if a_major and r.get(a_major) is not None else None
        obj.start_money = _num(r.get(a_start)) if a_start else 0
        n += 1
    dst.flush()
    counts["gl_accounts"] = n


def _load_gl_journal(insp, src, dst, counts) -> None:
    """Mirror eStock's ``Gedo_Financial`` (the central GL journal) verbatim.

    Every money movement in eStock posts here; this is a READ-ONLY historical
    mirror, not a reconstruction — ``from_type``/``to_type`` party-type codes
    are stored as eStock wrote them (NOT translated to ProCare's own
    ``LedgerEntry.account_type`` vocabulary, since the encoding is unconfirmed
    pending the schema-dump). Upserted by source_id (gf_id) so re-syncing never
    duplicates; NOT in ``_WIPE_ORDER`` — an append-only ledger survives full
    refreshes, same as shareholders/payroll. Optional — absent source table =
    skipped, never an error."""
    if not insp.has_table("Gedo_Financial"):
        return
    cols = {c["name"] for c in insp.get_columns("Gedo_Financial")}
    g_id = _pick(cols, "gf_id")
    g_code = _pick(cols, "gf_code")
    g_type = _pick(cols, "gf_gedo_type")
    g_value = _pick(cols, "gf_value")
    g_from_type = _pick(cols, "gf_from_type")
    g_from_id = _pick(cols, "gf_from_id")
    g_to_type = _pick(cols, "gf_to_type")
    g_to_id = _pick(cols, "gf_to_id")
    g_form = _pick(cols, "gf_form_type")
    g_notes = _pick(cols, "gf_notes")
    g_computer = _pick(cols, "gf_computer")
    g_cashier = _pick(cols, "gf_actual_cashier")

    existing = {e.source_id for e in dst.scalars(select(m.GlJournalEntry)).all() if e.source_id is not None}
    n = 0
    rows = []
    for r in src.execute(text("SELECT * FROM Gedo_Financial")).mappings().all():
        sid = int(r.get(g_id)) if g_id and r.get(g_id) is not None else None
        if sid is not None and sid in existing:
            continue  # already mirrored — journal entries are immutable once posted
        rows.append(
            m.GlJournalEntry(
                source_id=sid,
                code=_str(r.get(g_code)) if g_code else None,
                gedo_type=_str(r.get(g_type)) if g_type else None,
                value=_num(r.get(g_value)) if g_value else 0,
                from_type=_str(r.get(g_from_type)) if g_from_type else None,
                from_id=int(r[g_from_id]) if g_from_id and r.get(g_from_id) is not None else None,
                to_type=_str(r.get(g_to_type)) if g_to_type else None,
                to_id=int(r[g_to_id]) if g_to_id and r.get(g_to_id) is not None else None,
                form_type=_str(r.get(g_form)) if g_form else None,
                notes=_str(r.get(g_notes)) if g_notes else None,
                computer_name=_str(r.get(g_computer)) if g_computer else None,
                actual_cashier=_str(r.get(g_cashier)) if g_cashier else None,
            )
        )
        n += 1
    if rows:
        dst.add_all(rows)
        dst.flush()
    counts["gl_journal_entries"] = n


def _load_gl_adjustments(insp, src, dst, counts) -> None:
    """Mirror eStock's ``Tuning_accounts`` (manual GL adjustments, تسويات) verbatim.

    Unlike the five Gedo_* sub-ledgers (customers/vendors/branches/employee/
    installment — deferred: their balance-column names aren't documented
    anywhere, and guessing wrong there would silently zero a real balance),
    Tuning_accounts' columns ARE fully enumerated in
    docs/CLAUDE_CODE_ESTOCK_STRUCTURE.md, so this one is safe to mirror now.
    ``who_class``/``reason_source_id`` are eStock's own opaque codes, stored
    as-is (not translated) — same posture as GlJournalEntry.from_type/to_type.
    Upserted by source_id; not in ``_WIPE_ORDER``. Optional — absent source
    table = skipped, never an error."""
    if not insp.has_table("Tuning_accounts"):
        return
    cols = {c["name"] for c in insp.get_columns("Tuning_accounts")}
    t_id = _pick(cols, "Tuning_accounts_id")
    t_class = _pick(cols, "class")
    t_who_class = _pick(cols, "who_class")
    t_who_id = _pick(cols, "who_id")
    t_reason = _pick(cols, "Tuning_accounts_reason_id")
    t_money = _pick(cols, "Tuning_accounts_money")
    t_notes = _pick(cols, "notes")

    by_src = {a.source_id: a for a in dst.scalars(select(m.GlAdjustment)).all() if a.source_id is not None}
    n = 0
    for r in src.execute(text("SELECT * FROM Tuning_accounts")).mappings().all():
        sid = int(r.get(t_id)) if t_id and r.get(t_id) is not None else None
        obj = by_src.get(sid)
        if obj is None:
            obj = m.GlAdjustment(source_id=sid)
            dst.add(obj)
        obj.class_code = _str(r.get(t_class)) if t_class else None
        obj.who_class = _str(r.get(t_who_class)) if t_who_class else None
        obj.who_id = int(r[t_who_id]) if t_who_id and r.get(t_who_id) is not None else None
        obj.reason_source_id = int(r[t_reason]) if t_reason and r.get(t_reason) is not None else None
        obj.amount = _num(r.get(t_money)) if t_money else 0
        obj.notes = _str(r.get(t_notes)) if t_notes else None
        n += 1
    dst.flush()
    counts["gl_adjustments"] = n


# The five Gedo_* sub-ledger tables — CONFIRMED columns from the Elsanta
# schema-dump (2026-08-17), all sharing one shape: (table, party_type, id_col,
# gf_col, flag_col, type_col, party_col, for_him_col, for_me_col, notes_col).
# Gedo_employee/Gedo_branches/Gedo_installment have no notes column (None).
_GEDO_SUBLEDGER_TABLES = [
    ("Gedo_customers", "customer", "gc_id", "gf_id", "Flag", "gc_type", "customer_id", "gc_for_him", "gc_for_me", "notes"),
    ("Gedo_Vendors", "vendor", "gv_id", "gf_id", "Flag", "gv_type", "vendor_id", "gv_for_him", "gv_for_me", "notes"),
    ("Gedo_branches", "branch", "gb_id", "gf_id", "Flag", "gb_type", "branch_id", "gb_for_him", "gb_for_me", None),
    ("Gedo_employee", "employee", "ge_id", "gf_id", "flag", "ge_type", "emp_id", "ge_for_him", "ge_for_me", None),
    ("Gedo_installment", "installment", "gi_id", "f_id", "flag", "gi_type", "cu_id", "gi_for_him", "gi_for_me", None),
]


def _load_gl_subledgers(insp, src, dst, counts) -> None:
    """Mirror eStock's five Gedo_* per-party sub-ledger balance tables verbatim.

    Was deliberately deferred through the rest of Phase 7 — unlike every
    other GL mirror, a wrong guess at the balance-column names here would
    have silently stored a plausible-looking but zeroed/wrong balance
    instead of just skipping a field. Now safe: all columns confirmed via
    the Elsanta schema-dump (2026-08-17). ``party_source_id`` is kept
    unresolved (raw eStock id) for every party type, including branch —
    Gedo_branches.branch_id is eStock's OWN branch-entity id, a different
    namespace than ProCare's store_id-keyed branch_map, so resolving it
    needs its own mapping (out of scope here; kept consistent with the
    other four unresolved party types rather than resolved for some and not
    others). Upserted by (party_type, source_id); not in ``_WIPE_ORDER``.
    Each table is optional and has_table-guarded independently — a source
    missing one (e.g. Gedo_installment, unused on this pharmacy) just skips
    it, never an error."""
    existing = {
        (b.party_type, b.source_id): b
        for b in dst.scalars(select(m.GlSubledgerBalance)).all()
        if b.source_id is not None
    }
    total_n = 0
    for tbl, party_type, id_col, gf_col, flag_col, type_col, party_col, for_him_col, for_me_col, notes_col in _GEDO_SUBLEDGER_TABLES:
        if not insp.has_table(tbl):
            continue
        cols = {c["name"] for c in insp.get_columns(tbl)}
        c_id = _pick(cols, id_col)
        c_gf = _pick(cols, gf_col)
        c_flag = _pick(cols, flag_col)
        c_type = _pick(cols, type_col)
        c_party = _pick(cols, party_col)
        c_for_him = _pick(cols, for_him_col)
        c_for_me = _pick(cols, for_me_col)
        c_total = _pick(cols, "total")
        c_notes = _pick(cols, notes_col) if notes_col else None

        n = 0
        for r in src.execute(text(f"SELECT * FROM {tbl}")).mappings().all():
            sid = int(r.get(c_id)) if c_id and r.get(c_id) is not None else None
            key = (party_type, sid)
            obj = existing.get(key)
            if obj is None:
                obj = m.GlSubledgerBalance(party_type=party_type, source_id=sid)
                dst.add(obj)
                existing[key] = obj
            obj.gf_ref = _str(r.get(c_gf)) if c_gf else None
            obj.flag = int(r[c_flag]) if c_flag and r.get(c_flag) is not None else None
            obj.type_code = _str(r.get(c_type)) if c_type else None
            obj.party_source_id = int(r[c_party]) if c_party and r.get(c_party) is not None else None
            obj.for_him = _num(r.get(c_for_him)) if c_for_him else 0
            obj.for_me = _num(r.get(c_for_me)) if c_for_me else 0
            obj.total = _num(r.get(c_total)) if c_total else 0
            obj.notes = _str(r.get(c_notes)) if c_notes else None
            n += 1
        total_n += n
    dst.flush()
    counts["gl_subledger_balances"] = total_n


def _load_shareholders(insp, src, dst, counts) -> None:
    """Mirror eStock's ``company_Owner`` (shareholders) + ``Gedo_Dividends_paied``
    (dividends per year). Upserts by source id so re-syncing from either branch
    keeps a single owners register (company_Owner is company-wide). Both tables
    are optional — absent source = skipped, never an error."""
    if not insp.has_table("company_Owner"):
        return
    cols = {c["name"] for c in insp.get_columns("company_Owner")}
    c_id = _pick(cols, "coow_id")
    c_code = _pick(cols, "coow_code")
    c_ar = _pick(cols, "coow_name_ar", "coow_name")
    c_en = _pick(cols, "coow_name_en")
    c_tel = _pick(cols, "tel")
    c_mob = _pick(cols, "mobile")
    c_addr = _pick(cols, "address")
    c_cur = _pick(cols, "coow_current_money")
    c_start = _pick(cols, "coow_start_money")
    c_active = _pick(cols, "active")
    c_deleted = _pick(cols, "deleted")

    # Existing shareholders by source id, to upsert rather than duplicate.
    by_src = {s.source_id: s for s in dst.scalars(select(m.Shareholder)).all() if s.source_id is not None}
    src_to_pk: dict[int, int] = {}
    n_owners = 0
    for r in src.execute(text("SELECT * FROM company_Owner")).mappings().all():
        if c_deleted and _b(r.get(c_deleted)):
            continue
        sid = int(r.get(c_id)) if c_id and r.get(c_id) is not None else None
        obj = by_src.get(sid)
        if obj is None:
            obj = m.Shareholder(source_id=sid, name_ar="")
            dst.add(obj)
        obj.code = _str(r.get(c_code)) if c_code else obj.code
        obj.name_ar = _ar(r.get(c_ar) if c_ar else None, r.get(c_en) if c_en else None)
        obj.name_en = _str(r.get(c_en)) if c_en else None
        obj.tel = _str(r.get(c_tel)) if c_tel else None
        obj.mobile = _str(r.get(c_mob)) if c_mob else None
        obj.address = _str(r.get(c_addr)) if c_addr else None
        obj.current_capital = _num(r.get(c_cur)) if c_cur else 0
        obj.start_capital = _num(r.get(c_start)) if c_start else 0
        obj.is_active = _b(r.get(c_active)) if c_active else True
        dst.flush()
        if sid is not None:
            src_to_pk[sid] = obj.shareholder_id
        n_owners += 1
    counts["shareholders"] = n_owners

    # Dividends (optional).
    if not insp.has_table("Gedo_Dividends_paied"):
        return
    dcols = {c["name"] for c in insp.get_columns("Gedo_Dividends_paied")}
    d_id = _pick(dcols, "dividends_id")
    d_owner = _pick(dcols, "coow_id")
    d_year = _pick(dcols, "yaer_id", "year_id", "year")
    d_gf = _pick(dcols, "gf_id")
    d_money = _pick(dcols, "paied_money", "paid_money")

    existing_div = {d.source_id for d in dst.scalars(select(m.DividendPayment)).all() if d.source_id is not None}
    n_div = 0
    for r in src.execute(text("SELECT * FROM Gedo_Dividends_paied")).mappings().all():
        dsid = int(r.get(d_id)) if d_id and r.get(d_id) is not None else None
        if dsid is not None and dsid in existing_div:
            continue  # already mirrored
        owner_src = int(r.get(d_owner)) if d_owner and r.get(d_owner) is not None else None
        shareholder_pk = src_to_pk.get(owner_src)
        if shareholder_pk is None:
            continue  # dividend for an unknown/deleted owner — skip
        dst.add(
            m.DividendPayment(
                source_id=dsid,
                shareholder_id=shareholder_pk,
                year=int(r.get(d_year)) if d_year and r.get(d_year) is not None else None,
                gf_id=int(r.get(d_gf)) if d_gf and r.get(d_gf) is not None else None,
                amount=_num(r.get(d_money)) if d_money else 0,
            )
        )
        n_div += 1
    dst.flush()
    counts["dividends"] = n_div


def _load_payroll(insp, src, dst, counts) -> None:
    """Mirror eStock's ``Employee_salary`` (monthly payroll) into ProCare.

    ProCare employees are matched to eStock by USERNAME (they carry no source
    ``emp_id``), so this resolves ``Employee_salary.emp_id`` → username (via the
    source ``Employee`` master) → ProCare ``employee_id``. Upserts by
    ``salary_id`` so re-syncing keeps one row per source payroll record.
    Optional — absent source table = skipped, never an error. Net is recomputed
    (basic + commission + over − deduction − absence − advance) so it stays
    self-consistent regardless of the source's own ``total``."""
    if not insp.has_table("Employee_salary") or not insp.has_table("Employee"):
        return

    # emp_id -> username, from the source Employee master.
    ecols = {c["name"] for c in insp.get_columns("Employee")}
    e_id = _pick(ecols, "emp_id")
    e_user = _pick(ecols, "username")
    if e_id is None or e_user is None:
        return
    empid_to_user: dict[int, str] = {}
    for r in src.execute(text(f"SELECT {e_id}, {e_user} FROM Employee")).mappings().all():
        if r.get(e_id) is not None and r.get(e_user):
            empid_to_user[int(r.get(e_id))] = str(r.get(e_user)).strip().lower()

    # username -> ProCare employee_id.
    user_to_pk = {
        (u or "").strip().lower(): eid
        for eid, u in dst.execute(select(m.Employee.employee_id, m.Employee.username)).all()
        if u
    }

    cols = {c["name"] for c in insp.get_columns("Employee_salary")}
    s_id = _pick(cols, "salary_id")
    s_emp = _pick(cols, "emp_id")
    s_basic = _pick(cols, "basic_salary")
    s_comm = _pick(cols, "emp_commission")
    s_over = _pick(cols, "emp_over_commission")
    s_ded = _pick(cols, "emp_deduction")
    s_abs = _pick(cols, "emp_absence_money")
    s_total = _pick(cols, "total")
    s_month = _pick(cols, "month_salary")
    s_adv = _pick(cols, "cash_advance")
    s_state = _pick(cols, "state")

    by_src = {p.source_id: p for p in dst.scalars(select(m.PayrollRecord)).all() if p.source_id is not None}
    n = 0
    for r in src.execute(text("SELECT * FROM Employee_salary")).mappings().all():
        emp_pk = user_to_pk.get(empid_to_user.get(int(r.get(s_emp)))) if s_emp and r.get(s_emp) is not None else None
        if emp_pk is None:
            continue  # payroll row for an employee ProCare doesn't know — skip
        basic = _num(r.get(s_basic)) if s_basic else 0
        comm = _num(r.get(s_comm)) if s_comm else 0
        over = _num(r.get(s_over)) if s_over else 0
        ded = _num(r.get(s_ded)) if s_ded else 0
        absence = _num(r.get(s_abs)) if s_abs else 0
        advance = _num(r.get(s_adv)) if s_adv else 0
        net = round(basic + comm + over - ded - absence - advance, 2)

        sid = int(r.get(s_id)) if s_id and r.get(s_id) is not None else None
        obj = by_src.get(sid)
        if obj is None:
            obj = m.PayrollRecord(source_id=sid, employee_id=emp_pk)
            dst.add(obj)
        obj.employee_id = emp_pk
        obj.period = _str(r.get(s_month)) if s_month else None
        obj.state = _str(r.get(s_state)) if s_state else None
        obj.basic_salary = basic
        obj.commission = comm
        obj.over_commission = over
        obj.deduction = ded
        obj.absence_money = absence
        obj.cash_advance = advance
        obj.source_total = _num(r.get(s_total)) if s_total else 0
        obj.net = net
        n += 1
    dst.flush()
    counts["payroll"] = n


def _estock_empid_to_pk(insp, src, dst) -> dict[int, int]:
    """{eStock emp_id -> ProCare employee_id}, bridged via username (ProCare
    employees carry no source id). Empty if the source ``Employee`` master or a
    username column is absent."""
    if not insp.has_table("Employee"):
        return {}
    ecols = {c["name"] for c in insp.get_columns("Employee")}
    e_id = _pick(ecols, "emp_id")
    e_user = _pick(ecols, "username")
    if e_id is None or e_user is None:
        return {}
    empid_to_user: dict[int, str] = {}
    for r in src.execute(text(f"SELECT {e_id}, {e_user} FROM Employee")).mappings().all():
        if r.get(e_id) is not None and r.get(e_user):
            empid_to_user[int(r.get(e_id))] = str(r.get(e_user)).strip().lower()
    user_to_pk = {
        (u or "").strip().lower(): eid
        for eid, u in dst.execute(select(m.Employee.employee_id, m.Employee.username)).all()
        if u
    }
    return {eid: user_to_pk[u] for eid, u in empid_to_user.items() if u in user_to_pk}


def _load_salary_advances(insp, src, dst, counts) -> None:
    """Mirror eStock's ``Employee_cash_advance`` (سلف) — a detail ledger of
    individual salary advances, separate from the monthly payroll roll-up.
    Resolves ``emp_id`` → ProCare employee (via username), upserts by
    ``cash_advance_id``. Optional — absent source = skipped."""
    if not insp.has_table("Employee_cash_advance"):
        return
    empid_to_pk = _estock_empid_to_pk(insp, src, dst)
    cols = {c["name"] for c in insp.get_columns("Employee_cash_advance")}
    a_id = _pick(cols, "cash_advance_id")
    a_emp = _pick(cols, "emp_id")
    a_money = _pick(cols, "cash_advance")
    a_type = _pick(cols, "type")

    by_src = {a.source_id: a for a in dst.scalars(select(m.SalaryAdvance)).all() if a.source_id is not None}
    n = 0
    for r in src.execute(text("SELECT * FROM Employee_cash_advance")).mappings().all():
        emp_pk = empid_to_pk.get(int(r.get(a_emp))) if a_emp and r.get(a_emp) is not None else None
        if emp_pk is None:
            continue  # advance for an employee ProCare doesn't know — skip
        sid = int(r.get(a_id)) if a_id and r.get(a_id) is not None else None
        obj = by_src.get(sid)
        if obj is None:
            obj = m.SalaryAdvance(source_id=sid, employee_id=emp_pk)
            dst.add(obj)
        obj.employee_id = emp_pk
        obj.amount = _num(r.get(a_money)) if a_money else 0
        obj.advance_type = _str(r.get(a_type)) if a_type else None
        n += 1
    dst.flush()
    counts["salary_advances"] = n


def _load_treasury(insp, src, dst, counts, branch_map, default_branch) -> None:
    """Mirror eStock cash vaults (``Cash_depots``) into ProCare's ledger so the
    treasury screen shows real balances instead of zero.

    Each depot's current balance becomes one ``cash``/``bank`` ledger entry
    (positive → debit, negative → credit). ``_WIPE_ORDER`` clears LedgerEntry on
    every full refresh, so re-running never double-counts.
    """
    # Treasury = the head-office server's own live vaults in ``Cash_depots``
    # (verified against the owner's report: Elsanta Cash_depots reconciles to the
    # "cash accounts by branch" total). ``Branches_cash_depots`` is a SEPARATE
    # aggregation on the same server that overcounts — do NOT include it.
    #
    # Depot balances are a SNAPSHOT, so the previous snapshot for this branch is
    # cleared first. The full wipe already clears LedgerEntry, but the
    # branch-scoped/incremental cycles do NOT — without this delete every cycle
    # stacked another copy of each depot balance and the treasury screen crept
    # upward. Only ``ref_type='depot'`` rows go; ProCare-native vouchers
    # (صرف/توريد) carry other ref_types and are never touched.
    dst.execute(
        delete(m.LedgerEntry).where(
            m.LedgerEntry.ref_type == "depot", m.LedgerEntry.branch_id == default_branch
        )
    )
    entries = []
    for tbl in ("Cash_depots",):
        if not insp.has_table(tbl):
            continue
        cols = {c["name"] for c in insp.get_columns(tbl)}
        name = _pick(cols, "cash_depot_name_ar", "cash_depot_name_en")
        money_col = _pick(cols, "cash_depot_current_money")
        bank = _pick(cols, "bank_id")
        if not money_col:
            continue
        for r in src.execute(text(f"SELECT * FROM {tbl}")).mappings().all():
            bal = _num(r.get(money_col))
            is_bank = bool(r.get(bank)) if bank else False
            entries.append(
                m.LedgerEntry(
                    branch_id=default_branch,
                    account_type="bank" if is_bank else "cash",
                    ref_type="depot",
                    debit=bal if bal >= 0 else 0,
                    credit=-bal if bal < 0 else 0,
                    note=(str(r.get(name)) if name else "depot"),
                )
            )
    if entries:
        dst.add_all(entries)
        dst.flush()
    counts["treasury_depots"] = len(entries)


def preflight() -> dict:
    """On-prem connectivity + read-only check before a first mirror run.

    Confirms (1) we can connect to EVERY configured eStock source, and (2) EACH
    login truly cannot write — a blocked write is the SUCCESS case (roadmap
    Phase 0). Run this on a machine that can reach the DB(s).

    For multi-source setups (branch servers), reports per-source connectivity
    and discovered store_ids so the operator can map them via ESTOCK_STORE_BRANCH_MAP.
    """
    sources = settings.estock_sources()
    if not sources:
        return {"ok": False, "reason": "No eStock credentials configured (config/connections.json)."}

    if len(sources) == 1:
        # Single-source: return flat result for backward compat.
        return _preflight_one(sources[0])

    # Multi-source: report per-source so the operator knows which server maps to which branch.
    results = {}
    all_ok = True
    for src_block in sources:
        name = src_block.get("name", "unknown")
        results[name] = _preflight_one(src_block)
        if not results[name]["ok"]:
            all_ok = False

    return {
        "ok": all_ok,
        "multi_source": True,
        "sources": results,
        "hint": "Map each source's store_ids to branches via ESTOCK_STORE_BRANCH_MAP, ESTOCK2_STORE_BRANCH_MAP, etc.; "
        "unmapped ids auto-create STORE<id> branches.",
    }


def _preflight_one(source_block: dict) -> dict:
    """Test connectivity + read-only for one eStock source."""
    url = _get_odbc_url(source_block)
    if not url:
        return {"ok": False, "reason": f"Missing credentials in source block (database={source_block.get('database')})."}
    try:
        src = create_engine(url, echo=False)
        with src.connect() as c:
            c.execute(text("SELECT 1"))
            insp = inspect(src)
            tables = insp.get_table_names()
            # Discover the branches present so the operator can name them.
            try:
                store_ids = sorted(_distinct_store_ids(insp, c))
            except Exception:  # noqa: BLE001
                store_ids = []
        result = {
            "ok": True,
            "connected": True,
            "source_tables": len(tables),
            "store_ids_found": store_ids,
            "hint": "Map each store_id to a branch code via store_branch_map.",
        }
        # Verify the login is read-only: a write MUST be rejected.
        try:
            with src.begin() as c:
                c.execute(text("CREATE TABLE procare_write_probe_x (n INT)"))
            result["read_only"] = False
            result["warning"] = "Login CAN write — use a dedicated READ-ONLY login before mirroring."
            with src.begin() as c:  # best-effort cleanup if it did create
                c.execute(text("DROP TABLE procare_write_probe_x"))
        except Exception:
            result["read_only"] = True  # write blocked == good
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "connected": False, "error": f"{type(e).__name__}: {e}"}


def _get_odbc_url(block: dict) -> str | None:
    """Build a pyodbc SQLAlchemy URL from a connection block, or None if not configured.

    Uses config.py's internal helper directly since that one is the canonical impl.
    """
    from app.config import _odbc_url as config_odbc_url

    return config_odbc_url(block)


def sync_customers_only(source_engine) -> dict:
    """Mirror ONLY the customer register from ``source_engine``.

    Used when a secondary branch server contributes customer names to the
    shared register but its operational data (products, stock, sales,
    purchases) already arrives from the main head-office server — syncing it
    twice would duplicate rows and waste the branch server's capacity.

    Customers are matched and updated in place (``dedup`` + ``update_on_match``)
    so the register stays single-copy across sources, exactly as in a
    ``branch_scoped`` mirror. Nothing is wiped: this mode never touches a
    branch's transactional rows, so it is safe to interleave with the main
    source's full/incremental cycles.
    """
    insp = inspect(source_engine)
    src = _ResilientSource(source_engine)
    try:
        counts: dict = {"sync_mode": "customers_only"}
        with SessionLocal() as dst:
            _load_customers(insp, src, dst, counts, dedup=True, update_on_match=True)
            dst.commit()
        return counts
    finally:
        src.close()


def run_full_load() -> dict:
    """Entry point for the Phase-1+ full mirror against live eStock DB(s).

    For single-source: full refresh of ProCare's data from one eStock server.
    For multi-source: full refresh of EACH branch server's data independently
    (branch_scoped=True so sources never wipe each other).

    Refuses to run (rather than guess) until a real read-only eStock login is
    configured, keeping the read-only guardrail explicit and safe.
    """
    sources = settings.estock_sources()
    if not sources:
        return {
            "ran": False,
            "reason": "No read-only eStock credentials configured. "
            "Fill config/connections.json:estock_source or estock_sources, then re-run. "
            "The system runs on its own seeded data until then.",
        }

    Base.metadata.create_all(engine)

    all_counts: dict = {}
    for src_block in sources:
        url = _get_odbc_url(src_block)
        if not url:
            continue
        try:
            # Multi-source: each source is branch-scoped so they don't wipe each other.
            source_engine = create_engine(url, echo=False)
            store_map = src_block.get("store_branch_map")
            with SessionLocal() as dst:
                counts = mirror(
                    source_engine, dst, store_map, branch_scoped=len(sources) > 1
                )
            all_counts[src_block.get("name", "source")] = counts
        except Exception as e:  # noqa: BLE001
            all_counts[src_block.get("name", "source")] = {
                "error": f"{type(e).__name__}: {e}"
            }

    return {
        "ran": bool(all_counts),
        "source": "eStock (read-only)" + (" — multi-branch" if len(sources) > 1 else ""),
        "counts": all_counts,
    }


def import_branch_backup(database: str, branch_code: str, *, append: bool = True) -> dict:
    """Import one restored branch backup into ProCare, mapped to ``branch_code``.

    ``database`` is a database on the SAME SQL Server as ``estock_source`` (e.g.
    ``stock_elsanta`` or ``stock_mashala`` restored from a .bak). Append by
    default so branches accumulate — import Elsanta, then Mashala — sharing one
    deduped catalogue. Pass ``append=False`` to start ProCare fresh first.
    """
    url = settings.estock_url_for_database(database)
    if not url:
        return {
            "ran": False,
            "reason": "estock_source credentials are not set in config/connections.json — "
            "fill server/username/password there (same login used for the mirror).",
        }
    Base.metadata.create_all(engine)
    source_engine = create_engine(url, echo=False)
    try:
        with SessionLocal() as dst:
            counts = mirror(source_engine, dst, wipe=not append, force_branch_code=branch_code)
    finally:
        source_engine.dispose()
    return {"ran": True, "database": database, "branch": branch_code.strip().upper(),
            "mode": "append" if append else "fresh", "counts": counts}



# ============================================================================
# 100% eStock coverage: raw mirror of all tables not handled by dedicated
# _load_* functions above. One EstockRawMirror row per source row, JSON-encoded,
# deduped on (source_table, source_id). Read-only SELECT on eStock — never a
# write. Takes ProCare from "28 of 114 tables" to 100% coverage without hand-
# modelling ~86 more tables.
# ============================================================================

_RAW_ROWS_PER_CHUNK = 20_000   # rows we AIM to pull per SELECT
_RAW_CHUNK_MIN = 20_000        # narrowest id-range window
_RAW_CHUNK_MAX = 5_000_000     # widest, so a dense patch cannot blow up memory
_RAW_ANTIJOIN_CHUNK = 900      # IN(...) size; SQL Server caps a batch at 2100 params

def _raw_mirror_enabled() -> bool:
    return str(os.environ.get("RAW_MIRROR", "1")).strip().lower() in ("1", "true", "yes", "on")

def _raw_refresh_max_rows() -> int:
    try: return max(0, int(os.environ.get("RAW_MIRROR_REFRESH_MAX_ROWS", "50000")))
    except ValueError: return 50_000

def _raw_skip_above_rows() -> int:
    try: return max(0, int(os.environ.get("RAW_MIRROR_SKIP_ABOVE_ROWS", "0")))
    except ValueError: return 0

def _raw_try_lock(dst) -> bool:
    """Take an exclusive advisory lock on the raw pass, without waiting.

    The backend syncs every 5 minutes and an off-peak backfill of the change logs
    runs for far longer than one cycle, so without this the two passes read and
    insert the same keys at once — each with its own anti-join snapshot, so the
    duplicates they create are the kind the anti-join cannot see.

    ``@LockOwner='Transaction'`` releases the lock when the mirror's transaction
    commits or rolls back, so a crashed backfill cannot strand it. Anything other
    than SQL Server (the SQLite test source) has no contention to arbitrate and is
    granted it. A lock that cannot be taken is never allowed to fail a sync — on
    error the pass proceeds, exactly as it did before this existed.
    """
    try:
        if dst.bind is None or dst.bind.dialect.name != "mssql":
            return True
        r = dst.execute(text(
            "DECLARE @r int; EXEC @r = sp_getapplock @Resource = 'procare_raw_mirror', "
            "@LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 0; SELECT @r"
        )).scalar()
        return int(r) >= 0
    except Exception:
        return True


def _raw_watermark(table: str) -> int | None:
    try:
        with SessionLocal() as s:
            r = s.execute(text("SELECT last_value FROM estock_raw_watermark WHERE source_table = :t"), {"t": table}).first()
            return int(r[0]) if r else None
    except Exception: return None

def _raw_save_watermark(table: str, value: int) -> None:
    try:
        with SessionLocal() as s:
            s.execute(text("IF NOT EXISTS (SELECT 1 FROM estock_raw_watermark WHERE source_table = :t) INSERT INTO estock_raw_watermark (source_table, last_value) VALUES (:t, :v) ELSE UPDATE estock_raw_watermark SET last_value = :v, updated_at = GETDATE() WHERE source_table = :t"), {"t": table, "v": value})
            s.commit()
    except Exception: pass

def _scalar(value) -> str:
    if value is None: return ""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value): return ""
        value = int(value) if float(value).is_integer() else value
    if hasattr(value, "isoformat"): return value.isoformat()
    if hasattr(value, "quantize"): return str(value)
    return str(value)

def _row_to_json(row) -> str:
    d = {}
    for k, v in row.items():
        if isinstance(v, bytes): d[k] = v.hex()
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)): d[k] = None
        elif hasattr(v, "isoformat"): d[k] = v.isoformat()
        elif hasattr(v, "quantize"): d[k] = float(v)
        else: d[k] = v
    return json.dumps(d, ensure_ascii=False)

def _pk_cols(insp, table: str) -> list[str]:
    """Every primary-key column, in constraint order, when all of them are numeric.

    Returning the *whole* key matters: keying on the first column alone collapsed
    ``Branches_Product_amount_Change``'s 1,052,383 rows onto its two distinct
    ``branch_id`` values.  A non-numeric member means the table cannot be read
    forward safely, so the caller falls back to the row-digest path.
    """
    try:
        cols = insp.get_pk_constraint(table).get("constrained_columns", []) or []
    except Exception:
        return []
    if not cols:
        return []
    try:
        types = {c["name"]: str(c["type"]).upper() for c in insp.get_columns(table)}
    except Exception:
        return []
    for name in cols:
        t = types.get(name, "")
        if not ("INT" in t or "DECIMAL" in t or "NUMERIC" in t):
            return []
    return list(cols)


def _raw_key(row, pk_cols: list[str]) -> str:
    """Dedup key for one source row: every primary-key column, in order.

    eStock ids are DECIMAL(18,0), so values go through ``_scalar`` — otherwise one
    cycle renders an id as '123' and the next as '1.23E+2' and every row looks new.
    A key longer than the 60-char ``source_id`` column is hashed, never truncated:
    truncation would make distinct rows collide and silently drop data.
    """
    key = "|".join(_scalar(row.get(c)) for c in pk_cols)
    return hashlib.sha1(key.encode("utf-8")).hexdigest() if len(key) > 60 else key


def _row_digest(row) -> str:
    """Stable scalar rendering of a whole row — the dedup key for keyless tables."""
    return json.dumps({k: _scalar(v) for k, v in row.items()}, ensure_ascii=False)


def _raw_forward_col(src, table: str, pk_cols: list[str]) -> str | None:
    """Which key column to read forward on.

    In a composite eStock key the first column is the low-cardinality one
    (``branch_id``, MAX 2) and watermarking on it strands the table permanently:
    after one cycle ``MAX(branch_id) <= last_value`` and every later cycle
    short-circuits.  The column with the widest range is the one that advances.
    """
    if not pk_cols:
        return None
    if len(pk_cols) == 1:
        return pk_cols[0]
    best, best_max = None, None
    for c in pk_cols:
        try:
            raw = src.execute(text(f"SELECT MAX({c}) FROM {table}")).scalar()
            m = int(raw) if raw is not None else None
        except Exception:
            continue
        if m is None:
            continue
        if best_max is None or m > best_max:
            best, best_max = c, m
    return best


def _raw_save_watermark_in(dst, table: str, value: int) -> None:
    """Advance the watermark **in the caller's session**, so it commits with the
    rows it describes.  A watermark committed separately can end up ahead of rows
    that were rolled back, and those rows would then never be read again."""
    row = dst.get(EstockRawWatermark, table)
    if row is None:
        dst.add(EstockRawWatermark(source_table=table, last_value=int(value)))
    else:
        row.last_value = int(value)
        row.updated_at = datetime.now()


def _source_table_branch_id(insp, src, tbl: str, bm: dict[int, int] | None, db: int | None) -> dict[int, int] | None:
    """For tables with a ``store_id`` column, return a `{source_store_id: branch_id}`
    map so rows get tagged to the right ProCare branch.

    ``src`` may be a raw connection OR a ``_ResilientSource`` — both expose
    ``.execute()``.
    """
    if not insp.has_table(tbl): return None
    if "store_id" not in {c["name"] for c in insp.get_columns(tbl)}: return None
    try:
        rows = src.execute(text("SELECT DISTINCT store_id FROM " + tbl)).mappings().all()
    except Exception: return None
    sids = {int(r["store_id"]) for r in rows if r["store_id"] is not None}
    if not sids: return None
    if not bm: return {s: db for s in sids} if db is not None else None
    return {s: bm.get(s, db) for s in sids}


def _mirror_one_raw_table(insp, src, dst, tbl: str, bm: dict[int, int] | None = None,
                          max_ref: int = 50_000) -> int:
    """Mirror ONE source table into ``estock_raw_mirror``. Returns rows added.

    Three shapes, because eStock has three:
      * **no usable key** — dedup on the row digest, refreshed wholesale;
      * **keyed and small** (<= ``max_ref``) — refreshed wholesale, so the tables
        eStock edits in place (balances, config) come back verbatim;
      * **keyed and large** — read forward from a watermark and anti-joined
        against the keys already held, so a 5-minute cadence stays cheap.

    Raises on a source it cannot read; the caller runs it inside a SAVEPOINT.
    """
    try:
        est = int(src.execute(text("SELECT COUNT(*) FROM " + tbl)).scalar() or 0)
    except Exception:
        est = 0
    pk_cols = _pk_cols(insp, tbl)

    def _branch_of(row):
        if bm and row.get("store_id") is not None:
            try:
                return bm.get(int(row["store_id"]))
            except (TypeError, ValueError):
                return None
        return None

    new: list = []
    n_new = 0

    def _flush(force=False):
        nonlocal new
        if new and (force or len(new) >= _RAW_ANTIJOIN_CHUNK):
            dst.add_all(new)
            new = []

    forward = _raw_forward_col(src, tbl, pk_cols) if pk_cols and est > max_ref else None

    # -- wholesale refresh: keyless, small, or no column safe to read forward on
    if not forward:
        dst.execute(text("DELETE FROM estock_raw_mirror WHERE source_table = :t"), {"t": tbl})
        rows = src.execute(text("SELECT * FROM " + tbl)).mappings().all()
        seen: set = set()
        for row in rows:
            digest = _row_digest(row)
            sid = _raw_key(row, pk_cols) if pk_cols else None
            dedup = sid if pk_cols else digest
            if dedup in seen:
                continue
            seen.add(dedup)
            new.append(EstockRawMirror(source_table=tbl, source_id=sid,
                                       raw=_row_to_json(row) if pk_cols else digest,
                                       branch_id=_branch_of(row)))
            n_new += 1
            _flush()
        _flush(force=True)
        return n_new

    # -- incremental: read forward, anti-join against what is already held
    existing = {
        "" if r["source_id"] is None else str(r["source_id"])
        for r in dst.execute(
            text("SELECT source_id FROM estock_raw_mirror WHERE source_table = :t"),
            {"t": tbl},
        ).mappings()
    }

    wm = _raw_watermark(tbl)
    if wm is None:
        # First fill: start below the smallest key, not at 0. eStock does issue
        # negative ids (Branches_shortcoming.product_id reaches -21670), and a
        # loop anchored at 0 would skip every row beneath it without a word.
        try:
            lo = int(src.execute(text(f"SELECT MIN({forward}) FROM {tbl}")).scalar()) - 1
        except Exception:
            lo = 0
    else:
        lo = int(wm)

    try:
        hi = int(src.execute(text(f"SELECT MAX({forward}) FROM {tbl}")).scalar())
    except Exception:
        hi = lo

    if hi > lo:
        # Size the window by key DENSITY, not by row count: Branches_convert_details
        # holds 62K rows spread over 7.3M ids, so a fixed 20K-id step would issue
        # ~365 requests, nearly all of them empty.
        span = hi - lo
        width = int(span / est * _RAW_ROWS_PER_CHUNK) if est > 0 and span > 0 else _RAW_ROWS_PER_CHUNK
        width = max(_RAW_CHUNK_MIN, min(_RAW_CHUNK_MAX, width))
        # `hi + 1`, so the row AT the maximum key is always inside a window. With
        # `range(lo, hi, ...)` a span that is an exact multiple of the width ends
        # on `< hi`, dropping that row -- and the watermark still advances past it,
        # so it is never read again.
        for start in range(lo, hi + 1, width):
            end = min(start + width, hi + 1)
            rows = src.execute(
                text(f"SELECT * FROM {tbl} WHERE {forward} >= :lo AND {forward} < :hi"),
                {"lo": start, "hi": end},
            ).mappings().all()
            for row in rows:
                sid = _raw_key(row, pk_cols)
                if sid in existing:
                    continue
                existing.add(sid)
                new.append(EstockRawMirror(source_table=tbl, source_id=sid,
                                           raw=_row_to_json(row), branch_id=_branch_of(row)))
                n_new += 1
                _flush()
        _flush(force=True)

    if hi:
        _raw_save_watermark_in(dst, tbl, hi)
    return n_new


def _load_uncovered_tables(insp, src, dst, counts: dict,
                           branch_map: dict[int, int] | None = None,
                           default_branch_id: int | None = None) -> None:
    """Mirror every eStock source table NOT already handled by a dedicated _load_*
    function into the generic ``estock_raw_mirror`` table.

    Each table runs inside its own SAVEPOINT: the raw pass shares the mirror's
    single transaction with everything the dedicated loaders just wrote, so one
    unreadable source table must unwind only its own work, never the whole sync.
    """
    if not _raw_mirror_enabled():
        counts["raw_enabled"] = False
        counts["raw_ok"] = True
        return

    # An off-peak backfill outlasts several 5-minute cycles; the cycles it overlaps
    # skip the raw pass rather than fight it for the same rows. Their dedicated
    # loaders still run, so the POS mirror stays current throughout.
    if not _raw_try_lock(dst):
        counts["raw_enabled"] = True
        counts["raw_locked"] = True
        counts["raw_ok"] = True
        return

    covered = COVERED_SOURCE_TABLES
    all_t = sorted(insp.get_table_names())
    uncov = [t for t in all_t if t not in covered]
    skip_above = _raw_skip_above_rows()
    max_ref = _raw_refresh_max_rows()

    counts.update(raw_enabled=True, raw_tables_total=len(all_t),
                  raw_tables_dedicated=len(all_t) - len(uncov))

    work, skipped = [], []
    if skip_above:
        for t in uncov:
            try:
                n = src.execute(text("SELECT COUNT(*) FROM " + t)).scalar()
                if n is not None and n > skip_above:
                    skipped.append(t)
                    continue
            except Exception:
                pass
            work.append(t)
    else:
        work = list(uncov)
    counts["raw_skipped"] = skipped

    failed: list[str] = []
    mirrored = 0
    total_new = 0

    for tbl in work:
        if not insp.has_table(tbl):
            continue
        bm = _source_table_branch_id(insp, src, tbl, branch_map, default_branch_id)
        sp = dst.begin_nested()
        try:
            n = _mirror_one_raw_table(insp, src, dst, tbl, bm, max_ref)
            sp.commit()
        except Exception as exc:
            sp.rollback()
            failed.append(f"{tbl}: {type(exc).__name__}")
            continue
        mirrored += 1
        total_new += n
        counts[f"raw_{tbl}"] = n

    counts["raw_tables_mirrored"] = mirrored
    counts["raw_failed"] = failed
    counts["raw_total_rows"] = total_new
    counts["raw_ok"] = not failed
    counts["raw_coverage_pct"] = (
        round((counts["raw_tables_dedicated"] + mirrored) * 100.0 / len(all_t), 1)
        if all_t else 100.0
    )



if __name__ == "__main__":
    import json
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "--status"
    if arg == "--check":
        out = preflight()
    elif arg == "--run":
        out = run_full_load()
    elif arg == "--import":
        # python -m app.services.etl --import <database> <BRANCH_CODE> [--fresh]
        database = sys.argv[2] if len(sys.argv) > 2 else ""
        branch = sys.argv[3] if len(sys.argv) > 3 else ""
        if not database or not branch:
            out = {"ran": False, "reason": "usage: --import <database> <BRANCH_CODE> [--fresh]"}
        else:
            out = import_branch_backup(database, branch, append="--fresh" not in sys.argv)
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
