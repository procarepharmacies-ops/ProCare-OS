# Deploy ProCare on the Elsanta SQL Server 2008 instance

This is the production topology the owner is standing up: the eStock database
lives on the **Elsanta branch server's SQL Server 2008** instance, and ProCare
hosts its **own** database on that *same* instance. No SQLite in production. The
first sync is seeded from a recent `.bak` backup (fast — no WAN hop), then
continuous sync keeps it fresh.

ProCare already speaks SQL Server 2008 (TOP-not-OFFSET pagination, no
TRIM/LENGTH, dialect-aware column adds). The switch is **config only** — until
`config/connections.json` carries real credentials the app falls back to the
local SQLite file, so nothing breaks while you prepare.

> ⚠️ **SQL Server 2008 is end-of-life (unpatched).** Keep this instance
> **LAN-only** — never expose port 1433 to the internet. Cross-branch sync stays
> *outbound* from ProCare.

---

## 0. Check the edition first (once)

In SSMS on the Elsanta instance:

```sql
SELECT SERVERPROPERTY('Edition') AS edition,
       SERVERPROPERTY('ProductVersion') AS version;
```

- **Express** → 10 GB **per-database** cap. ProCare's DB counts separately from
  eStock's, so you have a fresh 10 GB. ProCare's built-in disk/DB monitor
  (`GET /api/automation/db-health`, `DB_SIZE_CAP_MB=10240`) alerts at 80/90/95 %.
- **Standard / Enterprise** → no practical cap.

---

## 1. Create ProCare's database + logins (once)

ProCare needs **two** logins on the instance:
- a **read-write** login for its own `ProCare` database, and
- a **read-only** login for the eStock `stock` database (ProCare never writes to
  eStock — the sync preflight refuses to run otherwise).

```sql
-- ProCare's own database (separate from eStock — never inside the eStock DB)
CREATE DATABASE ProCare;
GO
CREATE LOGIN procare_app WITH PASSWORD = 'REPLACE_WITH_STRONG_PASSWORD';
GO
USE ProCare;
CREATE USER procare_app FOR LOGIN procare_app;
ALTER ROLE db_owner ADD MEMBER procare_app;   -- SQL 2008: sp_addrolemember 'db_owner','procare_app'
GO

-- Read-only login into the live eStock database (name it as it is on the server)
CREATE LOGIN procare_reader WITH PASSWORD = 'REPLACE_WITH_STRONG_PASSWORD';
GO
USE stock;                                    -- <-- the live eStock DB name
CREATE USER procare_reader FOR LOGIN procare_reader;
ALTER ROLE db_datareader ADD MEMBER procare_reader;   -- SQL 2008: sp_addrolemember 'db_datareader','procare_reader'
GO
```

On SQL Server 2008 `ALTER ROLE` may be unavailable — use the classic form:
`EXEC sp_addrolemember 'db_owner', 'procare_app';`

Make sure the instance has **TCP/IP enabled on 1433** and **mixed
authentication** on (see `SQL-SERVER-EXPRESS.md` §2 — identical steps), and that
the ProCare host has the **ODBC Driver 18 for SQL Server** installed (the client
driver is independent of the 2008 server version; Driver 18 defaults to
`Encrypt=yes`, and the config sets `TrustServerCertificate=yes`, which is what a
2008 instance with a self-signed cert needs).

### 1.1 Allow the TLS 1.0 handshake (non-Docker hosts only)

Driver 18 links **OpenSSL 3**, which refuses TLS 1.0/1.1 — the only protocols a
2008 instance negotiates. The handshake fails before authentication with:

```
SSL routines::unsupported protocol
```

`TrustServerCertificate=yes` does **not** help: this is a protocol-version
rejection, not a certificate one. Both connections terminate on the 2008 box
(eStock *and* ProCare's own co-hosted DB), so a host without this fix cannot
reach either — ProCare falls back to SQLite, and with `REQUIRE_SQLSERVER=1` the
watchdog reads that fallback as unhealthy and restarts the stack on a loop.

**Docker:** already handled — `deploy/Dockerfile.backend` patches the image's
`openssl.cnf`. Nothing to do.

**Linux (running `python run.py` directly):** apply the same patch to the host:

```bash
sudo sed -i '/^\[openssl_init\]/a ssl_conf = ssl_sect' /etc/ssl/openssl.cnf
sudo tee -a /etc/ssl/openssl.cnf >/dev/null <<'EOF'

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1
CipherString = DEFAULT@SECLEVEL=0
EOF
```

**Windows:** the OpenSSL patch does not apply — Driver 18 uses SChannel, so TLS
1.0 is an OS-level setting. Windows 10/11 up to 23H2 still enable the TLS 1.0
*client* by default and connect without changes; Windows 11 24H2 and Server 2025
disable TLS 1.0/1.1, and there the client must be re-enabled under
`HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.0\Client`
(`Enabled=1`, `DisabledByDefault=0`), followed by a reboot.

> Re-enabling TLS 1.0 weakens the host's TLS posture machine-wide. It is
> required only because the 2008 server cannot negotiate anything newer, and is
> one more reason to keep this instance off any untrusted network (see the
> end-of-life warning above).

---

## 2. Point ProCare at both databases

Edit `config/connections.json` (git-ignored). Fill **`procare_database`** (own
DB, read-write) and the **eStock source** (read-only):

```jsonc
{
  "estock_source": {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "localhost",          // same box → localhost (or the LAN IP)
    "port": 1433,
    "database": "stock",            // the live eStock DB
    "username": "procare_reader",
    "password": "…",
    "encrypt": "yes",
    "trust_server_certificate": "yes",
    "store_branch_map": { "1": "ELSANTA", "2": "MASHALA" }
  },
  "procare_database": {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "localhost",
    "port": 1433,
    "database": "ProCare",
    "username": "procare_app",
    "password": "…",
    "encrypt": "yes",
    "trust_server_certificate": "yes"
  }
}
```

On first boot ProCare's `create_all` + `ensure_*` migrations build the schema
(all 2008-compatible). `GET /api/health` should then report
`"procare_db": "sqlserver"`. If it still says `sqlite`, the block still has a
placeholder or the login failed — check `.local-run/backend.log`.

---

## 3. Seed the first sync from a recent backup (fast, no WAN)

Because ProCare shares the instance, seeding from a `.bak` is local disk I/O, not
a WAN pull. Proven procedure (see `docs/10-historical-backups-mashala-elsanta.md`
for the detailed version):

1. **Restore the latest backup beside the live DB** under a distinct name so the
   live eStock DB is never touched:

   ```sql
   RESTORE FILELISTONLY FROM DISK = 'F:\backup\stock_YYYYMMDD.bak';   -- note logical names
   RESTORE DATABASE stock_seed
     FROM DISK = 'F:\backup\stock_YYYYMMDD.bak'
     WITH MOVE 'stock'     TO 'F:\SQLDATA\stock_seed.mdf',
          MOVE 'stock_log' TO 'F:\SQLDATA\stock_seed.ldf',
          RECOVERY;
   GO
   ALTER DATABASE stock_seed SET READ_ONLY;   -- optional, belt-and-suspenders
   ```

2. **Grant the reader** into `stock_seed` (same `db_datareader` grant as §1) and
   temporarily point `estock_source.database` at `stock_seed`.

3. **Preflight + full mirror.** Start the backend, then:
   - `GET /api/sync/preflight` → confirms the read-only login works and lists
     `store_ids_found` (map each via `store_branch_map`).
   - `POST /api/etl/run` (one DB holding all branches → auto-creates a ProCare
     branch per store_id), **or** for branches split across separate `.bak`s use
     the branch importer:
     ```bat
     python -m app.services.etl --import stock_seed ELSANTA --fresh
     python -m app.services.etl --import stock_mashala MASHALA
     ```
     (`--fresh` wipes + full-loads the first source; the second appends with
     dedup by product code / customer mobile / vendor name.)

4. **Verify** the reconciliation (counts match the source) and that
   `full_synced_at` is recorded on the sync-state row.

5. **Repoint** `estock_source.database` back to the **live** `stock` DB, drop
   `stock_seed` when satisfied.

---

## 4. Turn on continuous sync

Once a full load is recorded, flip continuous sync on (`.env` at repo root):

```
SYNC_ENABLED=1
SYNC_INTERVAL_SECONDS=30
SYNC_INCREMENTAL_DAYS=7      # only the trailing 7 days of sales/purchases re-cross
```

Current-state tables (catalogue, customers, vendors, employees, stock, treasury)
refresh fully each cycle; sales/purchase **history** never re-crosses after the
first full load — so cycles are cheap even sharing the instance with live POS.

---

## 5. Keep it alive (watchdog)

Run the watchdog so a crash or a silent SQLite fallback self-heals:

```bat
set REQUIRE_SQLSERVER=1
deploy\procare-watchdog.bat
```

With `REQUIRE_SQLSERVER=1`, a `/api/health` that returns 200 but reports
`procare_db` ≠ `sqlserver` counts as a failure — so if the SQL Server login ever
breaks and ProCare silently falls back to SQLite, the watchdog restarts the
stack instead of quietly running on the wrong database. `deploy\procare-watchdog.bat --once`
exits 0 (healthy) / 1 (unhealthy) for Task Scheduler.

---

## Troubleshooting

### Error 9002 — "The transaction log for database 'ProCare' is full"

A database created from the default `model` inherits the **FULL** recovery model,
where the log is only truncated by a *log backup*. Nobody takes log backups of
ProCare, so the log grows until it hits the disk or its MAXSIZE — and the first
full mirror (121K `Branches_Product_Amount` rows, 70K `Branch_order_*` rows, plus
sales/purchase history) is what surfaces it.

ProCare's DB is a **mirror**: its recovery path is "re-run the mirror from
eStock", not "replay the log to a point in time". **SIMPLE** recovery is the
correct steady-state setting.

```sql
-- Diagnose (log_reuse_wait_desc tells you why the log can't be reused)
SELECT name, recovery_model_desc, log_reuse_wait_desc
FROM sys.databases WHERE name = 'ProCare';

-- Fix (LOG_BACKUP case — the common one)
ALTER DATABASE ProCare SET RECOVERY SIMPLE;
GO
USE ProCare;
CHECKPOINT;
DBCC SHRINKFILE (ProCare_log, 512);
GO
```

Run [`sql/fix-transaction-log-full.sql`](../sql/fix-transaction-log-full.sql) for
the full runbook — it covers the `ACTIVE_TRANSACTION` (crashed ETL run) and
disk-full cases too, sets a bounded 8 GB log ceiling, and verifies eStock was
untouched.

> ⚠️ Apply this to **ProCare only**. Never change the recovery model of the
> eStock `stock` database — that is the pharmacy's own recovery path.

If SSMS raised this while opening **Database Diagrams** (`sp_upgraddiagrams` in
the stack trace), that statement is incidental — it just happened to be the write
that hit the full log. ProCare doesn't use diagrams; skip that SSMS feature.

---

## Pre-flight checklist

- [ ] `SERVERPROPERTY('Edition')` checked (Express ⇒ mind the 10 GB cap)
- [ ] `ProCare` recovery model is **SIMPLE** (not FULL — see Troubleshooting)
- [ ] `ProCare` DB + `procare_app` (read-write) created
- [ ] `procare_reader` (read-only, `db_datareader`) into the eStock DB
- [ ] TCP 1433 + mixed auth enabled; ODBC Driver 18 installed
- [ ] `connections.json` filled; `/api/health` shows `"procare_db": "sqlserver"`
- [ ] `/api/sync/preflight` OK; full mirror from the restored `.bak` done
- [ ] `full_synced_at` recorded; `SYNC_ENABLED=1` with incremental window
- [ ] Watchdog running with `REQUIRE_SQLSERVER=1`
- [ ] Instance is LAN-only (1433 not internet-exposed)
