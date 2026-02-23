"""
notifications/mqtt_led_sender.py
Module centralisé pour l'envoi des configurations LED via MQTT.
Utilisé par notification_manager.py et notificationsScreen.py
"""
import paho.mqtt.client as mqtt
import json

# ========== CONFIGURATION MQTT ==========
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "ledstrip/config"

# Client MQTT global
mqtt_client = mqtt.Client(client_id="led_sender_client")

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[LED_SENDER] ✓ Connecté à MQTT {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"[LED_SENDER] ✗ Erreur connexion MQTT: {e}")

# ========== MAPPING MODE TEXTE → INT ==========
MODE_MAPPING = {
    "OFF": 0,
    "ON": 1,
    "BLINK": 2,
    "FADING_BLINK": 3,
}

# ========== FONCTIONS D'ENVOI ==========

def send_led_config(group, color, intensity, mode):
    """
    Envoie une configuration LED directement avec paramètres
    
    Args:
        group (int): Groupe LED (0-7) - FORCÉ À 7
        color (str): Couleur au format "#RRGGBB"
        intensity (int): Intensité (0-255)
        mode (int ou str): Mode (0-9 ou "ON"/"OFF"/"BLINK"/"FADING_BLINK")
    """
    # ========== FORCER LE GROUP À 7 ==========
    group = 7
    
    # Validation et conversion de l'intensité
    try:
        intensity = int(intensity)
        if not (0 <= intensity <= 255):
            print(f"[LED_SENDER] ⚠ Intensité invalide: {intensity}, utilisation de 255")
            intensity = 255
    except (ValueError, TypeError):
        print(f"[LED_SENDER] ⚠ Intensité invalide: {intensity}, utilisation de 255")
        intensity = 255
    
    # Validation de la couleur
    color = str(color).upper()
    if not color.startswith('#'):
        color = '#' + color
    if len(color) != 7:
        print(f"[LED_SENDER] ⚠ Couleur invalide: {color}, utilisation de #FFFFFF")
        color = "#FFFFFF"
    
    # Conversion du mode si nécessaire
    if isinstance(mode, str):
        mode = MODE_MAPPING.get(mode.upper(), 1)  # Par défaut ON = 1
    
    try:
        mode = int(mode)
        if not (0 <= mode <= 9):
            print(f"[LED_SENDER] ⚠ Mode invalide: {mode}, utilisation de 1 (ON)")
            mode = 1
    except (ValueError, TypeError):
        print(f"[LED_SENDER] ⚠ Mode invalide: {mode}, utilisation de 1 (ON)")
        mode = 1
    
    # Construction du payload
    payload = {
        "group": group,
        "color": color,
        "intensity": intensity,
        "mode": mode
    }
    
    # Envoi MQTT (format compact sans espaces)
    try:
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, separators=(',', ':')))
        print(f"[LED_SENDER] ✓ Published: {payload}")
    except Exception as e:
        print(f"[LED_SENDER] ✗ Erreur publication: {e}")

def send_led_config_from_dict(config_dict):
    """
    Envoie une configuration LED depuis un dictionnaire
    
    Args:
        config_dict (dict): Dictionnaire contenant:
            - group (int): Groupe LED - FORCÉ À 7
            - color (str): Couleur "#RRGGBB"
            - intensity (int): Intensité 0-255
            - mode (str ou int): Mode
    """
    group = config_dict.get("group", 7)  # Par défaut 7, mais sera forcé de toute façon
    color = config_dict.get("color", "#FFFFFF")
    intensity = config_dict.get("intensity", 255)
    mode = config_dict.get("mode", "ON")
    
    send_led_config(group, color, intensity, mode)

def turn_off_leds(group=7):
    """
    Éteint les LEDs du groupe spécifié
    
    Args:
        group (int): Groupe LED à éteindre (défaut: 7)
    """
    payload = {
        "group": 7,  # Toujours groupe 7
        "color": "#000000",
        "intensity": 0,
        "mode": 0  # OFF
    }
    
    try:
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, separators=(',', ':')))
        print(f"[LED_SENDER] ✓ LEDs éteintes: {payload}")
    except Exception as e:
        print(f"[LED_SENDER] ✗ Erreur extinction: {e}")

# ========== TEST DIRECT ==========
if __name__ == "__main__":
    print("[LED_SENDER] Test d'envoi de configuration LED")
    
    # Test 1: Envoi direct
    print("\n--- Test 1: Envoi direct ---")
    send_led_config(group=1, color="#FF0000", intensity=200, mode="BLINK")
    
    # Test 2: Depuis dictionnaire
    print("\n--- Test 2: Depuis dictionnaire ---")
    test_config = {
        "group": 2,
        "color": "#00FF00",
        "intensity": 150,
        "mode": "ON"
    }
    send_led_config_from_dict(test_config)
    
    # Test 3: Extinction
    print("\n--- Test 3: Extinction ---")
    import time
    time.sleep(2)
    turn_off_leds()
    
    print("\n[LED_SENDER] Tests terminés")
    
    time.sleep(1)