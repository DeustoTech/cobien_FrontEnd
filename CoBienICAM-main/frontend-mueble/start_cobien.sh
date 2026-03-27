#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="${COBIEN_WORKSPACE_ROOT:-$(cd "$FRONTEND_REPO_ROOT/.." && pwd)}"
MQTT_REPO="${COBIEN_MQTT_REPO:-$WORKSPACE_ROOT/cobien_MQTT_Dictionnary}"
BRIDGE_DIR="${COBIEN_BRIDGE_DIR:-$MQTT_REPO/Interface_MQTT_CAN_c}"
CAN_CONFIG="${COBIEN_CAN_CONFIG:-$BRIDGE_DIR/config/conversion.json}"
VENV_ACTIVATE="${COBIEN_VENV_ACTIVATE:-$FRONTEND_REPO_ROOT/.venv/bin/activate}"
PYTHON_BIN="${COBIEN_PYTHON_BIN:-python3}"
UV_BIN="${COBIEN_UV_BIN:-uv}"
UV_PYTHON="${COBIEN_UV_PYTHON:-3.11}"
FRONTEND_APP_DIR="${COBIEN_FRONTEND_APP_DIR:-$SCRIPT_DIR}"
CAN_BITRATE="${COBIEN_CAN_BITRATE:-500000}"
LOG_DIR="${COBIEN_LOG_DIR:-$FRONTEND_REPO_ROOT/logs}"

mkdir -p "$LOG_DIR"

can_command() {
  cat <<EOF
echo '[CAN] Initializing the CAN BUS';
sudo /sbin/ip link set can0 down;
sudo /sbin/ip link set can0 type can bitrate $CAN_BITRATE;
sudo /sbin/ip link set can0 up;
echo '[CAN] candump active';
candump can0;
exec bash
EOF
}

bridge_command() {
  cat <<EOF
echo '[BRIDGE] Build & Launch';
cd "$BRIDGE_DIR" || exit;
rm -rf build;
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo;
cmake --build build -j;
./build/cobien-bridge "$CAN_CONFIG";
exec bash
EOF
}

app_command() {
  cat <<EOF
echo '[APP] Launching with uv';
cd "$FRONTEND_APP_DIR" || exit;
if command -v "$UV_BIN" >/dev/null 2>&1; then
  "$UV_BIN" run --python "$UV_PYTHON" --project "$FRONTEND_APP_DIR" mainApp.py;
else
  echo '[APP] uv not found, using fallback python';
  if [ -f "$VENV_ACTIVATE" ]; then
    source "$VENV_ACTIVATE";
  fi
  "$PYTHON_BIN" mainApp.py;
fi
exec bash
EOF
}

can_open_terminals() {
  [[ -n "${DISPLAY:-}" ]] && command -v gnome-terminal >/dev/null 2>&1
}

launch_named_terminal() {
  local title="$1"
  local command_text="$2"
  if can_open_terminals; then
    gnome-terminal --title="$title" -- bash -lc "$command_text" || return 1
    return 0
  fi
  return 1
}

launch_background() {
  local name="$1"
  local command_text="$2"
  local log_file="$LOG_DIR/${name}.log"
  echo "[FALLBACK] Launching $name in background. Log: $log_file"
  nohup bash -lc "$command_text" >"$log_file" 2>&1 &
}

echo "=== Launching CoBien System ==="
echo "[PATHS] FRONTEND_REPO_ROOT=$FRONTEND_REPO_ROOT"
echo "[PATHS] MQTT_REPO=$MQTT_REPO"
echo "[PATHS] BRIDGE_DIR=$BRIDGE_DIR"
echo "[PATHS] VENV_ACTIVATE=$VENV_ACTIVATE"
echo "[PATHS] UV_BIN=$UV_BIN"
echo "[PATHS] FRONTEND_APP_DIR=$FRONTEND_APP_DIR"
echo "[PATHS] LOG_DIR=$LOG_DIR"
if can_open_terminals; then
  echo "[TERM] gnome-terminal available on DISPLAY=${DISPLAY:-}"
else
  echo "[TERM] No graphical terminal available, using fallback mode"
fi

##########################################
# CLEAN PREVIOUS COBIEN TERMINALS
##########################################
echo "[CLEAN] Closing previous CoBien terminals..."

for title in "CAN BUS" "MQTT-CAN BRIDGE" "COBIEN APP"
do
    window_id="$(wmctrl -l 2>/dev/null | awk -v title="$title" '$0 ~ title {print $1; exit}')"
    if [[ -n "${window_id:-}" ]]; then
        wmctrl -ic "$window_id" >/dev/null 2>&1 || true
    fi
done

sleep 1

################################
# TERMINAL 1 : CAN BUS
################################
if ! launch_named_terminal "CAN BUS" "$(can_command)"; then
    launch_background "can-bus" "$(can_command)"
fi

sleep 2

##########################################
# TERMINAL 2 : MQTT ↔ CAN BRIDGE
##########################################
if ! launch_named_terminal "MQTT-CAN BRIDGE" "$(bridge_command)"; then
    launch_background "mqtt-can-bridge" "$(bridge_command)"
fi

sleep 2

#################################
# TERMINAL 3 : APPLICATION PYTHON
#################################
if ! launch_named_terminal "COBIEN APP" "$(app_command)"; then
    echo "[APP] Launching in current shell"
    bash -lc "$(app_command)"
fi
