"""Duplicate eStock usernames must not abort the mirror.

eStock has no unique index on ``Employee.username``; ProCare's column IS unique.
``_load_employees`` builds its ``existing`` map once before the scan, so a newly
created employee has to be registered into it as it is created — otherwise a
second source row carrying the same username queues a SECOND insert, which does
not fail at that point but at the post-loop flush, as a unique violation.

That distinction is the whole reason this matters: the mirror runs as ONE
transaction (a single commit at the end of ``mirror``), so the violation does not
cost one employee — it rolls back every table already loaded.

The fixtures here use per-test unique usernames rather than transactional
isolation, because ``conftest.seeded_db`` is session-scoped: the whole suite
shares one seeded database.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import etl


class _FakeInspector:
    """Minimal ``inspect()`` stand-in: one Employee table with the given columns."""

    def __init__(self, columns: list[str]):
        self._columns = columns

    def has_table(self, name: str) -> bool:
        return name == "Employee"

    def get_columns(self, name: str):
        return [{"name": c} for c in self._columns]


class _FakeSource:
    """Returns fixed eStock rows for the ``SELECT * FROM Employee`` scan."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def execute(self, statement, parameters=None):
        return self

    def mappings(self):
        return self

    def all(self):
        return self._rows


@pytest.fixture()
def dst():
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def uname():
    """A username unique to this test — the suite shares one database."""
    return f"dup{uuid.uuid4().hex[:10]}"


def _run(dst, rows: list[dict]) -> dict:
    counts: dict = {}
    etl._load_employees(
        _FakeInspector(["username", "emp_name_ar", "active"]),
        _FakeSource(rows),
        dst,
        counts,
    )
    return counts


def _count_with_username(dst, name: str) -> int:
    return int(
        dst.execute(
            select(func.count(m.Employee.employee_id)).where(
                func.lower(m.Employee.username) == name.lower()
            )
        ).scalar()
        or 0
    )


def test_duplicate_username_does_not_raise(dst, uname):
    """The regression: a repeated username must not blow up the mirror."""
    counts = _run(
        dst,
        [
            {"username": uname, "emp_name_ar": "أول", "active": "Y"},
            {"username": uname, "emp_name_ar": "ثانى", "active": "Y"},
        ],
    )
    assert counts["employees"] == 1, "the repeat must not be inserted twice"
    assert _count_with_username(dst, uname) == 1


def test_second_row_updates_the_first_rather_than_being_dropped(dst, uname):
    """Dedup routes the repeat through the update path — its fields must land."""
    _run(
        dst,
        [
            {"username": uname, "emp_name_ar": "أول", "active": "Y"},
            {"username": uname, "emp_name_ar": "ثانى", "active": "Y"},
        ],
    )
    name = dst.execute(
        select(m.Employee.name_ar).where(m.Employee.username == uname)
    ).scalar_one()
    assert name == "ثانى"


def test_rows_after_a_duplicate_still_load(dst, uname):
    """A duplicate must not truncate the rest of the scan."""
    later = f"{uname}after"
    counts = _run(
        dst,
        [
            {"username": uname, "emp_name_ar": "أول", "active": "Y"},
            {"username": uname, "emp_name_ar": "ثانى", "active": "Y"},
            {"username": later, "emp_name_ar": "بعد", "active": "Y"},
        ],
    )
    assert counts["employees"] == 2
    assert _count_with_username(dst, later) == 1


def test_case_and_whitespace_variants_are_deduped(dst, uname):
    """``existing`` is keyed on stripped-lowercase, so these are one user."""
    counts = _run(
        dst,
        [
            {"username": uname.upper(), "emp_name_ar": "أ", "active": "Y"},
            {"username": f"  {uname}  ", "emp_name_ar": "ب", "active": "Y"},
        ],
    )
    assert counts["employees"] == 1
    assert _count_with_username(dst, uname) == 1


def test_three_way_duplicate_still_yields_one_row(dst, uname):
    counts = _run(
        dst,
        [
            {"username": uname, "emp_name_ar": "١", "active": "Y"},
            {"username": uname, "emp_name_ar": "٢", "active": "Y"},
            {"username": uname, "emp_name_ar": "٣", "active": "Y"},
        ],
    )
    assert counts["employees"] == 1
    assert counts["employees_updated"] == 2
    assert _count_with_username(dst, uname) == 1


def test_existing_procare_password_is_never_overwritten(dst, uname):
    """A real ProCare login must survive the mirror (the lockout guard)."""
    dst.add(
        m.Employee(
            username=uname,
            password_hash="pbkdf2$200000$abc$def",
            role="ceo",
            name_ar="حقيقي",
            is_active=True,
        )
    )
    dst.flush()

    _run(dst, [{"username": uname, "emp_name_ar": "من eStock", "active": "N"}])

    emp = dst.execute(
        select(m.Employee).where(m.Employee.username == uname)
    ).scalar_one()
    assert emp.password_hash == "pbkdf2$200000$abc$def"
    # eStock's active/deleted state must not disable a real ProCare login.
    assert emp.is_active is True


def test_mirrored_employee_gets_an_unusable_password(dst, uname):
    """eStock plaintext passwords are never imported."""
    _run(dst, [{"username": uname, "emp_name_ar": "جديد", "active": "Y"}])
    emp = dst.execute(
        select(m.Employee).where(m.Employee.username == uname)
    ).scalar_one()
    assert emp.password_hash.startswith("!")
    assert emp.role == "assistant"


def test_blank_usernames_are_skipped(dst, uname):
    counts = _run(
        dst,
        [
            {"username": "", "emp_name_ar": "فارغ", "active": "Y"},
            {"username": None, "emp_name_ar": "لا شيء", "active": "Y"},
            {"username": uname, "emp_name_ar": "صحيح", "active": "Y"},
        ],
    )
    assert counts["employees"] == 1


def test_missing_employee_table_is_a_no_op(dst):
    class NoTable:
        def has_table(self, name):
            return False

    counts: dict = {}
    etl._load_employees(NoTable(), _FakeSource([]), dst, counts)
    assert counts["employees"] == 0
