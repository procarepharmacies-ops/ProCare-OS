"""First-seed helpers: the import decision (pure) + live inspect/backup guards.

``evaluate_readiness`` encodes the rule that actually drives the seeding runbook
— an empty branch CANNOT sync incrementally, because ``etl.mirror`` only takes
its incremental path once the branch already holds sales. That rule is pure and
exercised directly here. ``backup()`` is SQL Server-only, so on the SQLite test
database it must decline cleanly rather than raise.
"""
from __future__ import annotations

from app.services import seeding


# --- evaluate_readiness(): pure decision, no I/O ----------------------------
def test_branch_with_sales_does_not_need_import():
    out = seeding.evaluate_readiness({"ELSANTA": 95_000}, "ELSANTA")
    assert out["needs_import"] is False
    assert out["sales"] == 95_000
    assert "skip" in out["reason"].lower()


def test_empty_branch_needs_import():
    out = seeding.evaluate_readiness({"ELSANTA": 0}, "ELSANTA")
    assert out["needs_import"] is True
    assert out["sales"] == 0
    assert "full" in out["reason"].lower()


def test_branch_absent_entirely_needs_import():
    """A branch the mirror never created is as empty as one with zero sales."""
    out = seeding.evaluate_readiness({}, "ELSANTA")
    assert out["needs_import"] is True
    assert out["sales"] == 0


def test_branch_code_is_normalised():
    """Operators type 'elsanta'; the mirror stores 'ELSANTA'."""
    out = seeding.evaluate_readiness({"ELSANTA": 12}, "  elsanta  ")
    assert out["needs_import"] is False
    assert out["sales"] == 12


def test_other_branches_do_not_satisfy_the_gate():
    """Sales on a DIFFERENT branch must not mark this one as seeded."""
    out = seeding.evaluate_readiness({"MASHALA": 50_000}, "ELSANTA")
    assert out["needs_import"] is True
    assert out["sales"] == 0


def test_none_count_is_treated_as_zero():
    out = seeding.evaluate_readiness({"ELSANTA": None}, "ELSANTA")  # type: ignore[dict-item]
    assert out["needs_import"] is True


# --- inspect(): live against the seeded SQLite test database ----------------
def test_inspect_reports_counts_and_a_decision():
    out = seeding.inspect("ELSANTA")
    assert out["ok"] is True
    assert out["engine"] == "sqlite"
    assert out["branch"] == "ELSANTA"
    assert isinstance(out["counts"], dict)
    assert "products" in out["counts"]
    assert "sales" in out["counts"]
    assert isinstance(out["sales_by_branch"], dict)
    assert "needs_import" in out
    assert isinstance(out["reason"], str) and out["reason"]


def test_inspect_decision_matches_the_pure_rule():
    """inspect() must not invent its own logic — it delegates to the rule."""
    out = seeding.inspect("ELSANTA")
    expected = seeding.evaluate_readiness(out["sales_by_branch"], "ELSANTA")
    assert out["needs_import"] == expected["needs_import"]
    assert out["sales"] == expected["sales"]


# --- backup(): must decline, not explode, on the dev database ---------------
def test_backup_declines_on_sqlite():
    out = seeding.backup("/tmp/should-not-be-written.bak")
    assert out["ok"] is False
    assert out["skipped"] is True
    assert "sqlite" in out["reason"].lower()


def test_backup_rejects_empty_path():
    """Guard the arg before touching the database at all."""
    out = seeding.backup("")
    assert out["ok"] is False
