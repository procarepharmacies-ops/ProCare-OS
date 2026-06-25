"""Data-access layer for ProCare OS.

Two backends, one interface:

* **demo** (default) — a local SQLite database seeded with realistic synthetic
  data, so the dashboard, alerts and AI assistant all work out of the box with
  no SQL Server required. Lives at ``data/procare_demo.sqlite`` (git-ignored).
* **procare** (production) — ProCare's own SQL Server database, used when
  ``config/connections.json`` has real ``procare_database`` credentials *and*
  the ``pyodbc`` driver is importable. Read/write system of record.

Both expose the same ``query(sql, params) -> list[dict]`` using ``?`` (qmark)
placeholders — native to SQLite and to pyodbc (SQL Server's DBAPI), so the SQL
in ``queries.py`` and the AI assistant is portable across both. The only
dialect-specific objects are the SQL views (date functions); the SQLite views
ship here and the SQL Server equivalents are applied at deployment.

ProCare NEVER writes to the eStock database — that read-only source is reached
only through ``etl.py``. This module owns ProCare's *own* database.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.config import settings

# db.py -> app -> backend
BACKEND_DIR = Path(__file__).resolve().parents[1]
SQL_DIR = Path(__file__).resolve().parent / "sql"
DATA_DIR = BACKEND_DIR / "data"

SCHEMA_FILE = SQL_DIR / "schema_sqlite.sql"
VIEWS_FILE = SQL_DIR / "views_sqlite.sql"


def _demo_db_path() -> Path:
    import os

    override = os.environ.get("PROCARE_DEMO_DB")
    return Path(override) if override else (DATA_DIR / "procare_demo.sqlite")


class Database:
    """Thin facade over either SQLite (demo) or SQL Server (procare)."""

    def __init__(self) -> None:
        self.mode = "demo"
        self._engine = None  # SQLAlchemy engine when mode == 'procare'
        self._sqlite_path = _demo_db_path()
        self._lock = threading.Lock()
        self._select_engine()

    # -- backend selection ---------------------------------------------------
    def _select_engine(self) -> None:
        """Use SQL Server only when configured AND the driver is importable."""
        if not settings.procare_configured:
            return
        try:
            import sqlalchemy  # noqa: F401  (driver presence check)
            import pyodbc  # noqa: F401
        except Exception:
            # Configured but driver missing -> stay in demo mode (safe default).
            return
        block = settings.procare_connection()
        if not block:
            return
        try:
            from sqlalchemy import create_engine

            odbc = (
                f"DRIVER={{{block['driver']}}};SERVER={block['server']};"
                f"DATABASE={block['database']};UID={block['username']};"
                f"PWD={block['password']};Encrypt={block.get('encrypt', 'yes')};"
                f"TrustServerCertificate={block.get('trust_server_certificate', 'yes')}"
            )
            from urllib.parse import quote_plus

            self._engine = create_engine(
                "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc),
                pool_pre_ping=True,
            )
            self.mode = "procare"
        except Exception:
            self._engine = None
            self.mode = "demo"

    # -- demo lifecycle ------------------------------------------------------
    def demo_db_exists(self) -> bool:
        return self._sqlite_path.exists()

    def _connect_sqlite(self) -> sqlite3.Connection:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._sqlite_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def apply_schema(self) -> None:
        """Create tables + views in the demo SQLite database (idempotent)."""
        if self.mode != "demo":
            return
        with self._lock:
            conn = self._connect_sqlite()
            try:
                conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
                conn.executescript(VIEWS_FILE.read_text(encoding="utf-8"))
                conn.commit()
            finally:
                conn.close()

    # -- query interface (read) ---------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run a read query. ``?`` placeholders; returns a list of dicts."""
        if self.mode == "demo":
            conn = self._connect_sqlite()
            try:
                cur = conn.execute(sql, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
        # SQL Server via SQLAlchemy -> raw DBAPI (pyodbc) keeps ``?`` qmark.
        from sqlalchemy import text  # noqa: F401  (imported lazily)

        with self._engine.connect() as conn:  # type: ignore[union-attr]
            result = conn.exec_driver_sql(sql, tuple(params))
            cols = list(result.keys())
            return [dict(zip(cols, row)) for row in result.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # -- write interface (demo seed / writes) -------------------------------
    def executemany(self, sql: str, rows: list[tuple]) -> None:
        if self.mode != "demo":
            raise RuntimeError("executemany is only used for the demo seed path")
        with self._lock:
            conn = self._connect_sqlite()
            try:
                conn.executemany(sql, rows)
                conn.commit()
            finally:
                conn.close()

    def execute(self, sql: str, params: tuple = ()) -> int:
        if self.mode != "demo":
            raise RuntimeError("execute is only used for the demo seed path")
        with self._lock:
            conn = self._connect_sqlite()
            try:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def connection(self) -> sqlite3.Connection:
        """Raw SQLite connection for the seed loader (demo only)."""
        if self.mode != "demo":
            raise RuntimeError("Direct connection is demo-only")
        return self._connect_sqlite()


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def reset_db_for_tests(path: str) -> Database:
    """Point the singleton at a throwaway SQLite file (used by the test suite)."""
    global _db
    import os

    os.environ["PROCARE_DEMO_DB"] = path
    _db = Database()
    _db.apply_schema()
    return _db
