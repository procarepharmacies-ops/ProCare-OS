#!/usr/bin/env bash
# ProCare AI — install the "one-click" launcher icon on an UBUNTU desktop.
#
# The .bat files in this folder are WINDOWS-only — they create the desktop icon
# on Windows and do nothing on Ubuntu. On a Linux desktop, run this once instead:
#
#   ./deploy/install-desktop-icon.sh
#
# It writes a .desktop entry with the correct absolute paths (to THIS clone),
# into the applications menu and onto the Desktop, and marks it trusted so a
# double-click launches ProCare and opens the browser.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

# WSL has no Linux desktop — a .desktop icon can't appear there.
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "You are on WSL — there is no Linux desktop to place an icon on."
  echo "Run the system from the Ubuntu terminal:"
  echo "    ./deploy/procare-local.sh"
  echo "then open http://localhost:3000 in your Windows browser."
  echo "(For a Windows desktop icon, copy deploy/ProCare.bat to the Windows Desktop.)"
  exit 0
fi

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
TARGET="$APPS/procare-local.desktop"

# Substitute the placeholder path with this actual clone location.
sed -e "s|/home/YOUR_USER/ProCare-OS|$ROOT|g" deploy/procare-local.desktop > "$TARGET"
chmod +x "$TARGET"

# Also drop it on the Desktop, if there is one, and mark it trusted (GNOME).
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESK" ]; then
  cp "$TARGET" "$DESK/procare-local.desktop"
  chmod +x "$DESK/procare-local.desktop"
  gio set "$DESK/procare-local.desktop" metadata::trusted true 2>/dev/null || true
  echo "Icon placed on the Desktop: $DESK/procare-local.desktop"
fi

echo "Installed: $TARGET"
echo "Find 'ProCare AI (Local)' in your apps menu, or double-click the Desktop icon."
