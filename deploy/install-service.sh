#!/usr/bin/env bash
# ProCare AI — install as a systemd service so it auto-starts on boot and stays
# ALWAYS ON (auto-restarts on failure). Ubuntu/Debian desktop or server.
#
#   ./deploy/install-service.sh
#
# It primes the build once, writes /etc/systemd/system/procare.service with THIS
# clone's real user + paths (and a PATH that includes your node/python so systemd
# can find them — the #1 reason a hand-written unit fails), then enables it.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
USER_NAME="$(id -un)"

# --- WSL: systemd must be switched on first -------------------------------
if grep -qi microsoft /proc/version 2>/dev/null; then
  if ! systemctl is-system-running >/dev/null 2>&1 && [ "$(ps -p 1 -o comm= 2>/dev/null)" != "systemd" ]; then
    cat <<'WSL'
You are on WSL and systemd is not enabled. Turn it on once:
  1. Add to /etc/wsl.conf:
       [boot]
       systemd=true
  2. In Windows PowerShell:  wsl --shutdown
  3. Reopen Ubuntu and re-run this script.
(Or skip the service and just run ./deploy/procare-local.sh when you need it.)
WSL
    exit 1
  fi
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found — this machine doesn't use systemd. Use ./deploy/procare-local.sh instead."
  exit 1
fi

# --- Resolve tool locations so the service's PATH can find them -----------
NODE_DIR="$(dirname "$(command -v node)")"
PY_DIR="$(dirname "$(command -v python3)")"
SERVICE_PATH="$NODE_DIR:$PY_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# --- Prime once (install deps + build UI) so boot start is fast -----------
echo "[1/3] Priming dependencies + first build (one time)…"
./deploy/procare-local.sh start
./deploy/procare-local.sh stop || true

# --- Write + enable the unit ---------------------------------------------
UNIT=/etc/systemd/system/procare.service
echo "[2/3] Writing $UNIT (sudo)…"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=ProCare AI pharmacy system (local, no Docker)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER_NAME
WorkingDirectory=$ROOT
Environment=PATH=$SERVICE_PATH
ExecStart=$ROOT/deploy/procare-local.sh start
ExecStop=$ROOT/deploy/procare-local.sh stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "[3/3] Enabling + starting…"
sudo systemctl daemon-reload
sudo systemctl enable --now procare

echo
echo "Done — ProCare now starts on every boot."
echo "  status:  systemctl status procare"
echo "  logs:    journalctl -u procare -f   (app logs: $ROOT/.local-run/*.log)"
echo "  stop:    sudo systemctl stop procare      disable: sudo systemctl disable procare"
echo "  open:    http://localhost:3000"
