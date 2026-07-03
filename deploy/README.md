# Deploying ProCare OS — see it live

The whole stack (FastAPI backend + Next.js Arabic/RTL frontend) runs from **one
command**. It boots on ProCare's own seeded SQLite database, so it's live
immediately — no SQL Server, no eStock/Titan connection, no extra services.

The browser only ever talks to the frontend; Next.js proxies `/api/*` to the
backend **server-side**, so there's no CORS to configure and you never need to
know the host's IP for the app to work.

**Windows pharmacy PC quick paths:**

| Script / guide | What it does |
|---|---|
| `ProCare-Autostart-Install.bat` | Desktop icon + start on **login** (simple) |
| `ProCare-Service-Install.bat` | Start on **Windows boot, before login** (Task Scheduler as SYSTEM) + optional **Cloudflare Tunnel as a Windows service** for a public https URL (phone access from anywhere) |
| `SQL-SERVER-EXPRESS.md` | Move ProCare's database from SQLite to free **SQL Server Express** — config-only, step by step |
| `../docs/08-google-cloud-300-plan.md` | Gemini API key setup + the plan for the $300 Google Cloud trial (off-site backups, free always-on VM, monitoring) |

---

## Option A — your Multipass VM "foo" (one command)

Run on the **host** that has multipass (not inside the VM):

```bash
./deploy/foo-up.sh           # or:  VM=foo ./deploy/foo-up.sh
```

It provisions `foo` if needed, installs Docker, copies this repo in, builds and
starts the stack, and prints the live URL. When it finishes:

```
UI:   http://<foo-ip>:3000
API:  http://<foo-ip>:8080/docs
```

`<foo-ip>` is shown by the script (also `multipass info foo`). Re-run the script
any time to redeploy.

## Option B — Docker on any machine

```bash
docker compose up -d --build
# UI  http://localhost:3000   ·   API http://localhost:8080/docs
```

## Option B2 — SQL Server + live sync (production engine)

Run ProCare on **SQL Server** (its production database) with a second SQL Server
playing the role of **eStock**, kept in sync **continuously** (near-real-time):

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.sqlserver.yml up -d --build
# UI http://localhost:3000 · API http://localhost:8080/docs · sync GET /api/sync/status
```

What it does:
1. `procare-db` + `estock-db` (SQL Server) start.
2. `estock-seed` fills `estock-db` with realistic eStock-shaped data (once).
3. `backend` creates its own SQL Server schema and mirrors eStock → ProCare every
   `SYNC_INTERVAL_SECONDS` (default 10s), applying the data-quality rules. Watch
   it at `GET /api/sync/status`.

### Sync the REAL eStock server

Use the dedicated overlay (no demo eStock containers — points at the live server):

```bash
cp deploy/estock.env.example deploy/estock.env     # git-ignored; fill host/user/password
docker compose --env-file deploy/estock.env \
  -f docker-compose.yml -f deploy/docker-compose.estock-live.yml up -d --build
# UI http://localhost:3000 · sync GET http://localhost:8080/api/sync/status
```

eStock is opened **read-only** (only SELECTs; ProCare never creates or writes
anything there — use a dedicated read-only login). The machine running this must
reach the eStock host (a LAN IP, or a **public static IP** for a remote server).
Default mapping is owner-confirmed `store_id 1 = Elsanta`; any store_id you don't
map (e.g. Mashal) is still synced into an auto-created `STORE<id>` branch.

**Check the connection first (recommended):**

```bash
docker compose --env-file deploy/estock.env \
  -f docker-compose.yml -f deploy/docker-compose.estock-live.yml \
  run --rm estock-preflight
```

It reports `connected`, `read_only` (a blocked write is the good outcome), and
`store_ids_found` so you can see/name each branch. A timeout means the server's
firewall is blocking this machine's IP (allowlist it) or the SQL port is closed.
The same check is available on the running backend at `GET /api/sync/preflight`.

## Option C — no Docker (dev)

```bash
cd src/backend && pip install -r requirements.txt && python run.py   # :8000
cd src/frontend && npm install && npm run dev                        # :3000
```

---

## Optional configuration

| What | How |
|------|-----|
| **Arabic assistant via Claude** | `export ANTHROPIC_API_KEY=sk-ant-...` before `docker compose up` (compose passes it through). Without it, the assistant uses the offline keyword router. |
| **SQL Server (compose)** | Use the Option B2 overlay. The backend reads `PROCARE_DB_*` / `ESTOCK_DB_*` env vars and writes `connections.json` at startup; no secrets in git. |
| **Continuous sync cadence** | `SYNC_INTERVAL_SECONDS` (default 10 in the overlay, 30 otherwise). `SYNC_ENABLED=1` + a configured eStock source turns it on. Status at `/api/sync/status`. |
| **Live eStock mirror / real ProCare SQL Server (no Docker)** | Copy `config/connections.example.json` → `config/connections.json` (git-ignored) and fill the read-only eStock login + ProCare DB, then `python -m app.services.etl --check` and `--run`. Uncomment `pyodbc` in `src/backend/requirements.txt`. |
| **Titan / Drug-Eye clinical source** | Fill `titan_drugeye_source` in `connections.json` once the `D:\Labirdo` schema is audited; the advisory layer flips from curated rules to the live source automatically. |
| **Call the API directly (not via the proxy)** | Set `PROCARE_CORS_ORIGINS` on the backend (comma-separated origins, or `*`). |

## Manage the stack

```bash
docker compose logs -f          # follow logs
docker compose ps               # status
docker compose down             # stop & remove
```

## How it fits together

```
browser ──http──> frontend :3000 ──(/api/* proxied server-side)──> backend :8000 ──> ProCare DB (SQLite)
```

- `docker-compose.yml` — the two services (repo root).
- `deploy/Dockerfile.backend` — Python 3.11 + FastAPI (uvicorn on 0.0.0.0:8000).
- `deploy/Dockerfile.frontend` — Node 22, `next build` with the `/api` proxy baked to `backend:8000`, `next start` on :3000.
- `deploy/foo-up.sh` — the Multipass one-shot above.

---

## Control Center (the simple way — production server)

One script drives everything on the pharmacy server:

```bash
./deploy/procare.sh            # interactive menu (start/stop/update/logs…)
./deploy/procare.sh start      # start ProCare
./deploy/procare.sh update     # pull the newest version and rebuild
```

**Desktop icon (Windows + WSL):** copy `deploy/ProCare.bat` to the Windows
Desktop. Double-click = server starts (if not already running) and the app
opens in the browser. On a plain Ubuntu desktop use `deploy/procare.desktop`
instead (edit the two paths inside).

**Access from anywhere on the internet (Cloudflare Tunnel):**
1. Cloudflare Zero Trust → Networks → Tunnels → create/open your tunnel and
   copy its **token**.
2. Add to `.env` next to this repo's `docker-compose.yml`:
   `TUNNEL_TOKEN=eyJ...`
3. In the tunnel's *Public Hostname* settings, point your hostname at
   `http://frontend:3000` (type: HTTP).
4. `./deploy/procare.sh start` — the tunnel container joins automatically.

Because the app is now reachable from the internet, keep `AUTH_ENABLED=true`
(the default) and set a strong `AUTH_SECRET` in `.env` — the login screen is
what stands between the internet and your pharmacy data.
