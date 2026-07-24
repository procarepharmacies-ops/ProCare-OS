"""Read-only eStock schema dump + ProCare coverage report.

Run this ONCE on the Elsanta branch server (or against any restored eStock
backup) to capture the live schema and see exactly which source tables ProCare
mirrors and which it doesn't — closing the "how much of eStock do we cover?"
blind spot with real data instead of guesses.

Strictly READ-ONLY: it only inspects table/column metadata (via SQLAlchemy's
dialect-agnostic Inspector, so it works on SQL Server 2008 and SQLite alike) and
optionally COUNT(*)s. It never writes to eStock.

Usage (from src/backend, with config/connections.json pointing at eStock):
    python -m tools.estock_schema_dump                 # metadata only
    python -m tools.estock_schema_dump --counts        # + row counts (slower)
    python -m tools.estock_schema_dump --url "sqlite:///…"   # explicit source
    python -m tools.estock_schema_dump --out docs/estock-schema-dump.md

Writes a Markdown report (and a .json beside it) listing every table, its
columns, row counts (if requested), and a COVERAGE section flagging the tables
ProCare's ETL does not yet read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# Import path shim so the tool runs both as `-m tools.estock_schema_dump` from
# src/backend and directly. COVERED_SOURCE_TABLES is the single source of truth
# for what the ETL reads (kept next to the _load_* functions).
try:
    from app.services.etl import COVERED_SOURCE_TABLES
except ModuleNotFoundError:  # run from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
    from app.services.etl import COVERED_SOURCE_TABLES


def dump_schema(engine: Engine, with_counts: bool = False) -> dict:
    """Inspect every table + its columns; flag ETL coverage; optional row counts.

    Coverage is matched case-insensitively (SQL Server is case-insensitive on
    identifiers) so a table's casing on the server doesn't hide a match."""
    insp = inspect(engine)
    covered_lower = {t.lower() for t in COVERED_SOURCE_TABLES}
    tables = []
    for name in sorted(insp.get_table_names()):
        columns = [
            {"name": c["name"], "type": str(c["type"]), "nullable": bool(c.get("nullable", True))}
            for c in insp.get_columns(name)
        ]
        row = {
            "name": name,
            "columns": columns,
            "column_count": len(columns),
            "covered": name.lower() in covered_lower,
        }
        if with_counts:
            try:
                with engine.connect() as conn:
                    row["row_count"] = int(conn.execute(text(f"SELECT COUNT(*) FROM [{name}]")).scalar() or 0)
            except Exception:  # noqa: BLE001 — a count failing must not abort the dump
                row["row_count"] = None
        tables.append(row)

    covered = [t for t in tables if t["covered"]]
    uncovered = [t for t in tables if not t["covered"]]
    return {
        "total_tables": len(tables),
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "covered": [t["name"] for t in covered],
        "uncovered": [t["name"] for t in uncovered],
        "tables": tables,
    }


def render_markdown(dump: dict) -> str:
    lines = [
        "# eStock schema dump + ProCare coverage",
        "",
        f"- **Total tables:** {dump['total_tables']}",
        f"- **Mirrored by ProCare's ETL:** {dump['covered_count']}",
        f"- **Not yet mirrored:** {dump['uncovered_count']}",
        "",
        "## Coverage gap (tables ProCare does NOT read)",
        "",
    ]
    if dump["uncovered"]:
        for name in dump["uncovered"]:
            t = next(t for t in dump["tables"] if t["name"] == name)
            rc = t.get("row_count")
            rc_s = f" — {rc:,} rows" if isinstance(rc, int) else ""
            lines.append(f"- `{name}` ({t['column_count']} cols){rc_s}")
    else:
        lines.append("_None — every source table is mirrored._")
    lines += ["", "## All tables", ""]
    for t in dump["tables"]:
        mark = "✅" if t["covered"] else "🔲"
        rc = t.get("row_count")
        rc_s = f" · {rc:,} rows" if isinstance(rc, int) else ""
        lines.append(f"### {mark} `{t['name']}`{rc_s}")
        lines.append("")
        for c in t["columns"]:
            null = "NULL" if c["nullable"] else "NOT NULL"
            lines.append(f"- `{c['name']}` {c['type']} {null}")
        lines.append("")
    return "\n".join(lines)


def _resolve_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    from app.config import settings

    sources = settings.estock_sources()
    if not sources:
        raise SystemExit(
            "No eStock source configured. Fill config/connections.json (estock_source/"
            "estock_sources) or pass --url."
        )
    return sources[0]["url"]


def main(argv: list[str]) -> int:
    with_counts = "--counts" in argv
    url = None
    out = Path("docs/estock-schema-dump.md")
    if "--url" in argv:
        url = argv[argv.index("--url") + 1]
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])

    engine = create_engine(_resolve_url(url), echo=False)
    dump = dump_schema(engine, with_counts=with_counts)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(dump), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {out} — {dump['total_tables']} tables, "
        f"{dump['covered_count']} mirrored, {dump['uncovered_count']} not yet mirrored."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
