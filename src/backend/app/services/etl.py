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

import os
import time
from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, create_engine, delete, func, insert, inspect, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.db.base import Base, SessionLocal, engine

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

# Destination tables cleared (children first) before a full load. Branches and
# the reference/lookup seeds are kept; the mirror fills operational data.
_WIPE_ORDER = [
    m.LoyaltyTransaction,  # references sales + customers — must go first
    m.SaleLine, m.Sale, m.PurchaseLine, m.Purchase, m.StockMovement,
    m.StockTransferLine, m.StockTransfer, m.CashTransfer if hasattr(m, "CashTransfer") else None,
    m.OpeningStockLine if hasattr(m, "OpeningStockLine") else None,
    m.OpeningStock if hasattr(m, "OpeningStock") else None,
    m.StockAdjustment if hasattr(m, "StockAdjustment") else None,
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
    """First candidate column present (case-insensitive), else None."""
    lower = {c.lower() for c in cols}
    for cand in candidates:
        if cand.lower() in lower:
            return cand
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
        _load_employees(insp, src, dst, counts)
        _load_stock(insp, src, dst, counts, product_map, branch_map, default_branch)

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
        for h, d, ret, ck in sales_tables:
            _load_sales(
                insp, src, dst, counts, product_map, customer_map, branch_map,
                default_branch, employee_map, header_tbl=h, detail_tbl=d, returns=ret, count_key=ck,
                window_cutoff=window_cutoff,
            )

        for h, d in [
            ("Purchase_header", "Purchase_details"),
            ("Branches_purchase_header", "Branches_purchase_details"),
        ]:
            _load_purchases(insp, src, dst, counts, product_map, branch_map, default_branch,
                            header_tbl=h, detail_tbl=d, window_cutoff=window_cutoff)

        _load_treasury(insp, src, dst, counts, branch_map, default_branch)

        dst.commit()
    finally:
        src.close()
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
    """Every store_id present on the source (across the branch-bearing tables)."""
    ids: set[int] = set()
    for tbl in ("Product_Amount", "Sales_header", "Back_sales_header", "Purchase_header"):
        if not insp.has_table(tbl):
            continue
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "store_id" not in cols:
            continue
        for (v,) in src.execute(text(f"SELECT DISTINCT store_id FROM {tbl}")):
            if v is not None:
                ids.add(int(v))
    return ids


def _resolve_branch_map(
    dst: Session, store_branch_map: dict | None, store_ids: set[int] | None = None
) -> dict[int, int]:
    """store_id (eStock) -> branch_id (ProCare).

    Honours an operator-provided map ({store_id: 'CODE'} or {store_id: branch_id}),
    creating any named ProCare branch that doesn't exist yet. Any store_id seen on
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


def _load_employees(insp, src, dst, counts) -> None:
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
        eid, cur_hash = existing.get(uname.lower(), (None, None))
        if eid is not None:
            # A usable ProCare password (``sha256$…``) marks a REAL ProCare
            # login (roster or admin-granted). eStock's active/deleted state
            # must never disable it — otherwise a stale source employee row
            # locks the owner out on every sync cycle. Mirror-created rows
            # (sentinel hash, cannot log in) keep following the source.
            if cur_hash and cur_hash.startswith("sha256$"):
                fields.pop("is_active")
            dst.execute(
                m.Employee.__table__.update()
                .where(m.Employee.__table__.c.employee_id == eid)
                .values(**fields)
            )
            updated += 1
        else:
            dst.add(m.Employee(
                username=uname, password_hash="!estock-mirror", role="assistant", **fields
            ))
            created += 1
    dst.flush()
    counts["employees"] = created
    counts["employees_updated"] = updated


def _load_stock(insp, src, dst, counts, product_map, branch_map, default_branch) -> None:
    if not insp.has_table("Product_Amount"):
        counts["stock_batches"] = 0
        return
    cols = {c["name"] for c in insp.get_columns("Product_Amount")}
    pid = _pick(cols, "product_id")
    store = _pick(cols, "store_id")
    counter = _pick(cols, "counter_id")
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
        branch_id = branch_map.get(int(r[store])) if store and r.get(store) is not None else default_branch
        batch_objs.append(
            m.StockBatch(
                product_id=dst_pid,
                branch_id=branch_id or default_branch,
                source_counter=int(r[counter]) if counter and r.get(counter) is not None else None,
                amount=max(_num(r.get(amount)), 0),  # CK_stock_amount: never negative
                buy_price=_num(r.get(buy)) if buy else 0,
                sell_price=_num(r.get(sell)) if sell else 0,
                tax_price=_num(r.get(tax)) if tax else 0,
                exp_date=_as_date(r.get(exp)) if exp else None,
            )
        )
        n += 1
    dst.add_all(batch_objs)
    dst.flush()
    counts["stock_batches"] = n


def _load_sales(
    insp, src, dst, counts, product_map, customer_map, branch_map, default_branch,
    employee_map=None, *, header_tbl, detail_tbl, returns: bool, count_key: str,
    window_cutoff: date | None = None,
) -> None:
    """Mirror one sales header/detail table pair into ProCare.

    Called once per source table so the FULL eStock picture is captured: the
    head-office ``Sales_header`` AND the branch ``Branches_sales_header`` (which
    can hold MORE rows than the main table), plus the ``Back_*`` return variants.
    Counts ACCUMULATE across calls under ``count_key`` (sales / returns).
    """
    employee_map = employee_map or {}
    if not insp.has_table(header_tbl):
        counts.setdefault(count_key, 0)
        return

    hcols = {c["name"] for c in insp.get_columns(header_tbl)}
    sid = _pick(hcols, "sales_id")
    store = _pick(hcols, "store_id")
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

    sale_id_map: dict[int, int] = {}
    n_headers = 0
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
            branch_id = branch_map.get(int(r[store])) if store and r.get(store) is not None else default_branch
            # eStock cashier_id is a username (varchar) -> map to a ProCare employee.
            cashier_id = None
            if cashier and r.get(cashier) not in (None, "", 0):
                cashier_id = employee_map.get(str(r[cashier]).strip().lower())
            pairs.append((
                r,
                m.Sale(
                    branch_id=branch_id or default_branch,
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
                sale_id_map[int(r[sid])] = obj.sale_id
        n_headers += len(pairs)
    counts[count_key] = counts.get(count_key, 0) + n_headers

    # Lines
    if not insp.has_table(detail_tbl):
        counts.setdefault(count_key + "_lines", 0)
        return
    dcols = {c["name"] for c in insp.get_columns(detail_tbl)}
    d_sid = _pick(dcols, "sales_id")
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
        if not sale_id_map:
            counts[count_key + "_lines"] = counts.get(count_key + "_lines", 0)
            return
        detail_bounds = (min(sale_id_map), max(sale_id_map))

    n_lines = 0
    for drows in _iter_rows(src, detail_tbl, d_sid, bounds=detail_bounds):
        line_rows = []
        for r in drows:
            sale_pk = sale_id_map.get(int(r[d_sid])) if d_sid and r.get(d_sid) is not None else None
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
            dst.execute(insert(m.SaleLine), line_rows)
        n_lines += len(line_rows)
    counts[count_key + "_lines"] = counts.get(count_key + "_lines", 0) + n_lines


def _load_purchases(
    insp, src, dst, counts, product_map, branch_map, default_branch,
    vendor_map=None, *, header_tbl="Purchase_header", detail_tbl="Purchase_details",
    window_cutoff: date | None = None,
) -> None:
    """Mirror one purchase header/detail table pair. Called for both the
    head-office ``Purchase_header`` and the branch ``Branches_purchase_header``
    so purchase totals match eStock. Counts accumulate."""
    vendor_map = vendor_map or {}
    if not insp.has_table(header_tbl):
        counts.setdefault("purchases", 0)
        return
    hcols = {c["name"] for c in insp.get_columns(header_tbl)}
    pid = _pick(hcols, "purchase_id")
    vendor = _pick(hcols, "vendor_id")
    store = _pick(hcols, "store_id")
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

    purch_map: dict[int, int] = {}
    n_headers = 0
    for hrows in header_chunks:
        pairs = []  # (src row, Purchase) — only the rows actually kept
        for r in hrows:
            bd = (_as_date(r.get(bill_date)) if bill_date else None) or date.today()
            # Python-side window guard (see _load_sales): a dateless fallback
            # fetch must not re-insert history the window wipe didn't clear.
            if window_cutoff is not None and bd < window_cutoff:
                continue
            branch_id = branch_map.get(int(r[store])) if store and r.get(store) is not None else default_branch
            src_vendor = int(r[vendor]) if vendor and r.get(vendor) not in (None, 0) else None
            pairs.append((
                r,
                m.Purchase(
                    branch_id=branch_id or default_branch,
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
                purch_map[int(r[pid])] = obj.purchase_id
        n_headers += len(pairs)
    counts["purchases"] = counts.get("purchases", 0) + n_headers

    if not insp.has_table(detail_tbl):
        counts.setdefault("purchase_lines", 0)
        return
    dcols = {c["name"] for c in insp.get_columns(detail_tbl)}
    d_pid = _pick(dcols, "purchase_id")
    d_prod = _pick(dcols, "product_id")
    d_amount = _pick(dcols, "amount")
    d_bonus = _pick(dcols, "bouns", "bonus")
    d_buy = _pick(dcols, "buy_price")
    d_sell = _pick(dcols, "sell_price")
    d_exp = _pick(dcols, "exp_date")

    detail_bounds = None
    if window_cutoff is not None:
        if not purch_map:
            counts["purchase_lines"] = counts.get("purchase_lines", 0)
            return
        detail_bounds = (min(purch_map), max(purch_map))

    n_lines = 0
    for drows in _iter_rows(src, detail_tbl, d_pid, bounds=detail_bounds):
        line_rows = []
        for r in drows:
            purch_pk = purch_map.get(int(r[d_pid])) if d_pid and r.get(d_pid) is not None else None
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
            dst.execute(insert(m.PurchaseLine), line_rows)
        n_lines += len(line_rows)
    counts["purchase_lines"] = counts.get("purchase_lines", 0) + n_lines


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

    Confirms (1) we can connect to the configured eStock source, and (2) the
    login truly cannot write — a blocked write is the SUCCESS case (roadmap
    Phase 0). Run this on a machine that can reach the DB.
    """
    url = settings.estock_sqlalchemy_url()
    if not url:
        return {"ok": False, "reason": "No eStock credentials configured (config/connections.json)."}
    try:
        src = create_engine(url, echo=False)
        with src.connect() as c:
            c.execute(text("SELECT 1"))
            insp = inspect(src)
            tables = insp.get_table_names()
            # Discover the branches present so the operator can name them (e.g.
            # which store_id is Mashal) before/after the first sync.
            try:
                store_ids = sorted(_distinct_store_ids(insp, c))
            except Exception:  # noqa: BLE001
                store_ids = []
        result = {
            "ok": True,
            "connected": True,
            "source_tables": len(tables),
            "store_ids_found": store_ids,
            "hint": "Map each store_id to a branch via ESTOCK_STORE_BRANCH_MAP; "
            "unmapped ids auto-create a STORE<id> branch.",
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


def run_full_load() -> dict:
    """Entry point for the Phase-1 full mirror against the live eStock DB.

    Refuses to run (rather than guess) until a real read-only eStock login is
    configured, keeping the read-only guardrail explicit and safe.
    """
    url = settings.estock_sqlalchemy_url()
    if not url:
        return {
            "ran": False,
            "reason": "No read-only eStock credentials configured. "
            "Fill config/connections.json:estock_source, then re-run. "
            "The system runs on its own seeded data until then.",
        }
    Base.metadata.create_all(engine)
    # Read-only intent: the login itself has no write perms; we also never issue
    # anything but SELECT against the source.
    source_engine = create_engine(url, echo=False)
    store_map = settings.estock_store_branch_map()
    with SessionLocal() as dst:
        counts = mirror(source_engine, dst, store_map)
    return {"ran": True, "source": "eStock (read-only)", "counts": counts}


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
