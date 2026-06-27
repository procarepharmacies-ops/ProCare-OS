#!/usr/bin/env bash
#
# ProCare OS — one-shot deploy to a Multipass VM named "foo".
#
# Run this on the HOST machine that has multipass installed (not inside the VM).
# It provisions foo (if missing), installs Docker, copies this repo in, builds &
# starts the full stack with docker compose, and prints the live URL.
#
#   ./deploy/foo-up.sh                 # VM name "foo", uses the current repo
#   VM=foo ./deploy/foo-up.sh          # override the VM name
#
# Re-runnable: it reuses an existing "foo" and just redeploys.
set -euo pipefail

VM="${VM:-foo}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR="/home/ubuntu/procare-os"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

command -v multipass >/dev/null || { echo "multipass not found — install it first: https://multipass.run"; exit 1; }

# 1) Ensure the VM exists and is running.
if multipass info "$VM" >/dev/null 2>&1; then
  say "Using existing VM '$VM'"
  multipass start "$VM" 2>/dev/null || true
else
  say "Launching VM '$VM' (2 CPU, 2G RAM, 10G disk)"
  multipass launch --name "$VM" --cpus 2 --memory 2G --disk 10G
fi

# 2) Install Docker in the VM (idempotent).
if ! multipass exec "$VM" -- bash -lc 'command -v docker >/dev/null'; then
  say "Installing Docker in '$VM'"
  multipass exec "$VM" -- bash -lc 'curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu'
fi

# 3) Copy the repo in (excluding heavy/local dirs via git archive when possible).
say "Copying the repo into '$VM:$REMOTE_DIR'"
multipass exec "$VM" -- bash -lc "rm -rf '$REMOTE_DIR' && mkdir -p '$REMOTE_DIR'"
if git -C "$REPO_ROOT" rev-parse >/dev/null 2>&1; then
  git -C "$REPO_ROOT" archive --format=tar HEAD | multipass exec "$VM" -- bash -lc "tar -x -C '$REMOTE_DIR'"
else
  tar -C "$REPO_ROOT" --exclude='.git' --exclude='node_modules' --exclude='.next' -cf - . \
    | multipass exec "$VM" -- bash -lc "tar -x -C '$REMOTE_DIR'"
fi

# 4) Build & start the stack. (sg docker => no logout needed for the new group.)
say "Building & starting the stack (first build pulls base images; give it a few minutes)"
multipass exec "$VM" -- bash -lc "cd '$REMOTE_DIR' && sudo docker compose up -d --build"

# 5) Print the live URL.
IP="$(multipass info "$VM" --format csv | awk -F, 'NR==2 {print $3}')"
say "ProCare OS is live on '$VM'"
echo "   UI:   http://$IP:3000"
echo "   API:  http://$IP:8080/docs"
echo
echo "Logs:  multipass exec $VM -- sudo docker compose -f $REMOTE_DIR/docker-compose.yml logs -f"
echo "Stop:  multipass exec $VM -- sudo docker compose -f $REMOTE_DIR/docker-compose.yml down"
