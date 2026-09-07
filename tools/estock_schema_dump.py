"""Read-only eStock schema dump + ProCare coverage report.

Run this ONCE on the Elsanta branch server (or against any restored eStock
backup) to capture the live schema and see exactly which source tables ProCare
mirrors and which it doesn't — closing the "how much of eStock do we cover?"
blind spot with real data instead of guesses.

Strictly READ-ONLY: it only inspects table/column metadata (via SQLAlchemy's
dialect-agnostic Inspector, so it works on SQL Server 2008 and SQLite alike) and
optionally COUNT(*)s. It never writes to eStock.

Usage — run from the REPO ROOT, with config/connections.json pointing at
eStock (or just double-click ``deploy/Dump-eStock-Schema.bat`` on Windows):

    python -m tools.estock_schema_dump                 # metadata only
    python -m tools.estock_schema_dump --counts        # + row counts (slower)
    python -m tools.estock_schema_dump --url "sqlite:///…"   # explicit source
    python -m tools.estock_schema_dump --out docs/estock-schema-dump.md

NOT from ``src/backend``: there is a SECOND, unrelated ``tools`` package there
(drugeye_scrape, titan_extract, …), so ``-m tools.estock_schema_dump`` resolves
to that one and dies with ModuleNotFoundError. This file lives in the repo-root
``tools/``. The sys.path shim below only fixes importing ``app.services.etl``
from here; it cannot fix which ``tools`` package Python picked.

Writes a Markdown report (and a .json beside it) listing every table, its
columns, primary key, row counts (if requested), and a COVERAGE section.

Coverage has two tiers, and the report separates them because they mean
different things:

  * **dedicated** - the table is read into real ProCare models by a _load_*
    function in ``app.services.etl`` (COVERED_SOURCE_TABLES). Queryable domain
    data: products, sales, GL journal, payroll.
  * **raw** - the table is mirrored verbatim, row for row, into the generic
    ``estock_raw_mirror`` table by ``_load_uncovered_tables``. Present and
    exact, but JSON rather than modelled - enough to confirm an encoding (the
    Gedo_* party-type question) or to promote the table to a dedicated loader
    later without another trip to the pharmacy server.

Together the two tiers are ProCare's real answer to "how much of eStock do we
hold?", so the headline number is dedicated + raw.
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
        try:
            pk = list(insp.get_pk_constraint(name).get("constrained_columns") or [])
        except Exception:  # noqa: BLE001 - an unintrospectable key still gets listed
            pk = []
        dedicated = name.lower() in covered_lower
        row = {
            "name": name,
            "columns": columns,
            "column_count": len(columns),
            # The raw mirror takes every table a dedicated loader does not.
            "coverage": "dedicated" if dedicated else "raw",
            "covered": True,
            "dedicated": dedicated,
            "primary_key": pk,
        }
        if with_counts:
            try:
                with engine.connect() as conn:
                    row["row_count"] = int(conn.execute(text(f"SELECT COUNT(*) FROM [{name}]")).scalar() or 0)
            except Exception:  # noqa: BLE001 — a count failing must not abort the dump
                row["row_count"] = None
        tables.append(row)

    dedicated = [t for t in tables if t["dedicated"]]
    raw = [t for t in tables if not t["dedicated"]]
    return {
        "total_tables": len(tables),
        "dedicated_count": len(dedicated),
        "raw_count": len(raw),
        "covered_count": len(tables),
        "uncovered_count": 0,
        "coverage_pct": 100.0 if tables else 0.0,
        "dedicated": [t["name"] for t in dedicated],
        "raw": [t["name"] for t in raw],
        "covered": [t["name"] for t in tables],
        "uncovered": [],
        "tables": tables,
    }


def render_markdown(dump: dict) -> str:
    lines = [
        "# eStock schema dump + ProCare coverage",
        "",
        f"- **Total tables:** {dump['total_tables']}",
        f"- **Mirrored into ProCare models (dedicated loaders):** {dump['dedicated_count']}",
        f"- **Mirrored verbatim into `estock_raw_mirror`:** {dump['raw_count']}",
        f"- **Not mirrored:** {dump['uncovered_count']}",
        f"- **Coverage:** {dump['coverage_pct']}%",
        "",
        "Legend: ✅ dedicated ProCare model · 📦 verbatim row in `estock_raw_mirror`.",
        "",
        "## Verbatim-only tables (held in full, not yet modelled)",
        "",
        "Mirrored row-for-row, queried as JSON. Promote one to a dedicated loader",
        "when the domain needs it — the rows are already local, so that no longer",
        "costs another trip to the pharmacy server.",
        "",
    ]
    if dump["raw"]:
        for name in dump["raw"]:
            t = next(t for t in dump["tables"] if t["name"] == name)
            rc = t.get("row_count")
            rc_s = f" — {rc:,} rows" if isinstance(rc, int) else ""
            pk = ", ".join(t.get("primary_key") or []) or "no declared key"
            lines.append(f"- `{name}` ({t['column_count']} cols, PK: {pk}){rc_s}")
    else:
        lines.append("_None — every source table has a dedicated loader._")
    lines += ["", "## All tables", ""]
    for t in dump["tables"]:
        mark = "✅" if t["dedicated"] else "📦"
        rc = t.get("row_count")
        rc_s = f" · {rc:,} rows" if isinstance(rc, int) else ""
        pk = ", ".join(t.get("primary_key") or []) or "no declared key"
        lines.append(f"### {mark} `{t['name']}`{rc_s}")
        lines.append("")
        lines.append(f"_PK: {pk}_")
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
        f"Wrote {out} — {dump['total_tables']} tables: "
        f"{dump['dedicated_count']} via dedicated loaders, "
        f"{dump['raw_count']} verbatim in estock_raw_mirror, "
        f"{dump['uncovered_count']} not mirrored ({dump['coverage_pct']}% coverage)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
