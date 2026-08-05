#!/usr/bin/env bash
# ProCare AI — publish the local (no-Docker) system on the internet via a
# Cloudflare Tunnel, so you can open it from your phone from anywhere.
#
#   ./deploy/install-cloudflare.sh <TUNNEL_TOKEN>
#     (or:  TUNNEL_TOKEN=eyJ... ./deploy/install-cloudflare.sh)
#
# It installs cloudflared, stores the token safely (root-only), and runs the
# tunnel as an always-on systemd service pointing at the local ProCare frontend.
#
# BEFORE running, in the Cloudflare dashboard (one time):
#   1. Zero Trust -> Networks -> Tunnels -> create a tunnel, copy its TOKEN.
#   2. In that tunnel's Public Hostname, add your hostname (e.g.
#      procare.example.com) with Service = HTTP://localhost:3000
#      (match FRONTEND_PORT below if you changed it).
# AFTER: keep AUTH_ENABLED=true so the login screen guards your data online.
set -euo pipefail
cd "$(dirname "$0")/.."

FRONTEND_PORT="${PROCARE_UI_PORT:-3000}"
TOKEN="${1:-${TUNNEL_TOKEN:-}}"

if [ -z "$TOKEN" ]; then
  cat <<'MSG'
Missing tunnel token. Get it from:
  Cloudflare Zero Trust -> Networks -> Tunnels -> (your tunnel) -> token
Then run:
  ./deploy/install-cloudflare.sh <TUNNEL_TOKEN>
MSG
  exit 1
fi

if grep -qi microsoft /proc/version 2>/dev/null && ! systemctl is-system-running >/dev/null 2>&1; then
  echo "WSL without systemd. Either enable systemd (see deploy/install-service.sh),"
  echo "or run the tunnel by hand:  cloudflared tunnel --no-autoupdate run --token <TOKEN>"
  exit 1
fi

# --- Install cloudflared if missing --------------------------------------
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "[1/4] Installing cloudflared…"
  ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
  URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}"
  if command -v curl >/dev/null 2>&1; then sudo curl -fsSL "$URL" -o /usr/local/bin/cloudflared;
  else sudo wget -qO /usr/local/bin/cloudflared "$URL"; fi
  sudo chmod +x /usr/local/bin/cloudflared
else
  echo "[1/4] cloudflared already installed ($(command -v cloudflared))."
fi
CFD="$(command -v cloudflared)"

# --- Store the token root-only (kept out of the unit file) ---------------
echo "[2/4] Storing token (root-only) in /etc/procare/tunnel.env…"
sudo mkdir -p /etc/procare
printf 'TUNNEL_TOKEN=%s\n' "$TOKEN" | sudo tee /etc/procare/tunnel.env >/dev/null
sudo chmod 600 /etc/procare/tunnel.env

# --- systemd service -----------------------------------------------------
echo "[3/4] Writing /etc/systemd/system/procare-tunnel.service…"
sudo tee /etc/systemd/system/procare-tunnel.service >/dev/null <<EOF
[Unit]
Description=ProCare AI Cloudflare Tunnel (publishes localhost:${FRONTEND_PORT})
After=network-online.target procare.service
Wants=network-online.target

[Service]
EnvironmentFile=/etc/procare/tunnel.env
ExecStart=${CFD} tunnel --no-autoupdate run --token \${TUNNEL_TOKEN}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "[4/4] Enabling + starting…"
sudo systemctl daemon-reload
sudo systemctl enable --now procare-tunnel

echo
echo "Done — the tunnel is live and auto-starts on boot."
echo "  status: systemctl status procare-tunnel"
echo "  logs:   journalctl -u procare-tunnel -f"
echo
echo "Reminders:"
echo "  • In Cloudflare, the tunnel's Public Hostname service must be HTTP://localhost:${FRONTEND_PORT}"
echo "  • ProCare itself must be running (./deploy/install-service.sh or procare-local.sh)."
echo "  • Keep AUTH_ENABLED=true so the internet only sees the login screen."
