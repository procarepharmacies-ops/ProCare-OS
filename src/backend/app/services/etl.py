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

from datetime import date, datetime

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


def _ar(raw_ar, raw_en=None, placeholder: str = "بدون اسم") -> str:
    """Arabic display name: the source Arabic value, else the English name, else
    a clear Arabic placeholder. Never a bare ``"?"`` — that reads on screen as a
    font/encoding failure rather than what it actually is (a missing name)."""
    if raw_ar is not None and str(raw_ar).strip():
        return str(raw_ar).strip()
    if raw_en is not None and str(raw_en).strip():
        return str(raw_en).strip()
    return placeholder


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
    """
    dedup = (branch_scoped or not wipe) if dedup is None else dedup
    update_on_match = branch_scoped
    insp = inspect(source_engine)

    with source_engine.connect() as src:
        if force_branch_code:
            # Every row from this single-branch backup belongs to one branch.
            default_branch = _ensure_branch_code(dst, force_branch_code)
            branch_map: dict[int, int] = {}
        else:
            # Discover the branches that actually exist on the source and ensure a
            # ProCare branch for each, so no branch's data is merged into another
            # (the remote server may carry Main, Elsanta, Mashala, ...).
            store_ids = _distinct_store_ids(insp, src)
            branch_map = _resolve_branch_map(dst, store_branch_map, store_ids)
            default_branch = next(iter(branch_map.values()))

        if branch_scoped:
            _wipe_branch_rows(dst, set(branch_map.values()) | {default_branch})
        elif wipe:
            _wipe_destination(dst)
        counts: dict[str, int] = {}

        product_map = _load_products(insp, src, dst, counts, dedup=dedup, update_on_match=update_on_match)
        customer_map = _load_customers(insp, src, dst, counts, dedup=dedup, update_on_match=update_on_match)
        _load_vendors(insp, src, dst, counts, dedup=dedup)
        _load_stock(insp, src, dst, counts, product_map, branch_map, default_branch)
        _load_sales(insp, src, dst, counts, product_map, customer_map, branch_map, default_branch, returns=False)
        _load_sales(insp, src, dst, counts, product_map, customer_map, branch_map, default_branch, returns=True)
        _load_purchases(insp, src, dst, counts, product_map, branch_map, default_branch)

        dst.commit()
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
        "ELSANTA_EXP": ("مخزن منتهي الصلاحيه", "Expired depot"),
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
        # مسهله (MAIN kept as fallback for demo-seeded databases).
        if "ELSANTA" in by_code:
            out[1] = by_code["ELSANTA"]
        if "MASHALA" in by_code:
            out[2] = by_code["MASHALA"]
        elif "MAIN" in by_code:
            out[2] = by_code["MAIN"]

    # Auto-create a branch for any source store_id we don't have a mapping for.
    for sid in sorted(store_ids or []):
        if sid not in out:
            out[sid] = ensure_branch(f"STORE{sid}", name_ar=f"فرع {sid}", name_en=f"Store {sid}")

    return out or {1: next(iter(by_code.values()))}


def _wipe_destination(dst: Session) -> None:
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
    batch_ids = select(m.StockBatch.batch_id).where(m.StockBatch.branch_id.in_(ids))
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
    # Transfers touch batches on BOTH ends — any line touching a wiped batch
    # goes, then every transfer with a wiped endpoint branch.
    dst.execute(
        delete(m.StockTransferLine).where(
            m.StockTransferLine.from_batch_id.in_(batch_ids)
            | m.StockTransferLine.to_batch_id.in_(batch_ids)
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
                        "b_sell": _num(r.get(sell)) if sell else 0,
                        "b_buy": _num(r.get(buy)) if buy else 0,
                        "b_tax": _num(r.get(tax)) if tax else 0,
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
                sell_price=_num(r.get(sell)) if sell else 0,
                buy_price=_num(r.get(buy)) if buy else 0,
                tax_price=_num(r.get(tax)) if tax else 0,
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


def _load_sales(insp, src, dst, counts, product_map, customer_map, branch_map, default_branch, *, returns: bool) -> None:
    header_tbl = "Back_sales_header" if returns else "Sales_header"
    detail_tbl = "Back_Sales_details" if returns else "Sales_details"
    key = "returns" if returns else "sales"
    if not insp.has_table(header_tbl):
        counts[key] = 0
        return

    hcols = {c["name"] for c in insp.get_columns(header_tbl)}
    sid = _pick(hcols, "sales_id")
    store = _pick(hcols, "store_id")
    cust = _pick(hcols, "customer_id")
    bill_date = _pick(hcols, "bill_date")
    insert_date = _pick(hcols, "insert_date")
    gross = _pick(hcols, "total_bill")
    net = _pick(hcols, "total_bill_net")
    disc = _pick(hcols, "total_disc_money")
    cash = _pick(hcols, "bill_cash")
    card = _pick(hcols, "network_money")
    change = _pick(hcols, "money_change")
    back = _pick(hcols, "back")

    hrows = src.execute(text(f"SELECT * FROM {header_tbl}")).mappings().all()
    sale_id_map: dict[int, int] = {}
    sale_objs = []
    for r in hrows:
        is_ret = returns or (_b(r.get(back)) if back else False)
        src_cust = int(r[cust]) if cust and r.get(cust) not in (None, 0) else None
        sale_dt = _as_dt(r.get(bill_date) if bill_date else None) or _as_dt(
            r.get(insert_date) if insert_date else None
        ) or datetime.now()
        branch_id = branch_map.get(int(r[store])) if store and r.get(store) is not None else default_branch
        sale_objs.append(
            m.Sale(
                branch_id=branch_id or default_branch,
                customer_id=customer_map.get(src_cust) if src_cust else None,
                sale_date=sale_dt,
                total_gross=_num(r.get(gross)) if gross else 0,
                total_discount=_num(r.get(disc)) if disc else 0,
                total_net=_num(r.get(net)) if net else 0,
                cash_paid=_num(r.get(cash)) if cash else 0,
                card_paid=_num(r.get(card)) if card else 0,
                change_given=_num(r.get(change)) if change else 0,
                is_return=is_ret,
            )
        )
    dst.add_all(sale_objs)
    dst.flush()
    for r, obj in zip(hrows, sale_objs):
        if sid and r.get(sid) is not None:
            sale_id_map[int(r[sid])] = obj.sale_id
    counts[key] = len(sale_objs)

    # Lines
    if not insp.has_table(detail_tbl):
        counts[key + "_lines"] = 0
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

    drows = src.execute(text(f"SELECT * FROM {detail_tbl}")).mappings().all()
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
    counts[key + "_lines"] = len(line_rows)


def _load_purchases(insp, src, dst, counts, product_map, branch_map, default_branch) -> None:
    if not insp.has_table("Purchase_header"):
        counts["purchases"] = 0
        return
    hcols = {c["name"] for c in insp.get_columns("Purchase_header")}
    pid = _pick(hcols, "purchase_id")
    vendor = _pick(hcols, "vendor_id")
    store = _pick(hcols, "store_id")
    bill_date = _pick(hcols, "bill_date")
    bill_num = _pick(hcols, "bill_number")
    gross = _pick(hcols, "total_bill")
    disc = _pick(hcols, "bill_disc_money")
    tax = _pick(hcols, "bill_tax")
    back = _pick(hcols, "back")

    # Vendors were loaded without preserving src ids; purchases need a vendor FK.
    # Use the first vendor as a safe placeholder when the source vendor can't be
    # resolved (vendor identity mapping is part of the deferred ledger audit).
    any_vendor = dst.scalars(select(m.Vendor.vendor_id)).first()
    if any_vendor is None:
        counts["purchases"] = 0
        return

    hrows = src.execute(text("SELECT * FROM Purchase_header")).mappings().all()
    purch_map: dict[int, int] = {}
    objs = []
    for r in hrows:
        branch_id = branch_map.get(int(r[store])) if store and r.get(store) is not None else default_branch
        objs.append(
            m.Purchase(
                branch_id=branch_id or default_branch,
                vendor_id=any_vendor,
                bill_date=_as_date(r.get(bill_date)) if bill_date else date.today(),
                bill_number=r.get(bill_num) if bill_num else None,
                total_gross=_num(r.get(gross)) if gross else 0,
                total_discount=_num(r.get(disc)) if disc else 0,
                total_tax=_num(r.get(tax)) if tax else 0,
                is_return=_b(r.get(back)) if back else False,
            )
        )
    dst.add_all(objs)
    dst.flush()
    for r, obj in zip(hrows, objs):
        if pid and r.get(pid) is not None:
            purch_map[int(r[pid])] = obj.purchase_id
    counts["purchases"] = len(objs)

    if not insp.has_table("Purchase_details"):
        counts["purchase_lines"] = 0
        return
    dcols = {c["name"] for c in insp.get_columns("Purchase_details")}
    d_pid = _pick(dcols, "purchase_id")
    d_prod = _pick(dcols, "product_id")
    d_amount = _pick(dcols, "amount")
    d_bonus = _pick(dcols, "bouns", "bonus")
    d_buy = _pick(dcols, "buy_price")
    d_sell = _pick(dcols, "sell_price")
    d_exp = _pick(dcols, "exp_date")

    drows = src.execute(text("SELECT * FROM Purchase_details")).mappings().all()
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
    counts["purchase_lines"] = len(line_rows)


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
