#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_SRC_DIR="$SCRIPT_DIR/systemd"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SYSTEMD_OVERRIDE_DIR="$SYSTEMD_USER_DIR/cobien-launcher.service.d"
AUTOSTART_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/cobien-launcher.desktop"

mkdir -p "$SYSTEMD_USER_DIR"

# Enable linger so user services survive without an active login session
if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "$USER" || true
  echo "[OK] Enabled linger for user: $USER"
fi

install -m 0644 "$SYSTEMD_SRC_DIR/cobien-launcher.service" "$SYSTEMD_USER_DIR/cobien-launcher.service"
install -m 0644 "$SYSTEMD_SRC_DIR/cobien-update.service" "$SYSTEMD_USER_DIR/cobien-update.service"
install -m 0644 "$SYSTEMD_SRC_DIR/cobien-update.timer" "$SYSTEMD_USER_DIR/cobien-update.timer"

mkdir -p "$SYSTEMD_OVERRIDE_DIR"
cat > "$SYSTEMD_OVERRIDE_DIR/override.conf" <<'EOF'
[Service]
Environment=DISPLAY=:0
Environment=XAUTHORITY=%t/gdm/Xauthority
EOF

if [[ -f "$AUTOSTART_FILE" ]]; then
  rm -f "$AUTOSTART_FILE"
  echo "[OK] Removed legacy autostart file: $AUTOSTART_FILE"
fi

if crontab -l >/dev/null 2>&1; then
  crontab -l | grep -v 'cobien-launcher.sh --mode update-once' | crontab -
  echo "[OK] Removed legacy cron update-once entries (if any)"
fi

systemctl --user daemon-reload
systemctl --user enable --now cobien-launcher.service
systemctl --user enable --now cobien-update.timer
systemctl --user restart cobien-launcher.service

echo "[OK] Installed systemd user units in: $SYSTEMD_USER_DIR"
echo "[OK] Enabled: cobien-launcher.service"
echo "[OK] Enabled: cobien-update.timer"
echo "[OK] Applied graphical override: $SYSTEMD_OVERRIDE_DIR/override.conf"
echo
echo "Verification commands:"
echo "  systemctl --user status cobien-launcher.service"
echo "  systemctl --user list-timers | grep cobien-update"
echo "  journalctl --user -u cobien-launcher.service -f"
