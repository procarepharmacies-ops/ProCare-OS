# ProCare-OS — Cross-Machine Setup (3 computers)

Goal: run **Hermes Agent** on 3 machines (this PC + elsanta + mashala), all
pointing at the same repo + OpenRouter, and mirror both eStock branches.

---

## 1) Clone the repo (all 3 machines)

```bash
git clone https://github.com/procarepharmacies-ops/ProCare-OS.git
cd ProCare-OS
git checkout fix/sqlserver-compat-and-operations-center
```

Branch `fix/sqlserver-compat-and-operations-center` already contains:
- Decimal/WAL/gitignore fixes
- WAN-resilient chunked eStock mirror (`app/services/etl.py`)
- KPI + two-real-branches (Elsanta + Mashala) fixes
- OpenRouter AI fallback (`app/services/llm.py`)
- docs/CLAUDE_CODE_*.md

To get later updates on any machine: `git pull`.

---

## 2) Hermes on all 3 machines (same config)

### Path of the Hermes secrets file
```
%USERPROFILE%\.hermes\.env
```
(e.g. `C:\Users\server_m\.hermes\.env` on mashala, `C:\Users\ahmed\.hermes\.env` here)

### `.env` content (identical on all 3)
```
OPENROUTER_API_KEY=sk-or-v1-...
```

### Provider + model (run once per machine)
```bash
hermes config set model.provider openrouter
hermes config set model.default openai/gpt-oss-20b:free
hermes status
```

### Fastest path
Use the helper `.bat` files (run as **Administrator** after editing the KEY line):
- `setup-hermes-elsanta.bat`
- `setup-hermes-mashala.bat`

> If the installer failed earlier at the `venv` stage with
> "process could not be terminated / Access is denied", it means a Hermes
> process was already running without admin rights. Kill it
> (`taskkill /F /IM hermes.exe /T`) and re-run the installer as Administrator.

---

## 3) eStock mirror on each branch machine

The eStock SQL Server is **local** on elsanta. Point the elsanta source at
`localhost` so the mirror is instant (no WAN drop, no corruption).

### `config/connections.json` per machine
- **elsanta:** `"server": "localhost,1433"` (or `196.202.93.37,1433` over WAN)
- **mashala:** `"server": "192.168.1.2,1433"`
- both use DB name `stock`, and the creds already in the file.

> `config/connections.json` is git-ignored — it holds plaintext prod creds.
> Rotate them. Do NOT commit it.

### Backend `.env` (src/backend/.env) — identical on all 3
```
AI_PROVIDER=ollama
AI_BASE_URL=https://openrouter.ai/api
AI_MODEL=openai/gpt-oss-20b:free
AI_MODEL_FALLBACKS=nvidia/nemotron-nano-9b-v2:free,nousresearch/hermes-3-llama-3.1-405b:free,meta-llama/llama-3.3-70b-instruct:free
OLLAMA_API_KEY=sk-or-v1-...        # same OpenRouter key
SYNC_ENABLED=1
SYNC_INTERVAL_SECONDS=30
```

### Run the mirror (elsanta — local, instant)
```bash
cd src/backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
set PROCARE_DB_URL=sqlite:///./data/procare.db
del data\procare.db
PYTHONPATH=. python -c "from app.services import sync; print(sync.run_once())"
```

On mashala the same commands work; the WAN/branch pull goes to `192.168.1.2`.

---

## 4) Security notes
- The OpenRouter key was pasted in chat multiple times — **rotate it** in the
  OpenRouter dashboard once setup is verified, then update all 3 `.env` files.
- `config/connections.json` has plaintext eStock creds — rotate + keep git-ignored.
- `.env` files are git-ignored and must NOT be committed.

---

## 5) Verify
- `hermes status` → OpenRouter configured / ok on all 3 machines.
- Backend `GET /api/health` → `ok`.
- `git log --oneline -1` on each machine → same latest commit after `git pull`.
