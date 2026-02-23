#!/bin/bash

echo "=== Launching CoBien System ==="

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
sudo /sbin/ip link set can0 type can bitrate 500000;
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
cd ~/Desktop/CO_BIEN_MQTT_Dictionnary-Joseph/Interface_MQTT_CAN_c || exit;
rm -rf build;
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo;
cmake --build build -j;
./build/cobien-bridge config/conversion.json;
exec bash
"

sleep 2

#################################
# TERMINAL 3 : APPLICATION PYTHON
#################################
gnome-terminal --title="COBIEN APP" -- bash -c "
echo '[APP] Activating Virtual env';
cd ~/Desktop || exit;
source CoBien/bin/activate;
cd CoBienICAM/frontend-mueble || exit;
python3 mainApp.py;
exec bash
"
