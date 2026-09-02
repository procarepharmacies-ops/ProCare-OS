#!/usr/bin/env bash
# Materialise config/connections.json from environment variables, wait for SQL
# Server and ensure the target databases exist, then run the given command.
#
# This lets docker-compose inject SQL Server credentials without committing
# secrets. With no DB env set, nothing is written and the app falls back to the
# committed example config (SQLite) — so the image runs either way.
set -e

python - <<'PY'
import json, os, time

def block(prefix):
    server = os.environ.get(prefix + "_SERVER")
    if not server:
        return None
    b = {
        "server": server,
        "database": os.environ.get(prefix + "_DATABASE", ""),
        "username": os.environ.get(prefix + "_USER", ""),
        "password": os.environ.get(prefix + "_PASSWORD", ""),
        "encrypt": os.environ.get(prefix + "_ENCRYPT", "yes"),
        "trust_server_certificate": "yes",
    }
    port = os.environ.get(prefix + "_PORT")
    if port:
        b["port"] = port
    return b

data = {}
p = block("PROCARE_DB")
if p:
    data["procare_database"] = p

# Multi-source eStock (one per branch server): ESTOCK_DB_*, ESTOCK2_DB_*, ESTOCK3_DB_*, ...
# Fall back to a single ESTOCK_DB_* block for backward compatibility.
estock_sources = []
for i in range(1, 10):  # support up to 9 sources
    prefix = "ESTOCK_DB" if i == 1 else f"ESTOCK{i}_DB"
    e = block(prefix)
    if e:
        # Each source gets its own store_branch_map from env or defaults.
        sm_env = f"ESTOCK{i}_STORE_BRANCH_MAP" if i > 1 else "ESTOCK_STORE_BRANCH_MAP"
        sm = os.environ.get(sm_env)
        if sm:
            try:
                e["store_branch_map"] = json.loads(sm)
            except Exception:
                pass
        # Multi-source list: each source gets a readable name (database or "elsanta", etc).
        e["name"] = e.get("database", f"estock{i}").replace("stock", "").replace("_", "").lower() or f"estock{i}"
        estock_sources.append(e)

if estock_sources:
    if len(estock_sources) == 1:
        # Single source: keep legacy format for backward compat.
        data["estock_source"] = estock_sources[0]
    else:
        # Multi-source: use the list format.
        data["estock_sources"] = estock_sources

if data:
    os.makedirs("/app/config", exist_ok=True)
    with open("/app/config/connections.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print("entrypoint: wrote /app/config/connections.json for:", ", ".join(data))
else:
    print("entrypoint: no SQL Server env set — using example config (SQLite)")

# Wait for SQL Server and create each target database if missing (the server
# image starts with only `master`). Best-effort: skip if pyodbc isn't present.
def ensure_db(b):
    try:
        import pyodbc
    except Exception:
        return
    port = b.get("port", "1433")
    server = b["server"] if "," in b["server"] else f"{b['server']},{port}"
    # Local container connection: disable encryption (same network, no threat).
    # eStock (external server) uses the encrypt setting from config.
    encrypt = "no" if b["server"] == "sqlserver" else b.get("encrypt", "yes")
    master = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};DATABASE=master;"
        f"UID={b['username']};PWD={b['password']};Encrypt={encrypt};TrustServerCertificate=yes"
    )
    dbname = b["database"]
    for attempt in range(60):
        try:
            cn = pyodbc.connect(master, autocommit=True, timeout=5)
            cur = cn.cursor()
            cur.execute(f"IF DB_ID(N'{dbname}') IS NULL CREATE DATABASE [{dbname}]")
            cur.close(); cn.close()
            print(f"entrypoint: database '{dbname}' ready on {b['server']}")
            return
        except Exception as ex:  # noqa: BLE001
            if attempt == 0:
                print(f"entrypoint: waiting for SQL Server {b['server']} ... ({ex})")
            time.sleep(2)
    raise SystemExit(f"entrypoint: SQL Server {b['server']} not reachable; giving up")

# Always ensure ProCare's OWN database. NEVER create/write the eStock source —
# it's read-only by guardrail — unless explicitly asked (the local SQL Server
# demo sets ESTOCK_ENSURE_DB=1 for its throwaway eStock container).
targets = []
if data.get("procare_database"):
    targets.append(data["procare_database"])
if data.get("estock_source") and os.environ.get("ESTOCK_ENSURE_DB", "").lower() in ("1", "true", "yes", "on"):
    targets.append(data["estock_source"])
for b in targets:
    ensure_db(b)
PY

exec "$@"
