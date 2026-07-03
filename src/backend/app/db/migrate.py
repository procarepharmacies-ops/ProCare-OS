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
    aliases = {"mashal": ("mashal", "mashala", "mas-hala", "مشعل"), "santa": ("santa", "elsanta", "السنتا")}
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
