#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_SRC_DIR="$SCRIPT_DIR/systemd"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

mkdir -p "$SYSTEMD_USER_DIR"

install -m 0644 "$SYSTEMD_SRC_DIR/cobien-launcher.service" "$SYSTEMD_USER_DIR/cobien-launcher.service"
install -m 0644 "$SYSTEMD_SRC_DIR/cobien-update.service" "$SYSTEMD_USER_DIR/cobien-update.service"
install -m 0644 "$SYSTEMD_SRC_DIR/cobien-update.timer" "$SYSTEMD_USER_DIR/cobien-update.timer"

systemctl --user daemon-reload
systemctl --user enable --now cobien-launcher.service
systemctl --user enable --now cobien-update.timer

echo "[OK] Installed systemd user units in: $SYSTEMD_USER_DIR"
echo "[OK] Enabled: cobien-launcher.service"
echo "[OK] Enabled: cobien-update.timer"
echo
echo "Recommended cleanup to avoid duplicates:"
echo "  rm -f ~/.config/autostart/cobien-launcher.desktop"
echo "  crontab -l | grep -v 'cobien-launcher.sh --mode update-once' | crontab -"
echo
echo "Useful commands:"
echo "  systemctl --user status cobien-launcher.service"
echo "  systemctl --user list-timers | grep cobien-update"
echo "  journalctl --user -u cobien-launcher.service -f"
