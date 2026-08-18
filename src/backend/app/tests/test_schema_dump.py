"""Phase 7 tests: the read-only eStock schema-dump / coverage tool."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from tools import estock_schema_dump as dumptool  # noqa: E402


def _source(path):
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        # One table the ETL covers, one it does not.
        c.execute(text("CREATE TABLE Products (product_id INT, product_name_ar TEXT, sell_price REAL)"))
        c.execute(text("INSERT INTO Products VALUES (1,'صنف',10.0)"))
        c.execute(text("CREATE TABLE Employee_daily_time (edt_id INT, emp_id INT, work_date DATE, hours REAL)"))
        c.execute(text("INSERT INTO Employee_daily_time VALUES (1,1,'2026-01-01',8.0),(2,1,'2026-01-02',7.5)"))
    return eng


def test_dump_flags_coverage_and_columns(tmp_path):
    eng = _source(tmp_path / "estock.db")
    try:
        dump = dumptool.dump_schema(eng, with_counts=True)
        assert dump["total_tables"] == 2
        # Products is in COVERED_SOURCE_TABLES; Employee_daily_time is deliberately not.
        assert "Products" in dump["covered"]
        assert "Employee_daily_time" in dump["uncovered"]
        assert dump["covered_count"] == 1 and dump["uncovered_count"] == 1

        products = next(t for t in dump["tables"] if t["name"] == "Products")
        assert {c["name"] for c in products["columns"]} == {"product_id", "product_name_ar", "sell_price"}
        assert products["row_count"] == 1

        edt = next(t for t in dump["tables"] if t["name"] == "Employee_daily_time")
        assert edt["row_count"] == 2 and edt["covered"] is False
    finally:
        eng.dispose()


def test_coverage_is_case_insensitive(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'ci.db'}")
    try:
        with eng.begin() as c:
            c.execute(text("CREATE TABLE products (id INT)"))  # lowercase
        dump = dumptool.dump_schema(eng)
        assert "products" in dump["covered"]  # matched despite casing
    finally:
        eng.dispose()


def test_render_markdown_has_gap_section(tmp_path):
    eng = _source(tmp_path / "md.db")
    try:
        md = dumptool.render_markdown(dumptool.dump_schema(eng))
        assert "Coverage gap" in md
        assert "Employee_daily_time" in md
        assert "✅ `Products`" in md
    finally:
        eng.dispose()


def test_the_documented_invocation_actually_runs(tmp_path):
    """The tool is the ONLY thing standing between us and the parked mirrors
    (Gedo_* sub-ledgers, EMP_CONTROL), and an operator reaches it by running
    the command in its docstring / the .bat. That command lives at the REPO
    ROOT: `src/backend` holds a SECOND, unrelated `tools` package, so
    `-m tools.estock_schema_dump` from there resolves to the wrong one and
    dies with ModuleNotFoundError — which is how this stayed un-run. Pin the
    working invocation so a future reshuffle fails here, not on the pharmacy
    PC at the moment someone finally tries it.
    """
    import subprocess

    repo_root = Path(__file__).resolve().parents[4]
    assert (repo_root / "tools" / "estock_schema_dump.py").exists(), (
        "the tool must stay in the repo-root tools/ — the .bat and docstring point there"
    )

    src = tmp_path / "estock.db"
    _source(src)
    out = tmp_path / "dump.md"
    proc = subprocess.run(
        [sys.executable, "-m", "tools.estock_schema_dump",
         "--url", f"sqlite:///{src}", "--counts", "--out", str(out)],
        cwd=repo_root, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert out.exists() and out.with_suffix(".json").exists()
    body = out.read_text(encoding="utf-8")
    assert "Coverage gap" in body
    assert "Employee_daily_time" in body  # the uncovered table is named


def test_the_bat_invokes_it_from_the_repo_root(tmp_path):
    """deploy/Dump-eStock-Schema.bat must cd to the repo root, not src\\backend
    — the whole point of the fix above."""
    repo_root = Path(__file__).resolve().parents[4]
    bat = (repo_root / "deploy" / "Dump-eStock-Schema.bat").read_text(encoding="utf-8")
    # Look at the actual directory changes, not the prose around them: the
    # comments deliberately MENTION src\backend to explain why it is wrong.
    cds = [ln.strip() for ln in bat.splitlines()
           if ln.strip().lower().startswith("cd ") and not ln.strip().startswith("REM")]
    assert cds == ['cd /d "%~dp0\\.."'], f"expected one cd to the repo root, got {cds}"
    assert "python -m tools.estock_schema_dump" in bat
