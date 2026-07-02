#!/usr/bin/env bash
# ProCare AI Control Center — one script to run everything.
#
#   ./deploy/procare.sh           interactive menu
#   ./deploy/procare.sh start     start (or create) all containers
#   ./deploy/procare.sh stop      stop everything
#   ./deploy/procare.sh restart   restart the running stack
#   ./deploy/procare.sh update    pull the latest version from GitHub + rebuild
#   ./deploy/procare.sh status    what is running
#   ./deploy/procare.sh logs [svc]  follow logs (backend / frontend / sqlserver / tunnel)
#   ./deploy/procare.sh health    ask the backend if it is alive
#
# Internet access: put your Cloudflare tunnel token in .env as
#   TUNNEL_TOKEN=eyJ...
# and the tunnel container is included automatically on the next start.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  exit 1
fi

COMPOSE=(docker compose)
# Include the Cloudflare tunnel service only when a token is configured.
if grep -qs '^TUNNEL_TOKEN=..*' .env 2>/dev/null; then
  COMPOSE+=(--profile tunnel)
fi

urls() {
  local ip
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  echo
  echo "  ProCare AI is available at:"
  echo "    This computer:   http://localhost:3000"
  [ -n "${ip:-}" ] && echo "    Pharmacy LAN:    http://${ip}:3000"
  if grep -qs '^TUNNEL_TOKEN=..*' .env 2>/dev/null; then
    echo "    Internet:        your Cloudflare tunnel hostname (Zero Trust dashboard)"
  fi
  echo
}

case "${1:-menu}" in
  start)
    "${COMPOSE[@]}" up -d
    urls
    ;;
  stop)
    "${COMPOSE[@]}" down
    ;;
  restart)
    "${COMPOSE[@]}" restart
    urls
    ;;
  update)
    git pull origin main
    "${COMPOSE[@]}" up -d --build
    urls
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  logs)
    if [ -n "${2:-}" ]; then
      "${COMPOSE[@]}" logs -f --tail=100 "$2"
    else
      "${COMPOSE[@]}" logs -f --tail=100
    fi
    ;;
  health)
    curl -sf http://localhost:7000/api/health | head -c 400 && echo || echo "Backend is not responding — try: ./deploy/procare.sh start"
    ;;
  menu|*)
    echo "==============================================="
    echo "        ProCare AI — Control Center"
    echo "==============================================="
    echo "  1) Start          تشغيل"
    echo "  2) Stop           إيقاف"
    echo "  3) Restart        إعادة تشغيل"
    echo "  4) Update         تحديث لأحدث نسخة"
    echo "  5) Status         الحالة"
    echo "  6) Logs           السجلات"
    echo "  7) Health check   فحص الاتصال"
    echo "  0) Exit           خروج"
    echo "-----------------------------------------------"
    read -rp "  Choice / اختيار: " choice
    case "$choice" in
      1) exec "$0" start ;;
      2) exec "$0" stop ;;
      3) exec "$0" restart ;;
      4) exec "$0" update ;;
      5) exec "$0" status ;;
      6) exec "$0" logs ;;
      7) exec "$0" health ;;
      *) exit 0 ;;
    esac
    ;;
esac
