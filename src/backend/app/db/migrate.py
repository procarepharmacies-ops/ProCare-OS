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
