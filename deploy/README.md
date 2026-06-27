# Deploying ProCare OS — see it live

The whole stack (FastAPI backend + Next.js Arabic/RTL frontend) runs from **one
command**. It boots on ProCare's own seeded SQLite database, so it's live
immediately — no SQL Server, no eStock/Titan connection, no extra services.

The browser only ever talks to the frontend; Next.js proxies `/api/*` to the
backend **server-side**, so there's no CORS to configure and you never need to
know the host's IP for the app to work.

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
API:  http://<foo-ip>:8000/docs
```

`<foo-ip>` is shown by the script (also `multipass info foo`). Re-run the script
any time to redeploy.

## Option B — Docker on any machine

```bash
docker compose up -d --build
# UI  http://localhost:3000   ·   API http://localhost:8000/docs
```

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
| **Live eStock mirror / real ProCare SQL Server** | Copy `config/connections.example.json` → `config/connections.json` (git-ignored) and fill the read-only eStock login + ProCare DB, then `python -m app.services.etl --check` and `--run`. Uncomment `pyodbc` in `src/backend/requirements.txt`. |
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
