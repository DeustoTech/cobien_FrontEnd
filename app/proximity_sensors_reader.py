"""MQTT-based proximity sensor reader for Cobien."""
import json
import os

import paho.mqtt.client as mqtt

from icso_data.proximity_sensor_logger import log_proximity_event

try:
    from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
except ImportError:
    MQTT_LOCAL_BROKER = os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost")
    MQTT_LOCAL_PORT = int(os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883"))

TOPIC = "proximity/update"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(TOPIC, qos=1)
        print(f"[Proximity Sensor] Connected, subscribed to {TOPIC}")
    else:
        print(f"[Proximity Sensor] Connection failed: {reason_code}")


def on_disconnect(client, userdata, reason_code, properties):
    print(f"[Proximity Sensor] Disconnected: {reason_code}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        can_id = payload.get("can_id")
        event = payload.get("event")
        if can_id is None or event is None:
            print(f"[Proximity Sensor] Missing fields in payload: {payload}")
            return
        log_proximity_event(int(can_id), int(event))
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(f"[Proximity Sensor] Error processing message: {e}")


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        print(
            f"[Proximity Sensor] Connecting to "
            f"{MQTT_LOCAL_BROKER}:{MQTT_LOCAL_PORT}..."
        )
        client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT)
        client.loop_forever()
    except (OSError, ConnectionRefusedError) as e:
        print(f"[Proximity Sensor] Fatal error: {e}")


if __name__ == "__main__":
    main()
