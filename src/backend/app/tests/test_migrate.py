"""Schema migration + first-account bootstrap — the safety net for pharmacies
whose ``employees`` table predates the login feature (missing ``role``
column) or whose production DB was populated by eStock sync (which never
mirrors employees, so login would otherwise be impossible)."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db.migrate import bootstrap_ceo_if_configured, ensure_role_column


def test_ensure_role_column_adds_missing_column(tmp_path):
    # Simulate a pharmacy's pre-login-feature DB: create the employees table
    # via raw SQL without the role column that the current model expects.
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE employees (employee_id INTEGER PRIMARY KEY, "
            "name_ar VARCHAR(100), username VARCHAR(50), password_hash VARCHAR(255))"
        )
    ensure_role_column(eng)
    columns = {c["name"] for c in inspect(eng).get_columns("employees")}
    assert "role" in columns


def test_ensure_role_column_is_a_noop_when_already_present(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    Base.metadata.create_all(eng)  # current model already has role
    ensure_role_column(eng)  # must not raise
    columns = {c["name"] for c in inspect(eng).get_columns("employees")}
    assert "role" in columns


def test_ensure_role_column_is_a_noop_when_table_absent(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    ensure_role_column(eng)  # no employees table at all -> must not raise


def test_bootstrap_creates_ceo_only_when_env_and_table_empty(monkeypatch, tmp_path):
    # Isolated DB — must not touch the shared dev DB other tests rely on.
    from sqlalchemy.orm import sessionmaker
    from app.db import models as m

    eng = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)

    with Session() as s:
        monkeypatch.delenv("BOOTSTRAP_CEO_USERNAME", raising=False)
        monkeypatch.delenv("BOOTSTRAP_CEO_PASSWORD", raising=False)
        bootstrap_ceo_if_configured(s)
        assert s.query(m.Employee).count() == 0  # no env vars -> no-op

        monkeypatch.setenv("BOOTSTRAP_CEO_USERNAME", "owner")
        monkeypatch.setenv("BOOTSTRAP_CEO_PASSWORD", "s3cret!")
        bootstrap_ceo_if_configured(s)
        emp = s.query(m.Employee).filter_by(username="owner").one()
        assert emp.role == "ceo"

        # Second call must not duplicate the account (table no longer empty).
        bootstrap_ceo_if_configured(s)
        assert s.query(m.Employee).filter_by(username="owner").count() == 1
