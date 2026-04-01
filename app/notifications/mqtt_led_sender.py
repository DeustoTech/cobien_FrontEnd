"""
notifications/mqtt_led_sender.py
Centralized helper for sending LED strip configuration via MQTT.
Used by notification_manager.py and notificationsScreen.py.
"""
import paho.mqtt.client as mqtt
import json
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

# ========== MQTT CONFIGURATION ==========
MQTT_TOPIC = "ledstrip/config"

# Global MQTT client
mqtt_client = mqtt.Client(client_id="led_sender_client")

try:
    mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
    mqtt_client.loop_start()
    print(f"[LED_SENDER] ✓ Connected to MQTT {MQTT_LOCAL_BROKER}:{MQTT_LOCAL_PORT}")
except Exception as e:
    print(f"[LED_SENDER] ✗ MQTT connection error: {e}")

# ========== MODE STRING -> INT MAPPING ==========
MODE_MAPPING = {
    "OFF": 0,
    "ON": 1,
    "BLINK": 2,
    "FADING_BLINK": 3,
}

# ========== SEND HELPERS ==========

def send_led_config(group, color, intensity, mode):
    """
    Send LED configuration directly from explicit parameters.
    
    Args:
        group (int): LED group (0-7) - forced to 7 by design.
        color (str): Color in "#RRGGBB" format.
        intensity (int): Intensity (0-255).
        mode (int or str): Mode (0-9 or "ON"/"OFF"/"BLINK"/"FADING_BLINK").
    """
    # ========== FORCE GROUP TO 7 ==========
    group = 7
    
    # Validate and normalize intensity
    try:
        intensity = int(intensity)
        if not (0 <= intensity <= 255):
            print(f"[LED_SENDER] ⚠ Invalid intensity: {intensity}, using 255")
            intensity = 255
    except (ValueError, TypeError):
        print(f"[LED_SENDER] ⚠ Invalid intensity: {intensity}, using 255")
        intensity = 255
    
    # Validate color
    color = str(color).upper()
    if not color.startswith('#'):
        color = '#' + color
    if len(color) != 7:
        print(f"[LED_SENDER] ⚠ Invalid color: {color}, using #FFFFFF")
        color = "#FFFFFF"
    
    # Normalize mode
    if isinstance(mode, str):
        mode = MODE_MAPPING.get(mode.upper(), 1)  # Default ON = 1
    
    try:
        mode = int(mode)
        if not (0 <= mode <= 9):
            print(f"[LED_SENDER] ⚠ Invalid mode: {mode}, using 1 (ON)")
            mode = 1
    except (ValueError, TypeError):
        print(f"[LED_SENDER] ⚠ Invalid mode: {mode}, using 1 (ON)")
        mode = 1
    
    # Build payload
    payload = {
        "group": group,
        "color": color,
        "intensity": intensity,
        "mode": mode
    }
    
    # Publish compact JSON payload
    try:
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, separators=(',', ':')))
        print(f"[LED_SENDER] ✓ Published: {payload}")
    except Exception as e:
        print(f"[LED_SENDER] ✗ Publish error: {e}")

def send_led_config_from_dict(config_dict):
    """
    Send LED configuration from a dictionary.
    
    Args:
        config_dict (dict): Dictionary containing:
            - group (int): LED group - forced to 7
            - color (str): Color "#RRGGBB"
            - intensity (int): Intensity 0-255
            - mode (str ou int): Mode
    """
    group = config_dict.get("group", 7)  # Default 7, and still forced
    color = config_dict.get("color", "#FFFFFF")
    intensity = config_dict.get("intensity", 255)
    mode = config_dict.get("mode", "ON")
    
    send_led_config(group, color, intensity, mode)

def turn_off_leds(group=7):
    """
    Turn off LEDs for the configured group.
    
    Args:
        group (int): Target LED group (default: 7)
    """
    payload = {
        "group": 7,  # Always group 7
        "color": "#000000",
        "intensity": 0,
        "mode": 0  # OFF
    }
    
    try:
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, separators=(',', ':')))
        print(f"[LED_SENDER] ✓ LEDs turned off: {payload}")
    except Exception as e:
        print(f"[LED_SENDER] ✗ Turn-off error: {e}")

# ========== DIRECT SMOKE TEST ==========
if __name__ == "__main__":
    print("[LED_SENDER] LED configuration smoke test")
    
    # Test 1: Direct send
    print("\n--- Test 1: Envoi direct ---")
    send_led_config(group=1, color="#FF0000", intensity=200, mode="BLINK")
    
    # Test 2: From dictionary
    print("\n--- Test 2: Depuis dictionnaire ---")
    test_config = {
        "group": 2,
        "color": "#00FF00",
        "intensity": 150,
        "mode": "ON"
    }
    send_led_config_from_dict(test_config)
    
    # Test 3: Turn off
    print("\n--- Test 3: Extinction ---")
    import time
    time.sleep(2)
    turn_off_leds()
    
    print("\n[LED_SENDER] Smoke tests finished")
    
    time.sleep(1)
