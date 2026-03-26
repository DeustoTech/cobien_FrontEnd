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
CAN_BITRATE="${COBIEN_CAN_BITRATE:-500000}"

echo "=== Launching CoBien System ==="
echo "[PATHS] FRONTEND_REPO_ROOT=$FRONTEND_REPO_ROOT"
echo "[PATHS] MQTT_REPO=$MQTT_REPO"
echo "[PATHS] BRIDGE_DIR=$BRIDGE_DIR"
echo "[PATHS] VENV_ACTIVATE=$VENV_ACTIVATE"

##########################################
# CLEAN PREVIOUS COBIEN TERMINALS
##########################################
echo "[CLEAN] Closing previous CoBien terminals..."

for title in "CAN BUS" "MQTT-CAN BRIDGE" "COBIEN APP"
do
    wmctrl -ic "$(wmctrl -l | grep "$title" | awk '{print $1}')" 2>/dev/null
done

sleep 1

################################
# TERMINAL 1 : CAN BUS
################################
gnome-terminal --title="CAN BUS" -- bash -c "
echo '[CAN] Initializing the CAN BUS';
sudo /sbin/ip link set can0 down;
sudo /sbin/ip link set can0 type can bitrate $CAN_BITRATE;
sudo /sbin/ip link set can0 up;
echo '[CAN] candump active';
candump can0;
exec bash
"

sleep 2

##########################################
# TERMINAL 2 : MQTT ↔ CAN BRIDGE
##########################################
gnome-terminal --title="MQTT-CAN BRIDGE" -- bash -c "
echo '[BRIDGE] Build & Launch';
cd \"$BRIDGE_DIR\" || exit;
rm -rf build;
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo;
cmake --build build -j;
./build/cobien-bridge \"$CAN_CONFIG\";
exec bash
"

sleep 2

#################################
# TERMINAL 3 : APPLICATION PYTHON
#################################
gnome-terminal --title="COBIEN APP" -- bash -c "
echo '[APP] Activating Virtual env';
if [ -f \"$VENV_ACTIVATE\" ]; then
  source \"$VENV_ACTIVATE\";
else
  echo '[APP] Virtual env not found, using system python';
fi
cd \"$SCRIPT_DIR\" || exit;
$PYTHON_BIN mainApp.py;
exec bash
"
