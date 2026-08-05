# Elsanta pilot — go-live readiness checklist

Print this. Each section is signed off before the pilot starts.

**Date:** ________  **Go-live target:** Monday ________ 08:00

> This supersedes the Phase-2 pilot package (PR #48), which was written for a
> separate **ProCare Dev box at 192.168.1.10** serving **Elsanta + Mashala**
> terminals over the LAN. That topology was dropped. ProCare now runs **on the
> Elsanta branch server itself**, co-hosted on its SQL Server 2008 instance,
> with **Elsanta as the only branch**. Anything still referring to 192.168.1.10,
> a Mashala source, or a mobile app is out of date.

---

## Section 1 — Database (sign-off: DBA / owner)

- [ ] `SERVERPROPERTY('Edition')` recorded: ____________ (Express ⇒ 10 GB per-DB cap)
- [ ] `ProCare` database created on the **Elsanta** instance, separate from eStock `stock`
- [ ] `ProCare` recovery model is **SIMPLE** — see [`sql/fix-transaction-log-full.sql`](../sql/fix-transaction-log-full.sql)
- [ ] `stock` (eStock) recovery model **unchanged** — it is the pharmacy's own recovery path
- [ ] Login `procare_app` — `db_owner` on `ProCare` only
- [ ] Login `procare_reader` — `db_datareader` on `stock` only, **never** on `ProCare`
- [ ] `GET /api/sync/preflight` reports `"read_only": true`
- [ ] Mixed authentication enabled; TCP 1433 enabled
- [ ] ODBC driver confirmed present (`Get-OdbcDriver`) and matching `connections.json`:
      ____________________ (on 2008 boxes this is usually `SQL Server Native Client 10.0`)

**Signed:** _________________ Date: _______

---

## Section 2 — Seeding (sign-off: DBA / owner)

- [ ] Pre-seed backup of `ProCare` taken **and verified** with `RESTORE VERIFYONLY`
      (no `WITH COMPRESSION` — Enterprise-only on SQL 2008 RTM)
- [ ] Backup path recorded: ____________________________
- [ ] eStock `.bak` restored beside the live DB under its own name (e.g. `stock_seed`)
- [ ] `deploy\Seed-Elsanta.bat` run to completion
- [ ] `store_ids_found` recorded: ____________
      (store 1 = pharmacy, store 2 = expired-items depot; **both** fold into `ELSANTA`)
- [ ] Row counts spot-checked against the source
- [ ] `estock_source.database` repointed from `stock_seed` back to the live `stock`
- [ ] `stock_seed` dropped once the dashboard shows real numbers

**Signed:** _________________ Date: _______

---

## Section 3 — Application (sign-off: dev)

- [ ] `python run.py` starts cleanly
- [ ] `GET /api/health` returns `{"status":"ok"}` **and** `"procare_db": "sqlserver"`
      (`sqlite` here means the SQL login failed and it fell back — do not go live)
- [ ] `GET /api/sync/status` shows `"running": true` with a recent timestamp
- [ ] `GET /api/automation/db-health` severity is `ok`
- [ ] `pytest app/tests/` run and result recorded: ______ passed / ______ failed
- [ ] Dashboard responds in < 500 ms
- [ ] Arabic RTL layout checked on the till screen

**Signed:** _________________ Date: _______

---

## Section 4 — Continuous sync (sign-off: dev)

- [ ] `.env` carries `SYNC_ENABLED=1`, `SYNC_INTERVAL_SECONDS=30`, `SYNC_INCREMENTAL_DAYS=7`
- [ ] A full load is recorded (`full_synced_at` present on the sync-state row)
- [ ] A sync failure is confirmed **not** to block a sale (pull the network, ring one up)
- [ ] Watchdog running with `REQUIRE_SQLSERVER=1` (`deploy\procare-watchdog.bat`)

**Signed:** _________________ Date: _______

---

## Section 5 — Security (sign-off: owner)

Mandatory before **any** remote access. `python -m app.services.exposure --check`
must exit `safe_to_expose: true`; the tunnel installer refuses otherwise.

- [ ] `AUTH_SECRET` set to a long random value in `.env` — **not** the dev default.
      It HMAC-signs session tokens, so until it is changed anyone who reads this
      public repo can forge a CEO session **with no password**.
- [ ] `AUTH_ENABLED=true`
- [ ] Every seeded account moved off the demo password
      (`python -m app.services.exposure --set-password <user> <password>`)
- [ ] `--check` re-run after restarting ProCare, and passes
- [ ] SQL Server **1433 is not** exposed to the internet or added to the tunnel
      (this instance is SQL Server 2008 — end-of-life and unpatched)
- [ ] Cloudflare tunnel points at `HTTP://localhost:3000` (the UI), nothing else

**Signed:** _________________ Date: _______

---

## Section 6 — Operations (sign-off: pharmacy manager)

- [ ] Cashiers trained on the till screen; a named fallback if ProCare is down
- [ ] **eStock remains the system of record for the whole pilot.** ProCare runs in
      parallel; it does not replace anything yet.
- [ ] Daily reconciliation owner named: ____________________
- [ ] Manager WhatsApp number set for alerts, or alerts explicitly disabled
- [ ] [`INCIDENTS.md`](../INCIDENTS.md) in use from day one

**Signed:** _________________ Date: _______

---

## Daily during the pilot

| Check | Where | Pass |
|---|---|---|
| Backend alive | `GET /api/health` → `procare_db: sqlserver` | |
| Sync fresh | `GET /api/sync/status` → recent timestamp | |
| DB headroom | `GET /api/automation/db-health` → `ok` | |
| Sales match eStock | day's total, ProCare vs eStock | ±0.1 % |
| Incidents logged | `INCIDENTS.md` | |

Any mismatch over 0.1 % is an incident — log it before it is explained away.

---

## Go / no-go

**Go** only when all six sections are signed and the security check passes.

**Stop the pilot** on: any data loss, sales diverging from eStock beyond 0.1 %
for two days running, or ProCare writing to eStock (it must only ever read).

**Approved:**

- Owner / CEO: _________________ Date: _______
- Pharmacy manager: _________________ Date: _______
- Dev: _________________ Date: _______
