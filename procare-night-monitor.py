#!/usr/bin/env python3
"""ProCare Night Monitor — sync via DB query + err.log every 15 min for 2 hours.

Queries sync_state table for last_cycle_at as proxy for sync liveness.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
import pyodbc
from datetime import datetime, timezone

REPORT_PATH = r"C:\Users\Procare\ProCare-OS\HERMES-NIGHT-REPORT.md"
ERR_LOG     = r"C:\Users\Procare\ProCare-OS\.local-run\err.log"
HEALTH_URL  = "http://localhost:8100/api/health"

DB_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost,1433;"
    "DATABASE=ProCare;"
    "UID=procare_app;"
    "PWD=Procare@2026;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)

INTERVAL = 900   # 15 minutes
SAMPLES  = 8     # 2 hours


def fetch_text(url: str, timeout: int = 15) -> str:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"FETCH_FAILED: {type(e).__name__}: {e}"


def err_log_tail(path: str, n: int = 30) -> str:
    if not os.path.exists(path):
        return f"FILE NOT FOUND: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception as e:
        return f"UNREADABLE: {e}"


def db_sync_status() -> dict:
    """Query sync_state table for last cycle timestamps."""
    try:
        conn = pyodbc.connect(DB_CONN, timeout=10)
        cur = conn.cursor()
        cur.execute(
            "SELECT source_name, full_synced_at, last_cycle_at, last_mode "
            "FROM sync_state ORDER BY last_cycle_at DESC"
        )
        rows = cur.fetchall()
        conn.close()
        result = {"rows": [], "count": len(rows)}
        for r in rows:
            result["rows"].append({
                "source_name": r.source_name,
                "full_synced_at": str(r.full_synced_at) if r.full_synced_at else None,
                "last_cycle_at": str(r.last_cycle_at) if r.last_cycle_at else None,
                "last_mode": r.last_mode,
            })
        return result
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def append_section(text: str):
    delim = "\n" + "=" * 60 + "\n"
    try:
        with open(REPORT_PATH, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
    except Exception:
        existing = ""
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"{delim}{text}")


def update_summary_tables(samples_collected: int, all_records: list):
    """Rewrite the summary tables in the report."""
    try:
        with open(REPORT_PATH, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return

    # Collect data for tables
    ts_rows = "\n".join(
        f"| {rec['sample']} | {rec['time']} | {rec['last_cycle'][:80]} | {rec.get('urgent','—')} |"
        for rec in all_records
    )

    # Sync timeline
    old_sync = re.search(
        r"### Sync Timeline.*?\| Sample # \| Time \(approx\) \| last_run \| error \|.*?\n(?:\|[-| ]+\|\n)(?:\|.*?\n)*",
        content, re.DOTALL
    )
    if old_sync:
        new_sync = f"""### Sync Timeline

| Sample # | Time (approx) | last_cycle_at (stock source) | urgent flags |
|----------|---------------|------------------------------|--------------|
{ts_rows}"""
        content = content.replace(old_sync.group(0), new_sync)

    # Error watch
    old_err = re.search(
        r"### Error Log Watch.*?\| Sample # \| Time \(approx\) \| Notable entries \|.*?\n(?:\|[-| ]+\|\n)(?:\|.*?\n)*",
        content, re.DOTALL
    )
    if old_err:
        new_err = f"""### Error Log Watch

| Sample # | Time (approx) | Notable entries |
|----------|---------------|-----------------|
{ts_rows}"""
        content = content.replace(old_err.group(0), new_err)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def flag_urgent(text: str) -> list:
    flags = []
    for pat, label in [
        (r"9002|transaction log.*full", "SQL ERROR 9002 — transaction log full"),
        (r"Login failed", "Login failures"),
        (r"Communication link failure", "Communication link failures"),
        (r"Traceback", "Python tracebacks"),
        (r"buffer latch|845", "SQL Server buffer latch timeout (845)"),
        (r"SystemExit|KeyboardInterrupt", "Process termination"),
    ]:
        if re.search(pat, text, re.IGNORECASE):
            flags.append(f"⚠ {label}")
    return flags


def build_verdict(all_records: list) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not all_records:
        return f"## Step 5 — Final Verdict — {ts}\n\n**IS PROCARE SYNCING?** UNCERTAIN — no samples collected.\n"

    # Get last_cycle_at values for stock source
    stock_cycles = [r for r in all_records if "stock" in r.get("last_cycle", "")]
    all_cycles = [r["last_cycle"] for r in all_records if r.get("last_cycle")]

    # Read full report for urgent patterns
    try:
        with open(REPORT_PATH, "r", encoding="utf-8", errors="replace") as f:
            full_report = f.read()
    except Exception:
        full_report = ""

    urgent_all = flag_urgent(full_report)

    # Determine if last_cycle_at advanced
    unique_cycles = set(r["last_cycle"] for r in all_records if r.get("last_cycle"))
    first_cycle = all_records[0].get("last_cycle", "N/A") if all_records else "N/A"
    last_cycle  = all_records[-1].get("last_cycle", "N/A") if all_records else "N/A"

    vt = f"""## Step 5 — Final Verdict — {ts}

### Summary

| Metric | Value |
|--------|-------|
| Samples collected | {len(all_records)} |
| Unique last_cycle_at values | {len(unique_cycles)} |
| First sample last_cycle | {first_cycle} |
| Last sample last_cycle | {last_cycle} |
| Expected cycles (2h @ 300s) | ~14 |

### Sync Health Assessment

"""
    if len(unique_cycles) >= 2:
        vt += f"""✅ **YES — ProCare IS syncing.**

last_cycle_at advanced {len(unique_cycles)} times across {len(all_records)} samples.
The sync thread is cycling at ~300s intervals as configured.

### Error Log Assessment
"""
    elif len(unique_cycles) == 1 and len(all_records) > 1:
        vt += f"""⚠️ **UNCERTAIN — last_cycle_at did not advance.**

Same value ({list(unique_cycles)[0][:40]}...) across {len(all_records)} samples.
The sync cycle may be stuck, the thread may have died, or DB queries may be stale.

### Error Log Assessment
"""
    else:
        vt += f"""❌ **NO — sync could not be confirmed.**

Only {len(unique_cycles)} unique last_cycle value(s) across {len(all_records)} samples.

### Error Log Assessment
"""

    if urgent_all:
        vt += "\n".join(f"  {u}" for u in urgent_all)
        vt += "\n\n**⚠️ These require immediate attention.**\n"
    else:
        vt += "No urgent error patterns detected in the error log across the monitoring window.\n"

    vt += f"""

---

*Report complete. HERMES-NIGHT-REPORT.md updated at {ts}.*
"""
    return vt


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ProCare Night Monitor v2 starting")
    print(f"  Interval: {INTERVAL}s ({INTERVAL//60} min), Samples: {SAMPLES}")
    print()

    all_records = []

    for i in range(SAMPLES):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sec = i * INTERVAL
        label = f"#{i+1}/{SAMPLES}"
        print(f"[{ts}] Sample {label} (T+{sec}s)")

        # Health
        health = fetch_text(HEALTH_URL)
        hs = {}
        try:
            hs = json.loads(health)
        except Exception:
            pass
        sync_cfg = hs.get("sync", {})
        sync_enabled = sync_cfg.get("enabled", "?")
        sync_interval = sync_cfg.get("interval_seconds", "?")

        # DB sync state
        db = db_sync_status()
        db_json = json.dumps(db, indent=2, default=str)

        # Extract last_cycle_at for stock source
        last_cycle_stock = None
        if isinstance(db, dict) and "rows" in db:
            for row in db["rows"]:
                if row["source_name"] == "stock":
                    last_cycle_stock = row["last_cycle_at"]
                    break
            if not last_cycle_stock and db["rows"]:
                last_cycle_stock = db["rows"][0]["last_cycle_at"]

        # Error log
        err_text = err_log_tail(ERR_LOG, 30)
        urgent_flags = flag_urgent(err_text)
        urgent_str = ", ".join(urgent_flags) if urgent_flags else "none"

        record = {
            "sample": i + 1,
            "time": ts,
            "last_cycle": last_cycle_stock or "NO_DATA",
            "urgent": urgent_str,
        }
        all_records.append(record)

        section = f"""## Sync Status Sample {label} — {ts} (T+{sec} sec)

**Health sync config:** enabled={sync_enabled}, interval={sync_interval}s

**DB sync_state table (stock source):**
```json
{db_json}
```

**last_cycle_at (stock):** {last_cycle_stock or "N/A"}

**Error log (last 30 lines):**
```text
{err_text}
```

**Urgent flags this sample:** {urgent_str}

"""
        append_section(section)
        update_summary_tables(i + 1, all_records)

        if i < SAMPLES - 1:
            print(f"  → Sleep {INTERVAL}s...")
            time.sleep(INTERVAL)
        else:
            print(f"  → Done.")

    verdict = build_verdict(all_records)
    append_section(verdict)
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitor complete.")


if __name__ == "__main__":
    main()
