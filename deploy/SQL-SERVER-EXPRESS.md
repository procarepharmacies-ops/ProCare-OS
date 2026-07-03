# Move ProCare from SQLite to SQL Server Express (free)

SQL Server Express is Microsoft's **free** edition (10 GB per database — years of
pharmacy data). ProCare already speaks both engines; the switch is **config only,
no code changes**. Until `config/connections.json` carries real credentials the
app keeps using the local SQLite file, so nothing breaks while you prepare.

---

## 1. Install SQL Server Express (once, on the pharmacy PC)

1. Download **SQL Server 2022 Express**: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
2. Run the installer → choose **Basic** → accept defaults. Note the instance
   name it prints at the end (usually `SQLEXPRESS`).
3. Install **SQL Server Management Studio (SSMS)** too (link on the same page) —
   you'll use it twice below.
4. Install the **ODBC Driver 18 for SQL Server** (ProCare's client driver):
   https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

## 2. Enable TCP + mixed authentication (once)

Express ships with TCP off and Windows-auth only; ProCare needs both changed.

1. Open **SQL Server Configuration Manager** →
   *SQL Server Network Configuration* → *Protocols for SQLEXPRESS* →
   **TCP/IP → Enabled**. In TCP/IP properties → *IP Addresses* → *IPAll*:
   clear "TCP Dynamic Ports", set **TCP Port = 1433**.
2. Services → restart **SQL Server (SQLEXPRESS)**.
3. In SSMS connect to `localhost\SQLEXPRESS` (Windows auth) →
   right-click the server → *Properties* → *Security* →
   **SQL Server and Windows Authentication mode** → OK → restart the service again.

## 3. Create the database + login (once)

In SSMS, run (pick your own strong password):

```sql
CREATE DATABASE ProCare;
GO
CREATE LOGIN procare_app WITH PASSWORD = 'REPLACE_WITH_STRONG_PASSWORD';
GO
USE ProCare;
CREATE USER procare_app FOR LOGIN procare_app;
ALTER ROLE db_owner ADD MEMBER procare_app;
GO
```

## 4. Point ProCare at it (the only ProCare-side change)

Copy `config/connections.example.json` → `config/connections.json`
(**git-ignored — never commit it**) and fill the `procare_database` block:

```json
"procare_database": {
  "driver": "ODBC Driver 18 for SQL Server",
  "server": "localhost",
  "port": 1433,
  "database": "ProCare",
  "username": "procare_app",
  "password": "the password from step 3",
  "encrypt": "yes",
  "trust_server_certificate": "yes"
}
```

Restart ProCare (double-click the desktop icon). On first start against the
empty database it creates the full schema, seeds the branches and the real
staff roster, and runs all column migrations automatically. Check
`http://localhost:3000` → Settings, or `http://localhost:8000/api/health` —
it should report `"procare_db": "sqlserver"`.

## 5. Bring your data across

Pick ONE:

* **From live eStock (recommended)** — fill the `estock_source` block with the
  read-only login and run the mirror: *Settings → Sync* or
  `POST /api/etl/run`. Products, customers, vendors, sales history, batches
  all flow in. This is the normal Phase-1 path.
* **Fresh start** — do nothing; start selling and let data accumulate.
* **Keep the SQLite history** — the dev file lives at
  `src/backend/data/procare.db`; keep it as an archive. (A one-off
  SQLite→SQL Server copy script is possible — ask if you want it.)

## 6. Backups (do not skip)

In SSMS: right-click *ProCare* → *Tasks* → *Back Up…* — or schedule nightly:

```sql
BACKUP DATABASE ProCare TO DISK = 'C:\Backups\ProCare.bak' WITH INIT;
```

Windows Task Scheduler → nightly `sqlcmd -S localhost -Q "<the line above>"`,
and copy the `.bak` off the machine (external drive / Google Drive / GCS).

## Troubleshooting

| Symptom | Fix |
|---|---|
| health says `sqlite (dev)` | `connections.json` missing, still has `REPLACE_ME`, or a JSON typo |
| *Login failed for user* | Mixed auth not enabled (step 2.3) or wrong password |
| *TCP Provider: No connection* | TCP not enabled / port not 1433 / service not restarted (step 2) |
| *IM002 driver not found* | Install ODBC Driver 18 (step 1.4) |
