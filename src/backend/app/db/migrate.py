"""Lightweight, dependency-free schema migration + first-account bootstrap.

This app has no formal migration tool (no Alembic) — ``Base.metadata.create_all``
only creates missing *tables*, never adds columns to a table that already
exists. That's exactly the situation the login feature introduced: pharmacies
already running ProCare have an ``employees`` table without the new ``role``
column. Run once at startup, idempotent, safe on SQLite and SQL Server.
"""
from __future__ import annotations

import os

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import auth as auth_svc


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




