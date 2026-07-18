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


def ensure_role_column(engine) -> None:
    """Add ``employees.role`` if the table predates it (default 'assistant',
    the most restrictive tier, so nobody is silently over-privileged)."""
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return  # create_all will make the table with the column already.
    columns = {c["name"] for c in inspector.get_columns("employees")}
    if "role" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE employees ADD COLUMN role VARCHAR(20) DEFAULT 'assistant'"))


def ensure_original_sale_id_column(engine) -> None:
    """Add ``sales.original_sale_id`` (return -> original invoice link) if the
    table predates the sale-returns feature. NULL for all existing rows."""
    inspector = inspect(engine)
    if "sales" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("sales")}
    if "original_sale_id" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE sales ADD COLUMN original_sale_id INTEGER NULL"))


def ensure_shelf_location_column(engine) -> None:
    """Add ``products.shelf_location`` (merchandising place code) if the table
    predates it."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "shelf_location" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE products ADD COLUMN shelf_location VARCHAR(80) NULL"))


def ensure_loyalty_points_column(engine) -> None:
    """Add ``customers.loyalty_points`` (loyalty programme balance) if the
    table predates it. Existing customers start at 0 points."""
    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("customers")}
    if "loyalty_points" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customers ADD COLUMN loyalty_points NUMERIC(18,3) DEFAULT 0"))


def ensure_task_priority_columns(engine) -> None:
    """Add ``employee_tasks.priority`` and ``.category`` if the table predates
    the professional daily-plan upgrade. Existing tasks default to normal/general."""
    inspector = inspect(engine)
    if "employee_tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("employee_tasks")}
    with engine.begin() as conn:
        if "priority" not in columns:
            conn.execute(text("ALTER TABLE employee_tasks ADD COLUMN priority VARCHAR(10) DEFAULT 'normal'"))
        if "category" not in columns:
            conn.execute(text("ALTER TABLE employee_tasks ADD COLUMN category VARCHAR(20) DEFAULT 'general'"))


def ensure_prescription_status_columns(engine) -> None:
    """Add ``prescriptions.status`` + ``.reviewed_by`` if the table predates the
    capture -> review -> dispense workflow. Existing rows become 'captured'."""
    inspector = inspect(engine)
    if "prescriptions" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("prescriptions")}
    with engine.begin() as conn:
        if "status" not in columns:
            conn.execute(text("ALTER TABLE prescriptions ADD COLUMN status VARCHAR(20) DEFAULT 'captured'"))
        if "reviewed_by" not in columns:
            conn.execute(text("ALTER TABLE prescriptions ADD COLUMN reviewed_by INTEGER NULL"))


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


