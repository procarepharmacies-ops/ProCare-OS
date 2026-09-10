"""Lightweight, dependency-free schema migration + first-account bootstrap.

This app has no formal migration tool (no Alembic) — ``Base.metadata.create_all``
only creates missing *tables*, never adds columns to a table that already
exists. That's exactly the situation the login feature introduced: pharmacies
already running ProCare have an ``employees`` table without the new ``role``
column. Run once at startup, idempotent, safe on SQLite and SQL Server.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import auth as auth_svc

log = logging.getLogger("procare.migrate")


# FK-check indexes: SQLite (and SQL Server) verify child references on every
# parent-row DELETE. Without an index on the child FK column that check is a
# full table scan PER DELETED ROW — the branch-scoped sync wipe of 35K stock
# batches against 190K unindexed sale_lines.batch_id took ~500 seconds on the
# dev database; 0.1s with the index. Names must match the models' Index()
# declarations so fresh (create_all) and migrated databases end up identical.
_FK_INDEXES = [
    ("sale_lines", "IX_sale_lines_batch", "batch_id"),
    ("purchase_lines", "IX_purchase_lines_purchase", "purchase_id"),
    ("purchase_lines", "IX_purchase_lines_batch", "batch_id"),
    ("loyalty_transactions", "IX_loyalty_sale", "sale_id"),
    ("stock_movements", "IX_movements_batch", "batch_id"),
    ("stock_transfer_lines", "IX_transfer_lines_transfer", "transfer_id"),
    ("stock_transfer_lines", "IX_transfer_lines_from", "from_batch_id"),
    ("stock_transfer_lines", "IX_transfer_lines_to", "to_batch_id"),
    ("sales", "IX_sales_original", "original_sale_id"),
]


def ensure_fk_indexes(engine) -> None:
    """Create any missing FK-check index (idempotent, SQLite + SQL Server)."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, name, col in _FK_INDEXES:
        if table not in tables:
            continue  # create_all will make the table with its indexes.
        existing = {ix["name"] for ix in inspector.get_indexes(table)}
        if name in existing:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX {name} ON {table} ({col})"))


def ensure_role_column(engine) -> None:
    """Add ``employees.role`` if the table predates it (default 'assistant',
    the most restrictive tier, so nobody is silently over-privileged)."""
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return  # create_all will make the table with the column already.
    columns = {c["name"] for c in inspector.get_columns("employees")}
    if "role" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE employees {add} role VARCHAR(20) DEFAULT 'assistant'"))


def ensure_original_sale_id_column(engine) -> None:
    """Add ``sales.original_sale_id`` (return -> original invoice link) if the
    table predates the sale-returns feature. NULL for all existing rows."""
    inspector = inspect(engine)
    if "sales" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("sales")}
    if "original_sale_id" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE sales {add} original_sale_id INTEGER NULL"))


def ensure_shelf_location_column(engine) -> None:
    """Add ``products.shelf_location`` (merchandising place code) if the table
    predates it."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "shelf_location" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE products {add} shelf_location VARCHAR(80) NULL"))


def ensure_loyalty_points_column(engine) -> None:
    """Add ``customers.loyalty_points`` (loyalty programme balance) if the
    table predates it. Existing customers start at 0 points."""
    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("customers")}
    if "loyalty_points" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE customers {add} loyalty_points NUMERIC(18,3) DEFAULT 0"))


def ensure_task_priority_columns(engine) -> None:
    """Add ``employee_tasks.priority`` and ``.category`` if the table predates
    the professional daily-plan upgrade. Existing tasks default to normal/general."""
    inspector = inspect(engine)
    if "employee_tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("employee_tasks")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "priority" not in columns:
            conn.execute(text(f"ALTER TABLE employee_tasks {add} priority VARCHAR(10) DEFAULT 'normal'"))
        if "category" not in columns:
            conn.execute(text(f"ALTER TABLE employee_tasks {add} category VARCHAR(20) DEFAULT 'general'"))


def ensure_prescription_status_columns(engine) -> None:
    """Add ``prescriptions.status`` + ``.reviewed_by`` if the table predates the
    capture -> review -> dispense workflow. Existing rows become 'captured'."""
    inspector = inspect(engine)
    if "prescriptions" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("prescriptions")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "status" not in columns:
            conn.execute(text(f"ALTER TABLE prescriptions {add} status VARCHAR(20) DEFAULT 'captured'"))
        if "reviewed_by" not in columns:
            conn.execute(text(f"ALTER TABLE prescriptions {add} reviewed_by INTEGER NULL"))


def ensure_titan_match_columns(engine) -> None:
    """Add ``products.titan_match_method`` + ``.titan_match_score`` if the table
    predates the Titan/Drug-Eye mapping job (docs/03 §4). Existing rows stay
    NULL = unmapped; ``tools/titan_extract.py`` fills them."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "titan_match_method" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} titan_match_method VARCHAR(20) NULL"))
        if "titan_match_score" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} titan_match_score INTEGER NULL"))


def ensure_titan_drug_columns(engine) -> None:
    """Add ``titan_drugs.origin`` + ``.is_medicine`` (derived by the extractor
    from manufacturer nationality and therapeutic category — Titan stores no
    such flags itself), and relax ``name_en`` to NULL: the TITAN.349 build
    carries drugs with an Arabic name only."""
    inspector = inspect(engine)
    if "titan_drugs" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("titan_drugs")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "origin" not in columns:
            conn.execute(text(f"ALTER TABLE titan_drugs {add} origin VARCHAR(10) NULL"))
        if "is_medicine" not in columns:
            col_type = "BIT" if engine.dialect.name == "mssql" else "BOOLEAN"
            conn.execute(text(f"ALTER TABLE titan_drugs {add} is_medicine {col_type} NULL"))
        # SQLite cannot ALTER a column's nullability; it is only a constraint on
        # new writes there and the table is reloaded wholesale, so skip it.
        if engine.dialect.name == "mssql":
            conn.execute(text("ALTER TABLE titan_drugs ALTER COLUMN name_en VARCHAR(60) NULL"))


def ensure_employee_reset_columns(engine) -> None:
    """Add the WhatsApp password-reset columns if the table predates them.

    Dialect-aware: SQL Server wants ``ADD``, SQLite wants ``ADD COLUMN``.
    """
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("employees")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "phone" not in columns:
            conn.execute(text(f"ALTER TABLE employees {add} phone VARCHAR(20) NULL"))
        if "reset_code_hash" not in columns:
            conn.execute(text(f"ALTER TABLE employees {add} reset_code_hash VARCHAR(255) NULL"))
        if "reset_code_expires" not in columns:
            conn.execute(text(f"ALTER TABLE employees {add} reset_code_expires DATETIME NULL"))
        if "reset_attempts" not in columns:
            conn.execute(text(f"ALTER TABLE employees {add} reset_attempts INTEGER DEFAULT 0"))


def ensure_sync_cycle_columns(engine) -> None:
    """Add ``sync_state.cycle_started_at/cycle_mode`` if the table predates the
    interrupted-cycle guard. Without them an aborted full load looks identical
    to a finished one and the mirror stays silently partial.
    """
    inspector = inspect(engine)
    if "sync_state" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("sync_state")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "cycle_started_at" not in columns:
            conn.execute(text(f"ALTER TABLE sync_state {add} cycle_started_at DATETIME NULL"))
        if "cycle_mode" not in columns:
            conn.execute(text(f"ALTER TABLE sync_state {add} cycle_mode VARCHAR(30) NULL"))


def ensure_product_unit_columns(engine) -> None:
    """Add ``products.unit_big/unit_small/unit_factor`` (وحدة كبرى/صغرى) if the
    table predates the units feature. Existing products default to factor 1
    (no subdivision) until the next eStock sync refreshes them."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "unit_big" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} unit_big VARCHAR(50) NULL"))
        if "unit_small" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} unit_small VARCHAR(50) NULL"))
        if "unit_factor" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} unit_factor NUMERIC(18,3) DEFAULT 1"))


def ensure_customer_address_column(engine) -> None:
    """Add ``customers.address`` (العنوان) if the table predates the customer
    360 screen."""
    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("customers")}
    if "address" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE customers {add} address VARCHAR(300) NULL"))


def ensure_product_classification_columns(engine) -> None:
    """Add ``products.dosage_form/is_otc/uses`` (الشكل الصيدلاني / OTC /
    الاستخدامات) if the table predates the classification feature."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "dosage_form" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} dosage_form VARCHAR(50) NULL"))
        if "is_otc" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} is_otc BIT DEFAULT 0"))
        if "uses" not in columns:
            conn.execute(text(f"ALTER TABLE products {add} uses VARCHAR(300) NULL"))


# The pharmacy's real staff, as given by the owner (2026-07-02). Ensured at
# every startup so both the dev-seeded DB and the eStock-synced production DB
# (which never gets employees from the sync) have the same real logins.
# Everyone starts with INITIAL_PASSWORD and must change it from the login
# menu (POST /auth/change-password) — existing accounts are never overwritten,
# so changed passwords survive restarts.
INITIAL_PASSWORD = "Procare@2026"
ROSTER = [
    # (username, name_en, name_ar, role, branch hint — matched against
    #  branch code/name, None = all branches / head office)
    ("ahmedibrahim", "Ahmed Ibrahim", "أحمد إبراهيم", "ceo", None),
    ("yousef", "Yousef Abuzaid", "يوسف أبو زيد", "manager", "santa"),
    ("afaf", "Afaf", "عفاف", "manager", "mashal"),
    ("abdullah", "Abdullah Alaa", "عبدالله علاء", "assistant", None),
    ("nada", "Nada Magdy", "ندى مجدي", "assistant", None),
    ("nouran", "Nouran Shehata (Training Pharmacist)", "نوران شحاتة (صيدلانية تحت التدريب)", "assistant", None),
    ("alaa", "Alaa Mohamed", "علاء محمد", "assistant", "mashal"),
]


def _find_branch(session: Session, hint: str | None) -> int | None:
    """Match a roster branch hint against branch code / English / Arabic name,
    case-insensitively. Branch names in production come from the eStock sync
    (ELSANTA, auto-created STORE<n>, …), so match loosely and return None when
    nothing fits — the account still works, just isn't branch-scoped yet."""
    if not hint:
        return None
    from sqlalchemy import select

    hint = hint.lower()
    aliases = {"mashal": ("mashal", "mashala", "mas-hala", "مشعل"), "santa": ("santa", "elsanta", "السنطه")}
    needles = aliases.get(hint, (hint,))
    for b in session.scalars(select(m.Branch)):
        haystack = " ".join(filter(None, (b.code, b.name_en, b.name_ar))).lower()
        if any(n in haystack for n in needles):
            return b.branch_id
    return None


def ensure_roster(session: Session) -> None:
    """Create any missing real-staff accounts (create-only: never touches an
    existing row, so password changes and role edits made later stick)."""
    from sqlalchemy import select

    existing = set(session.scalars(select(m.Employee.username)).all())
    added = False
    for username, name_en, name_ar, role, branch_hint in ROSTER:
        if username in existing:
            continue
        session.add(
            m.Employee(
                name_ar=name_ar,
                name_en=name_en,
                username=username,
                password_hash=auth_svc.hash_password(INITIAL_PASSWORD),
                role=role,
                branch_id=_find_branch(session, branch_hint),
                can_see_buy_price=role in ("ceo", "manager"),
                can_edit_sell_price=role == "ceo",
                can_sale_credit=True,
                can_return=role in ("ceo", "manager"),
                can_void=role == "ceo",
                can_change_shift=True,
            )
        )
        added = True
    if added:
        session.commit()


def bootstrap_ceo_if_configured(session: Session) -> None:
    """Create exactly one CEO account from env vars if the employees table is
    otherwise empty. Without this, a freshly-synced production DB (eStock sync
    fills products/customers/sales but never employees — there's no eStock
    employee mirror) would have no way to log in at all.

    No-op unless BOOTSTRAP_CEO_USERNAME and BOOTSTRAP_CEO_PASSWORD are both
    set — we don't want a guessable default account in production.
    """
    username = os.environ.get("BOOTSTRAP_CEO_USERNAME", "").strip()
    password = os.environ.get("BOOTSTRAP_CEO_PASSWORD", "")
    if not username or not password:
        return
    from sqlalchemy import func, select

    count = session.scalar(select(func.count()).select_from(m.Employee)) or 0
    if count > 0:
        return
    session.add(
        m.Employee(
            name_ar=username,
            name_en=username,
            username=username,
            password_hash=auth_svc.hash_password(password),
            role="ceo",
        )
    )
    session.commit()


def ensure_assigned_agent_column(engine) -> None:
    """Add ``employee_tasks.assigned_agent`` so tasks can be routed to AI agents."""
    inspector = inspect(engine)
    if "employee_tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("employee_tasks")}
    if "assigned_agent" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE employee_tasks ADD assigned_agent VARCHAR(20) NULL"))


def ensure_incentive_points_column(engine) -> None:
    """Add ``products.incentive_points`` (OTC incentive list points per unit sold)
    if the table predates the employee incentive feature. Existing products
    default to 0 (no incentive)."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "incentive_points" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE products {add} incentive_points NUMERIC(18,3) DEFAULT 0"))


def ensure_branch_names_corrected(engine) -> None:
    """Fix old Arabic branch name spelling in existing DBs.

    Seed used to write السنطه/مسهله (ه = ha) instead of the correct
    السنطة/مسهلة (ة = taa marbuta). This migration updates any rows that
    still carry the old spelling. Safe no-op if already correct or if the
    branches table doesn't exist yet.
    """
    inspector = inspect(engine)
    if "branches" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE branches SET name_ar = 'السنطة' WHERE code = 'ELSANTA' AND name_ar = 'السنطه'"
        ))
        conn.execute(text(
            "UPDATE branches SET name_ar = 'مسهلة' WHERE code = 'MASHALA' AND name_ar = 'مسهله'"
        ))


def ensure_loyalty_tier_columns(engine) -> None:
    """Add ``customers.tier`` and ``.tier_spend_12m`` (Phase 3: loyalty tiers).

    Existing customers default to 'silver' tier with 0 spend tracked.
    Nightly scheduler job recomputes tiers based on 12-month transaction history.
    """
    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("customers")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "tier" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} tier VARCHAR(20) DEFAULT 'silver'"))
        if "tier_spend_12m" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} tier_spend_12m NUMERIC(18,3) DEFAULT 0"))


def ensure_customer_crm_columns(engine) -> None:
    """Add ``customers.birthday``, ``.wa_opt_out``, ``.rfm_segment``,
    ``.last_purchase_date`` (Phase 3: CRM engagement + RFM segmentation).

    Existing customers: no birthday, not opted out, default to 'regular' segment,
    last_purchase_date NULL.
    """
    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("customers")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "birthday" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} birthday DATE NULL"))
        if "wa_opt_out" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} wa_opt_out BIT DEFAULT 0"))
        if "rfm_segment" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} rfm_segment VARCHAR(20) DEFAULT 'regular'"))
        if "last_purchase_date" not in columns:
            conn.execute(text(f"ALTER TABLE customers {add} last_purchase_date DATETIME NULL"))


def ensure_forecast_tables(engine) -> None:
    """Ensure forecasts and decision_cards tables exist (Phase 5).

    Creates tables via create_all if missing; idempotent (safe to re-run).
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "forecasts" not in table_names or "decision_cards" not in table_names:
        from app.db.models import Forecast, DecisionCard, Base
        Base.metadata.create_all(engine, tables=[Forecast.__table__, DecisionCard.__table__] if "forecasts" not in table_names else [])


def ensure_ledger_reason_column(engine) -> None:
    """Add ``ledger_entries.reason_code`` (Phase 6: named adjustment reasons,
    eStock Tuning_accounts parity) if the table predates it. Existing rows keep
    a NULL reason (they are machine postings, not manual adjustments)."""
    inspector = inspect(engine)
    if "ledger_entries" not in inspector.get_table_names():
        return  # create_all will make the table with the column already.
    columns = {c["name"] for c in inspector.get_columns("ledger_entries")}
    if "reason_code" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE ledger_entries {add} reason_code VARCHAR(30) NULL"))


def ensure_purchase_line_discount_column(engine) -> None:
    """Add ``purchase_lines.disc_money`` (per-line cash discount) if the table
    predates it. Existing lines default to 0."""
    inspector = inspect(engine)
    if "purchase_lines" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("purchase_lines")}
    if "disc_money" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE purchase_lines {add} disc_money NUMERIC(18,3) DEFAULT 0"))


def ensure_purchase_header_extra_columns(engine) -> None:
    """Add ``purchases.disc_percent`` + ``purchases.other_expenses`` (header
    discount rate + other invoice expenses) if the table predates them.
    Existing purchases default both to 0 — no change to their net."""
    inspector = inspect(engine)
    if "purchases" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("purchases")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "disc_percent" not in columns:
            conn.execute(text(f"ALTER TABLE purchases {add} disc_percent NUMERIC(18,3) DEFAULT 0"))
        if "other_expenses" not in columns:
            conn.execute(text(f"ALTER TABLE purchases {add} other_expenses NUMERIC(18,3) DEFAULT 0"))


def ensure_job_source_columns(engine) -> None:
    """Add ``jobs.source_id`` + ``jobs.code`` if the table predates the eStock
    ``Jobs`` mirror. Pre-existing (seeded) job titles keep NULL source_id and
    are matched by name instead, so the mirror reuses them rather than
    inserting a duplicate."""
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("jobs")}
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        if "source_id" not in columns:
            conn.execute(text(f"ALTER TABLE jobs {add} source_id INTEGER"))
        if "code" not in columns:
            conn.execute(text(f"ALTER TABLE jobs {add} code VARCHAR(30)"))


def ensure_held_invoice_table(engine) -> None:
    """Ensure the held_invoices table exists (Phase 7: hold/park invoice).
    Creates it via create_all if missing; idempotent."""
    inspector = inspect(engine)
    if "held_invoices" not in inspector.get_table_names():
        from app.db.models import Base, HeldInvoice

        Base.metadata.create_all(engine, tables=[HeldInvoice.__table__])


def ensure_product_barcode_table(engine) -> None:
    """Ensure the product_barcodes table exists (scanned GTIN -> product map).
    Creates it via create_all if missing; idempotent."""
    inspector = inspect(engine)
    if "product_barcodes" not in inspector.get_table_names():
        from app.db.models import Base, ProductBarcode

        Base.metadata.create_all(engine, tables=[ProductBarcode.__table__])


def ensure_sale_note_column(engine) -> None:
    """Add ``sales.note`` (cashier's free-text invoice note) if the table
    predates it. Existing sales keep a NULL note."""
    inspector = inspect(engine)
    if "sales" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("sales")}
    if "note" in columns:
        return
    add = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE sales {add} note VARCHAR(300) NULL"))


def ensure_payroll_table(engine) -> None:
    """Ensure the payroll_records table exists (Phase 6: payroll depth mirror).
    Creates it via create_all if missing; idempotent."""
    inspector = inspect(engine)
    if "payroll_records" not in inspector.get_table_names():
        from app.db.models import Base, PayrollRecord

        Base.metadata.create_all(engine, tables=[PayrollRecord.__table__])


def ensure_salary_advance_table(engine) -> None:
    """Ensure the salary_advances table exists (Phase 6: advances ledger,
    Employee_cash_advance parity). Creates it via create_all if missing;
    idempotent."""
    inspector = inspect(engine)
    if "salary_advances" not in inspector.get_table_names():
        from app.db.models import Base, SalaryAdvance

        Base.metadata.create_all(engine, tables=[SalaryAdvance.__table__])


def ensure_shareholder_tables(engine) -> None:
    """Ensure shareholders + dividend_payments tables exist (Phase 6:
    shareholders mirror). Creates them via create_all if missing; idempotent."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    missing = [t for t in ("shareholders", "dividend_payments") if t not in table_names]
    if missing:
        from app.db.models import Base, DividendPayment, Shareholder

        tables = [Shareholder.__table__, DividendPayment.__table__]
        Base.metadata.create_all(engine, tables=[t for t in tables if t.name in missing])


def ensure_product_change_table(engine) -> None:
    """Ensure the product_changes table exists (Phase 6: price/min-stock change
    log). Creates it via create_all if missing; idempotent."""
    inspector = inspect(engine)
    if "product_changes" not in inspector.get_table_names():
        from app.db.models import Base, ProductChange

        Base.metadata.create_all(engine, tables=[ProductChange.__table__])


def ensure_notification_table(engine) -> None:
    """Ensure the notification_dismissals table exists (Phase 6: notification
    center). Creates it via create_all if missing; idempotent."""
    inspector = inspect(engine)
    if "notification_dismissals" not in inspector.get_table_names():
        from app.db.models import Base, NotificationDismissal

        Base.metadata.create_all(engine, tables=[NotificationDismissal.__table__])


def ensure_commission_tables(engine) -> None:
    """Ensure commission_runs and commission_run_lines tables exist (Phase 6).

    Sales-rep commission calculator. Creates the tables via create_all if
    missing; idempotent (safe to re-run).
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    missing = [t for t in ("commission_runs", "commission_run_lines") if t not in table_names]
    if missing:
        from app.db.models import Base, CommissionRun, CommissionRunLine

        tables = [CommissionRun.__table__, CommissionRunLine.__table__]
        Base.metadata.create_all(engine, tables=[t for t in tables if t.name in missing])
def ensure_estock_raw_mirror_tables(engine) -> None:
    """Ensure estock_raw_mirror + estock_raw_watermark exist (100% eStock
    coverage: every source table not read by a dedicated loader is mirrored
    verbatim). Creates them via create_all if missing; idempotent."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    missing = [t for t in ("estock_raw_mirror", "estock_raw_watermark") if t not in table_names]
    if missing:
        from app.db.models import Base, EstockRawMirror, EstockRawWatermark

        tables = [EstockRawMirror.__table__, EstockRawWatermark.__table__]
        Base.metadata.create_all(engine, tables=[t for t in tables if t.name in missing])


_ARABIC_UNICODE_COLUMNS_PART1 = [
    ("branches", "name_ar", 100),
    ("companies", "name_ar", 150),
    ("customer_classes", "name_ar", 50),
    ("estock_raw_mirror", "raw", None),
    ("gl_accounts", "name_ar", 200),
    ("gl_adjustments", "notes", 300),
    ("gl_journal_entries", "notes", 300),
    ("gl_subledger_balances", "notes", 150),
    ("jobs", "name_ar", 80),
    ("product_groups", "name_ar", 100),
    ("shareholders", "name_ar", 150),
    ("shareholders", "address", 255),
    ("titan_drugs", "name_ar", 60),
    ("units", "name_ar", 50),
    ("vendors", "name_ar", 100),
    ("branch_order_headers", "note", 300),
    ("customers", "name_ar", 100),
    ("customers", "address", 300),
    ("employees", "name_ar", 100),
    ("ledger_entries", "note", 255),
    ("products", "name_ar", 150),
    ("products", "unit_big", 50),
    ("products", "unit_small", 50),
    ("products", "dosage_form", 50),
    ("products", "uses", 300),
    ("products", "shelf_location", 80),
]
_ARABIC_UNICODE_COLUMNS_PART2 = [
    ("branch_order_lines", "note", 300),
    ("campaigns", "name", 120),
    ("campaigns", "message", 2000),
    ("cash_shift_closes", "note", 300),
    ("commission_runs", "note", 255),
    ("decision_cards", "title_ar", 256),
    ("decision_cards", "body_ar", None),
    ("employee_goals", "title", 200),
    ("employee_goals", "details", 1000),
    ("employee_tasks", "title", 200),
    ("employee_tasks", "details", 1000),
    ("held_invoices", "label", 80),
    ("held_invoices", "note", 300),
    ("held_invoices", "cart_json", None),
    ("prescriptions", "doctor_name", 150),
    ("prescriptions", "clinic", 150),
    ("prescriptions", "drugs_json", 4000),
    ("prescriptions", "raw_text", 4000),
    ("promo_codes", "description_ar", 200),
    ("sales", "note", 300),
    ("shortage_items", "product_name", 200),
    ("shortage_items", "note", 500),
    ("social_posts", "body_ar", 2000),
    ("stock_counts", "note", 300),
    ("treasury_transfers", "note", 255),
    ("loyalty_transactions", "note", 255),
    ("stock_count_lines", "name_ar", 200),
]
# The ``*_en`` and free-text columns below were typed VARCHAR on the assumption
# that they only ever hold Latin text. eStock does not honour that: its own
# ``customer_name_en`` / ``product_name_en`` / ``vendor_name_en`` fields are
# filled by pharmacists who type Arabic into whichever box is in front of them,
# and the journal's cashier/terminal names are Arabic throughout. Every one of
# these was verified to be holding '?' runs in the live database before this
# migration was implemented (customers.name_en 13,116 rows; vendors.name_en
# 15,480; products.name_en 4,035), so they belong on the Unicode list too.
_ARABIC_UNICODE_COLUMNS_PART3 = [
    ("agent_runs", "output", 2000),
    ("agent_runs", "task", 500),
    ("branches", "name_en", 100),
    ("companies", "name_en", 150),
    ("customer_classes", "name_en", 50),
    ("customers", "name_en", 100),
    ("decision_cards", "body_en", None),
    ("decision_cards", "title_en", 256),
    ("employees", "name_en", 100),
    ("gl_accounts", "name_en", 200),
    ("gl_journal_entries", "actual_cashier", 80),
    ("gl_journal_entries", "computer_name", 80),
    ("gl_journal_entries", "form_type", 40),
    ("gl_journal_entries", "gedo_type", 40),
    ("gl_subledger_balances", "gf_ref", 50),
    ("jobs", "name_en", 80),
    ("prescriptions", "doctor_specialty", 100),
    ("product_groups", "name_en", 100),
    ("products", "fast_code", 20),
    ("products", "name_en", 150),
    ("products", "scientific_name", 200),
    ("promo_codes", "description_en", 200),
    ("purchases", "bill_number", 50),
    ("shareholders", "name_en", 150),
    ("social_posts", "body_en", 2000),
    ("social_posts", "title", 120),
    ("titan_drugs", "category", 80),
    ("titan_drugs", "manufacturer", 40),
    ("titan_drugs", "name_en", 60),
    ("titan_drugs", "scientific_name", 80),
    ("units", "name_en", 50),
    ("vendors", "name_en", 100),
]
_ARABIC_UNICODE_COLUMNS = (
    _ARABIC_UNICODE_COLUMNS_PART1
    + _ARABIC_UNICODE_COLUMNS_PART2
    + _ARABIC_UNICODE_COLUMNS_PART3
)

# sys.types names that already store Unicode — nothing to do for these.
_UNICODE_TYPES = {"nvarchar", "nchar", "ntext"}


def _mssql_text_column(conn, table: str, column: str):
    """Return (typ, max_length, is_nullable) for a column, or None if absent."""
    return conn.execute(
        text(
            """
            SELECT ty.name AS typ, c.max_length AS ml, c.is_nullable AS nul
            FROM sys.columns c
            JOIN sys.types ty ON ty.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(:t) AND c.name = :c
            """
        ),
        {"t": table, "c": column},
    ).first()


def _mssql_column_is_constrained(conn, table: str, column: str) -> bool:
    """True when the column backs a PK / unique index or constraint.

    ALTER COLUMN through one of those needs the constraint dropped and rebuilt,
    which is a different (and riskier) operation than a type widening. Such a
    column is left alone and reported rather than silently restructured.
    """
    return bool(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sys.indexes i
                JOIN sys.index_columns ic
                  ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                JOIN sys.columns c
                  ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                WHERE i.object_id = OBJECT_ID(:t)
                  AND c.name = :c
                  AND (i.is_primary_key = 1 OR i.is_unique_constraint = 1 OR i.is_unique = 1)
                """
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def _mssql_plain_indexes_on(conn, table: str, column: str) -> list[tuple[str, str]]:
    """Return [(index_name, create_sql)] for the non-unique indexes covering
    ``column``. SQL Server refuses ALTER COLUMN while an index covers the
    column, so each one is dropped and rebuilt around the change.
    """
    rows = conn.execute(
        text(
            """
            SELECT i.name AS idx,
                   STUFF((SELECT ',' + QUOTENAME(c2.name)
                          FROM sys.index_columns ic2
                          JOIN sys.columns c2
                            ON c2.object_id = ic2.object_id AND c2.column_id = ic2.column_id
                          WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id
                            AND ic2.is_included_column = 0
                          ORDER BY ic2.key_ordinal
                          FOR XML PATH('')), 1, 1, '') AS key_cols
            FROM sys.indexes i
            WHERE i.object_id = OBJECT_ID(:t)
              AND i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.is_unique = 0
              AND i.type IN (1, 2)
              AND EXISTS (SELECT 1 FROM sys.index_columns ic
                          JOIN sys.columns c
                            ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                          WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
                            AND c.name = :c)
            """
        ),
        {"t": table, "c": column},
    ).all()
    return [
        (r.idx, f"CREATE INDEX [{r.idx}] ON [{table}] ({r.key_cols})")
        for r in rows
        if r.idx and r.key_cols
    ]


def ensure_arabic_columns_unicode(engine) -> None:
    """Widen VARCHAR to NVARCHAR for columns that carry Arabic text.

    ProCare's database collation (SQL_Latin1_General_CP1_CI_AS) has no Arabic
    in its codepage, so a plain VARCHAR column can only store what that
    codepage covers — every Arabic character is replaced by '?' AT WRITE TIME,
    silently and unrecoverably. NVARCHAR stores Unicode regardless of
    collation, which matches how eStock's own source tables already work
    (Arabic_CI_AS).

    Widening the column type does not rewrite existing row values; a follow-up
    data refresh from eStock repopulates the affected text columns with
    correctly stored Arabic (``tools/repair_arabic.py``).

    Idempotent: skips a column already NVARCHAR/NTEXT and any table that
    doesn't exist yet; no-op on SQLite (dev), which has one text type.
    """
    if engine.dialect.name != "mssql":
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for table, column, size in _ARABIC_UNICODE_COLUMNS:
        if table not in tables:
            continue
        try:
            with engine.begin() as conn:
                meta = _mssql_text_column(conn, table, column)
                if meta is None or meta.typ in _UNICODE_TYPES:
                    continue
                if _mssql_column_is_constrained(conn, table, column):
                    log.warning(
                        "arabic-unicode: skipping %s.%s - backs a unique/primary index",
                        table,
                        column,
                    )
                    continue
                # max_length is in BYTES; -1 means varchar(max) -> nvarchar(max).
                # Never shrink: the declared size is a floor, not a cap.
                if size is None or int(meta.ml) == -1 or meta.typ == "text":
                    target = "NVARCHAR(MAX)"
                else:
                    target = f"NVARCHAR({max(int(size), int(meta.ml))})"
                nullness = "NULL" if meta.nul else "NOT NULL"

                indexes = _mssql_plain_indexes_on(conn, table, column)
                for idx_name, _ in indexes:
                    conn.execute(text(f"DROP INDEX [{idx_name}] ON [{table}]"))
                conn.execute(
                    text(f"ALTER TABLE [{table}] ALTER COLUMN [{column}] {target} {nullness}")
                )
                for _, create_sql in indexes:
                    conn.execute(text(create_sql))
                log.info("arabic-unicode: %s.%s %s -> %s", table, column, meta.typ, target)
        except Exception as e:  # noqa: BLE001 - one bad column must not stop startup
            log.warning("arabic-unicode: could not convert %s.%s: %s", table, column, e)
