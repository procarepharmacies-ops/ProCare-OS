# ProCare OS — Backend (FastAPI)

Phase-0 skeleton. Starts with **no database connection required**, so the
frontend has a live API to talk to from day one. Wiring to the ProCare DB /
eStock ETL / AI follows [`../../docs/06-roadmap.md`](../../docs/06-roadmap.md).

## Run

```bash
# from this folder
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt       # macOS/Linux
.venv\Scripts\python run.py
```

API → http://127.0.0.1:8000  ·  interactive docs → http://127.0.0.1:8000/docs

Or use the editor **Run** (preview): see [`../../.claude/launch.json`](../../.claude/launch.json), server **`procare-backend`**.

## Endpoints (Phase 0)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | service info |
| GET | `/api/health` | status + which DBs are configured + UI defaults |
| GET | `/api/branches` | the two branches (Main / Elsanta) from config |
| GET | `/api/dashboard/summary` | stub KPIs (wired to DB in Phase 1) |

Config is read by [`app/config.py`](app/config.py) from `config/connections.json`
(git-ignored), falling back to `config/connections.example.json`. **Secrets are
never returned by the API** — `/api/health` only reports whether each source has
real (non-placeholder) credentials.
