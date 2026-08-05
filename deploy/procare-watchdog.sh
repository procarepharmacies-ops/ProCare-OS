#!/usr/bin/env bash
# ProCare OS — health watchdog (auto-restart on failure).
#
# The pharmacy opens at 9am. If the backend dies overnight or freezes at 10am,
# the only recovery today is a human. This watchdog polls /api/health and, after
# N consecutive failures, restarts the stack via the tested procare.sh path — so
# a frozen screen self-heals instead of costing sales.
#
# Usage:
#   ./deploy/procare-watchdog.sh          run forever (poll every INTERVAL secs)
#   ./deploy/procare-watchdog.sh --once   one check; exit 0 healthy / 1 unhealthy
#
# Run it as a background service:
#   nohup ./deploy/procare-watchdog.sh >/dev/null 2>&1 &        # quick + dirty
#   (or a systemd unit / Windows Task Scheduler — see deploy/DEPLOYMENT.md)
#
# Configuration (all via environment, with sane defaults):
#   HEALTH_URL          health endpoint         (default http://localhost:7000/api/health)
#   INTERVAL            seconds between polls    (default 60)
#   FAIL_THRESHOLD      consecutive fails before restart (default 3)
#   REQUIRE_SQLSERVER   1 = a 200 that is NOT on sqlserver counts as a failure
#                       (catches a silent fallback to the dev SQLite DB) (default 1)
#   COOLDOWN            seconds to wait after a restart before polling (default 120)
#   RESTART_CMD         command run to recover  (default: deploy/procare.sh restart)
#   BACKEND_CONTAINER   container name for OOM check (default procare-backend)
#   LOG_FILE            where to append logs     (default <repo>/.local-run/watchdog.log)
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HEALTH_URL="${HEALTH_URL:-http://localhost:7000/api/health}"
INTERVAL="${INTERVAL:-60}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-3}"
REQUIRE_SQLSERVER="${REQUIRE_SQLSERVER:-1}"
COOLDOWN="${COOLDOWN:-120}"
RESTART_CMD="${RESTART_CMD:-$SCRIPT_DIR/procare.sh restart}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-procare-backend}"
LOG_FILE="${LOG_FILE:-$REPO_ROOT/.local-run/watchdog.log}"

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() {
  # Timestamped line to both stdout and the log file.
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

# Return 0 (healthy) / 1 (unhealthy). A failure is: curl error, non-2xx, or —
# when REQUIRE_SQLSERVER=1 — a 200 whose body is not on the sqlserver backend.
check_health() {
  local body
  if ! body="$(curl -sf -m 10 "$HEALTH_URL" 2>/dev/null)"; then
    return 1
  fi
  if [ "$REQUIRE_SQLSERVER" = "1" ]; then
    # The health payload reports "procare_db":"sqlserver" in production and
    # "sqlite (dev)" if it silently fell back — treat the fallback as a failure.
    case "$body" in
      *sqlserver*) : ;;
      *) return 1 ;;
    esac
  fi
  return 0
}

# Extra safety net: if Docker OOM-killed the backend, restart proactively.
oom_killed() {
  command -v docker >/dev/null 2>&1 || return 1
  local state
  state="$(docker inspect -f '{{.State.OOMKilled}}' "$BACKEND_CONTAINER" 2>/dev/null)" || return 1
  [ "$state" = "true" ]
}

do_restart() {
  log "RESTART: running: $RESTART_CMD"
  if ( cd "$REPO_ROOT" && eval "$RESTART_CMD" ) >>"$LOG_FILE" 2>&1; then
    log "RESTART: completed."
  else
    log "RESTART: command exited non-zero — check the stack manually."
  fi
}

run_once() {
  if check_health; then
    return 0
  fi
  return 1
}

# --- --once mode: single check for manual testing / cron / systemd oneshot ---
if [ "${1:-}" = "--once" ] || [ "${1:-}" = "once" ]; then
  if run_once; then
    log "OK (once): $HEALTH_URL healthy."
    exit 0
  fi
  log "FAIL (once): $HEALTH_URL unhealthy."
  exit 1
fi

# --- continuous mode ---------------------------------------------------------
trap 'log "watchdog stopping (signal received)."; exit 0' INT TERM

log "watchdog started — url=$HEALTH_URL interval=${INTERVAL}s threshold=$FAIL_THRESHOLD require_sqlserver=$REQUIRE_SQLSERVER"
fails=0
while true; do
  if oom_killed; then
    log "OOM: $BACKEND_CONTAINER was OOM-killed — restarting."
    do_restart
    fails=0
    sleep "$COOLDOWN"
    continue
  fi

  if check_health; then
    if [ "$fails" -ne 0 ]; then
      log "RECOVERED: health OK after $fails failure(s)."
    fi
    fails=0
  else
    fails=$((fails + 1))
    log "UNHEALTHY: $HEALTH_URL (consecutive failures: $fails/$FAIL_THRESHOLD)."
    if [ "$fails" -ge "$FAIL_THRESHOLD" ]; then
      do_restart
      fails=0
      sleep "$COOLDOWN"
      continue
    fi
  fi
  sleep "$INTERVAL"
done
