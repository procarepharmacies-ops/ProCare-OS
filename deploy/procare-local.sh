#!/usr/bin/env bash
# ProCare AI — LOCAL launcher (no Docker).
#
# Runs the whole system natively on this machine: FastAPI backend (SQLite
# database in src/backend) + Next.js frontend, then opens the browser.
# First run installs dependencies and builds the frontend automatically.
#
#   ./deploy/procare-local.sh            start everything + open browser
#   ./deploy/procare-local.sh start      same, without opening the browser
#   ./deploy/procare-local.sh stop       stop backend + frontend
#   ./deploy/procare-local.sh status     is it running?
#   ./deploy/procare-local.sh logs       tail both logs
#
# Requirements: python3 (3.11+) and node (18+) on PATH. No Docker needed.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
RUN="$ROOT/.local-run"
mkdir -p "$RUN"

BACKEND_PORT="${PROCARE_API_PORT:-8000}"
FRONTEND_PORT="${PROCARE_UI_PORT:-3000}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing '$1' — install it first."; exit 1; }; }

is_up() { curl -fsS -o /dev/null "$1" 2>/dev/null; }

setup() {
  need python3; need node; need npm
  if [ ! -f "$RUN/.pip-done" ]; then
    echo "[setup] installing backend dependencies..."
    python3 -m pip install -q -r src/backend/requirements.txt && touch "$RUN/.pip-done"
  fi
  if [ ! -d src/frontend/node_modules ]; then
    echo "[setup] installing frontend dependencies..."
    (cd src/frontend && npm install --no-audit --no-fund)
  fi
  if [ ! -d src/frontend/.next ] || [ ! -f "$RUN/.built" ]; then
    echo "[setup] building the frontend (one time)..."
    # Same-origin API: the browser talks only to the frontend, which proxies
    # /api to the local backend server-side (no CORS, works offline on LAN).
    # BOTH vars must be set at BUILD time — Next bakes rewrites into the
    # production build manifest; setting them only at start does nothing.
    (cd src/frontend && NEXT_PUBLIC_API_BASE="" \
      BACKEND_INTERNAL="http://127.0.0.1:$BACKEND_PORT" npm run build) && touch "$RUN/.built"
  fi
}

start() {
  setup
  if ! is_up "http://127.0.0.1:$BACKEND_PORT/api/health"; then
    echo "[start] backend on :$BACKEND_PORT"
    (cd src/backend && PROCARE_API_PORT="$BACKEND_PORT" nohup python3 run.py \
      > "$RUN/backend.log" 2>&1 & echo $! > "$RUN/backend.pid")
  else
    echo "[start] backend already running"
  fi
  if ! is_up "http://127.0.0.1:$FRONTEND_PORT"; then
    echo "[start] frontend on :$FRONTEND_PORT"
    (cd src/frontend && BACKEND_INTERNAL="http://127.0.0.1:$BACKEND_PORT" \
      nohup npx next start -p "$FRONTEND_PORT" \
      > "$RUN/frontend.log" 2>&1 & echo $! > "$RUN/frontend.pid")
  else
    echo "[start] frontend already running"
  fi
  for i in $(seq 1 30); do
    is_up "http://127.0.0.1:$FRONTEND_PORT" && break
    sleep 1
  done
  echo "[ready] ProCare AI -> http://localhost:$FRONTEND_PORT"
}

stop() {
  for name in backend frontend; do
    if [ -f "$RUN/$name.pid" ]; then
      kill "$(cat "$RUN/$name.pid")" 2>/dev/null || true
      rm -f "$RUN/$name.pid"
      echo "[stop] $name stopped"
    fi
  done
  # Belt and braces: kill anything still bound to our ports by this project.
  pkill -f "next start -p $FRONTEND_PORT" 2>/dev/null || true
}

status() {
  is_up "http://127.0.0.1:$BACKEND_PORT/api/health" && echo "backend:  UP (:$BACKEND_PORT)" || echo "backend:  down"
  is_up "http://127.0.0.1:$FRONTEND_PORT" && echo "frontend: UP (:$FRONTEND_PORT)" || echo "frontend: down"
}

case "${1:-open}" in
  open)   start; (xdg-open "http://localhost:$FRONTEND_PORT" 2>/dev/null || open "http://localhost:$FRONTEND_PORT" 2>/dev/null || true) ;;
  start)  start ;;
  stop)   stop ;;
  status) status ;;
  logs)   tail -n 50 -f "$RUN/backend.log" "$RUN/frontend.log" ;;
  *) echo "usage: $0 [open|start|stop|status|logs]"; exit 1 ;;
esac
