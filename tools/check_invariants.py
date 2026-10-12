#!/usr/bin/env python3
"""Enforce the CLAUDE.md invariants a test suite cannot catch.

Run by CI and safe to run locally:  python tools/check_invariants.py

Two classes of check, both chosen because they fail SILENTLY in production
rather than loudly in a test:

  * Credential files that must never be committed. config/connections.json and
    .env carry the live eStock logins and AUTH_SECRET; once pushed, redacting
    the file does not remove them from history.
  * SQL Server 2008 constructs. Production runs on 2008 (CLAUDE.md), but the
    test suite runs on SQLite, which happily accepts OFFSET/FETCH, LAG and
    friends. A violation therefore passes every test and only fails on the
    pharmacy's server.

Comment-aware on purpose: CLAUDE.md's rules are quoted verbatim in comments
and docstrings throughout the codebase (e.g. "NB: no func.trim/length"), so a
plain grep flags the documentation rather than the code.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files whose presence in git history leaks production credentials.
NEVER_TRACKED = ("config/connections.json", ".env")

# 2008 does not implement these. SQLite does, so tests stay green regardless.
PY_BANNED = [
    (r"\.offset\s*\(", ".offset() emits OFFSET/FETCH (2012+); use .limit()/keyset"),
    (r"func\.trim\s*\(", "func.trim is absent on SQL Server 2008"),
    (r"func\.length\s*\(", "func.length is absent on SQL Server 2008"),
    (r"\.nulls_last\s*\(", "NULLS LAST is not valid on 2008; use fefo_order()"),
]
SQL_BANNED = [
    (r"\bDATEFROMPARTS\s*\(", "DATEFROMPARTS is 2012+"),
    (r"\bSTRING_AGG\s*\(", "STRING_AGG is 2012+"),
    (r"\bIIF\s*\(", "IIF is 2012+"),
    (r"\bLAG\s*\(", "LAG is 2012+"),
    (r"\bLEAD\s*\(", "LEAD is 2012+"),
]


def _strip_py(line: str) -> str:
    """Drop a trailing # comment, ignoring #s inside string literals."""
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and line[i - 1 : i] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _strip_sql(line: str) -> str:
    return line.split("--", 1)[0]


def _sql_block_mask(lines: list[str]) -> list[bool]:
    """True for lines inside a /* ... */ block. The header comment of every
    sql/ script quotes the banned constructs by name, so without this the
    documentation trips its own rule."""
    inside, mask = False, []
    for raw in lines:
        starts = raw.count("/*")
        ends = raw.count("*/")
        mask.append(inside or (starts > 0 and ends == 0) or (inside and ends > 0))
        if starts > ends:
            inside = True
        elif ends > starts:
            inside = False
    return mask


def _scan(paths, banned, strip) -> list[str]:
    problems = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        block = _sql_block_mask(lines) if strip is _strip_sql else [False] * len(lines)
        in_doc = False
        for n, raw in enumerate(lines, 1):
            if block[n - 1]:
                continue
            # Skip docstring bodies — the rules are quoted in them verbatim.
            fences = raw.count('"""') + raw.count("'''")
            if in_doc:
                if fences:
                    in_doc = False
                continue
            if fences % 2:
                in_doc = True
                continue
            code = strip(raw)
            for pattern, why in banned:
                if re.search(pattern, code):
                    problems.append(f"{path.relative_to(ROOT)}:{n}: {why}\n    {raw.strip()}")
    return problems


def main() -> int:
    failures: list[str] = []

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    for secret in NEVER_TRACKED:
        if secret in tracked:
            failures.append(
                f"{secret} is tracked by git. It holds live credentials — remove it "
                f"from the index AND rotate what it contained; redaction does not "
                f"undo a push."
            )

    app = ROOT / "src" / "backend" / "app"
    py = [p for p in app.rglob("*.py") if "/tests/" not in p.as_posix()]
    failures += _scan(py, PY_BANNED, _strip_py)
    failures += _scan(sorted((ROOT / "sql").glob("*.sql")), SQL_BANNED, _strip_sql)

    if failures:
        print("Invariant check FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nThese pass on SQLite and fail on the pharmacy's SQL Server 2008.",
            file=sys.stderr,
        )
        return 1

    print("Invariant check passed: no committed credentials, no 2012+ SQL constructs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
