"""Phase 6: eStock ``Jobs`` master mirror + employee job-title linkage.

Columns are fully enumerated in docs/CLAUDE_CODE_ESTOCK_STRUCTURE.md §2
(``job_id, job_code, job_name_ar/en``), so — unlike the parked Gedo_* ledgers —
this mirror is built on documented shapes rather than guesses.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db import estock_seed, models as m
from app.db.base import Base, SessionLocal
from app.db.migrate import ensure_job_source_columns
from app.db.seed import reset_and_seed
from app.services import etl, sync


@pytest.fixture
def estock_source(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'estock_jobs.db'}")
    estock_seed.seed_estock_source(eng, days=5)
    yield eng
    eng.dispose()


def _add_jobs_and_employees(eng, *, jobs_rows: str, employee_rows: str) -> None:
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE Jobs (job_id INTEGER PRIMARY KEY, job_code TEXT, "
            "job_name_ar TEXT, job_name_en TEXT)"
        ))
        c.execute(text(f"INSERT INTO Jobs VALUES {jobs_rows}"))
        c.execute(text(
            "CREATE TABLE Employee (emp_id INTEGER PRIMARY KEY, emp_name_ar TEXT, "
            "emp_name_en TEXT, username TEXT, pass TEXT, job_id INTEGER, active TEXT, "
            "deleted TEXT)"
        ))
        c.execute(text(f"INSERT INTO Employee VALUES {employee_rows}"))


def test_jobs_mirror_links_employee_to_their_title(estock_source):
    _add_jobs_and_employees(
        estock_source,
        jobs_rows="(1, 'PH', 'صيدلي', 'Pharmacist'), (2, 'CASH', 'كاشير', 'Cashier')",
        employee_rows=(
            "(1, 'سارة', 'Sara', 'sara.estock', 'pw', 1, '1', '0'), "
            "(2, 'كريم', 'Karim', 'karim.estock', 'pw', 2, '1', '0')"
        ),
    )
    try:
        counts = sync.run_once(source_engine=estock_source)["counts"]["source"]
        assert counts["jobs"] >= 1

        with SessionLocal() as s:
            sara = s.query(m.Employee).filter(m.Employee.username == "sara.estock").one()
            job = s.get(m.Job, sara.job_id)
            assert job is not None, "the employee must be linked to a mirrored title"
            assert job.name_ar == "صيدلي"
            assert job.name_en == "Pharmacist"
            assert job.code == "PH"
            assert job.source_id == 1
    finally:
        reset_and_seed()


def test_rerunning_updates_titles_instead_of_duplicating(estock_source):
    _add_jobs_and_employees(
        estock_source,
        jobs_rows="(1, 'PH', 'صيدلي', 'Pharmacist')",
        employee_rows="(1, 'سارة', 'Sara', 'sara.estock', 'pw', 1, '1', '0')",
    )
    try:
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            before = s.query(m.Job).count()

        # The owner renames the title on eStock; the next cycle must follow it
        # in place, not add a second row.
        with estock_source.begin() as c:
            c.execute(text("UPDATE Jobs SET job_name_ar = 'صيدلي أول' WHERE job_id = 1"))

        counts = sync.run_once(source_engine=estock_source)["counts"]["source"]
        assert counts["jobs"] == 0  # nothing created
        assert counts["jobs_updated"] >= 1

        with SessionLocal() as s:
            assert s.query(m.Job).count() == before
            assert s.query(m.Job).filter(m.Job.source_id == 1).one().name_ar == "صيدلي أول"
    finally:
        reset_and_seed()


def test_seeded_titles_are_matched_by_name_not_duplicated(estock_source):
    """seed.py creates 'مدير'/'كاشير' with no source id. The mirror must adopt
    those rows rather than create a second 'كاشير' beside them."""
    with SessionLocal() as s:
        seeded = s.query(m.Job).filter(m.Job.name_ar == "كاشير").one()
        seeded_id = seeded.job_id
        assert seeded.source_id is None

    _add_jobs_and_employees(
        estock_source,
        jobs_rows="(7, 'CASH', 'كاشير', 'Cashier')",
        employee_rows="(1, 'كريم', 'Karim', 'karim.estock', 'pw', 7, '1', '0')",
    )
    try:
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            assert s.query(m.Job).filter(m.Job.name_ar == "كاشير").count() == 1
            adopted = s.get(m.Job, seeded_id)
            assert adopted.source_id == 7  # the seeded row now carries the source id
            karim = s.query(m.Employee).filter(m.Employee.username == "karim.estock").one()
            assert karim.job_id == seeded_id
    finally:
        reset_and_seed()


def test_unknown_job_id_leaves_the_employee_unlinked(estock_source):
    """A dangling source job_id must not write a broken FK."""
    _add_jobs_and_employees(
        estock_source,
        jobs_rows="(1, 'PH', 'صيدلي', 'Pharmacist')",
        employee_rows="(1, 'نور', 'Nour', 'nour.estock', 'pw', 999, '1', '0')",
    )
    try:
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            nour = s.query(m.Employee).filter(m.Employee.username == "nour.estock").one()
            assert nour.job_id is None
    finally:
        reset_and_seed()


def test_source_without_a_jobs_table_is_skipped_not_an_error(estock_source):
    """Older eStock builds may not carry Jobs — the mirror must go on."""
    with estock_source.begin() as c:
        c.execute(text(
            "CREATE TABLE Employee (emp_id INTEGER PRIMARY KEY, emp_name_ar TEXT, "
            "emp_name_en TEXT, username TEXT, pass TEXT, job_id INTEGER, active TEXT, "
            "deleted TEXT)"
        ))
        c.execute(text("INSERT INTO Employee VALUES (1, 'هند', 'Hind', 'hind.estock', 'pw', 3, '1', '0')"))
    try:
        res = sync.run_once(source_engine=estock_source)
        assert res["ran"] is True
        counts = res["counts"]["source"]
        assert counts["jobs"] == 0
        with SessionLocal() as s:
            assert s.query(m.Employee).filter(m.Employee.username == "hind.estock").one().job_id is None
    finally:
        reset_and_seed()


def test_jobs_survive_a_full_refresh(estock_source):
    """Employees are never wiped, so their titles must not be either — Job is
    deliberately absent from etl._WIPE_ORDER."""
    assert m.Job not in [t for t in etl._WIPE_ORDER if t is not None]


def test_employee_api_exposes_the_title_in_both_languages(client):
    with SessionLocal() as s:
        job = m.Job(name_ar="محاسب", name_en="Accountant", source_id=42, code="ACC")
        s.add(job)
        s.flush()
        emp = s.query(m.Employee).first()
        emp.job_id = job.job_id
        s.commit()
        employee_id = emp.employee_id

    try:
        row = next(
            e for e in client.get("/api/employees/list").json()["employees"]
            if e["employee_id"] == employee_id
        )
        # job_name is kept for existing callers; the pair is what lets the UI
        # label the title in whichever language it is rendering.
        assert row["job_name"] == "محاسب"
        assert row["job_name_ar"] == "محاسب"
        assert row["job_name_en"] == "Accountant"
    finally:
        reset_and_seed()


# --- migration --------------------------------------------------------------
def test_ensure_job_source_columns_adds_them_to_a_legacy_table(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy_jobs.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE jobs (job_id INTEGER PRIMARY KEY, name_ar VARCHAR(80), "
            "name_en VARCHAR(80))"
        )
    ensure_job_source_columns(eng)
    columns = {c["name"] for c in inspect(eng).get_columns("jobs")}
    assert {"source_id", "code"} <= columns

    ensure_job_source_columns(eng)  # idempotent


def test_ensure_job_source_columns_noop_on_current_schema_and_missing_table(tmp_path):
    fresh = create_engine(f"sqlite:///{tmp_path / 'fresh_jobs.db'}")
    Base.metadata.create_all(fresh)
    ensure_job_source_columns(fresh)  # must not raise

    empty = create_engine(f"sqlite:///{tmp_path / 'no_jobs.db'}")
    ensure_job_source_columns(empty)  # no jobs table at all -> must not raise
