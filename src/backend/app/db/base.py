"""Database engine + session for ProCare's OWN database.

ProCare is a standalone system of record. In production it runs on SQL Server
(see ``sql/procare-schema.sql``); for development, demos and CI it runs on a
local SQLite file so the whole stack is runnable with zero infrastructure.

The choice is driven by ``settings.procare_url``:
  * If ``procare_database`` in ``config/connections.json`` has real SQL Server
    credentials, ProCare connects there via pyodbc.
  * Otherwise it falls back to ``data/procare.db`` (SQLite) — the default that
    lets ``run.py`` start with no setup.

eStock and Titan/Drug-Eye are NEVER reached from here; they are read-only
*sources* handled separately by ``app.services.etl`` (a pluggable adapter that
only activates when real read-only credentials are present).
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# backend/app/db -> backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


def _build_url() -> str:
    """Return the SQLAlchemy URL for ProCare's own DB.

    ``PROCARE_DB_URL`` (env) wins — the test suite sets it to an isolated SQLite
    file so tests can NEVER drop/reseed a configured production SQL Server.
    Otherwise: SQL Server when real credentials exist, else the SQLite dev file.
    """
    override = os.environ.get("PROCARE_DB_URL")
    if override:
        return override
    sqlserver_url = settings.procare_sqlalchemy_url()
    if sqlserver_url:
        return sqlserver_url
    return f"sqlite:///{DATA_DIR / 'procare.db'}"


DATABASE_URL = _build_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_MSSQL = DATABASE_URL.startswith("mssql")

# SQL Server bulk-load accelerator: pyodbc's default executemany sends one
# round-trip per row, so a full mirror (95K+ sales, 184K+ sale lines) crawls.
# fast_executemany batches parameter arrays into a single call — a large speedup
# for the ETL's add_all/flush, exactly the co-hosted-2008 scenario. mssql+pyodbc
# only; harmless to omit elsewhere.
_engine_kwargs = {"fast_executemany": True} if IS_MSSQL else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    **_engine_kwargs,
    # SQL Server can drop a pooled connection at any time (server restart, the
    # sync thread's transaction being KILLed, an idle-timeout, a network blip).
    # Without a liveness check the pool hands out a dead connection and the
    # request 500s with "Communication link failure (08S01)". pool_pre_ping
    # issues a cheap SELECT 1 before every checkout and transparently replaces a
    # stale connection, so the dashboard survives a sync/restart underneath it —
    # the "pharmacy never waits on sync" invariant, connection-level. Harmless on
    # SQLite (single-file, always live), so applied unconditionally.
    pool_pre_ping=not IS_SQLITE,
    pool_recycle=1800 if not IS_SQLITE else -1,
)


if IS_SQLITE:
    # SQLite ignores foreign keys unless told otherwise; ProCare's whole premise
    # is real referential integrity, so enforce it here too. WAL journaling +
    # a busy_timeout let the lifespan seeding session, the background sync
    # thread and concurrent HTTP requests share the single-file DB without
    # tripping "database is locked" (the default rollback-journal allows only
    # one writer and blocks readers mid-write).
    @event.listens_for(engine, "connect")
    def _enable_sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL: a writer never blocks readers, and concurrent connections can
        # each make progress instead of serialising on a journal lock.
        cursor.execute("PRAGMA journal_mode=WAL")
        # Wait (ms) for a lock to clear instead of immediately raising
        # OperationalError "database is locked" under contention.
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ProCare ORM models."""


def get_session():
    """FastAPI dependency: yields a session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
