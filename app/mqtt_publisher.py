# mqtt_publisher.py
import requests
import os
import json
import paho.mqtt.client as mqtt
import time
from datetime import date, datetime
from timezonefinder import TimezoneFinder
from icso_data.imu_logger import log_imu_event
from icso_data.log_writer import load_full_state as load_state
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
from config_store import load_section

BROKER_HOST = MQTT_LOCAL_BROKER
BROKER_PORT = MQTT_LOCAL_PORT
TOPIC_RFID_IN = "rfid/read"
TOPIC_SENSORS_IN = "sensors/update"
TOPIC_APP_NAV_OUT = "app/nav"
TOPIC_IMU = "imu/update"
TOPIC_WEATHER_RELOAD = "weather/reload"
TOPIC_RFID_RELOAD = "rfid/actions_reload"
TOPIC_EVENTS_RELOAD = "events/reload"  
TOPIC_BOARD_RELOAD = "board/reload"    
RFID_DEBOUNCE_SECONDS = 5
_last_rfid_card_id = None
_last_rfid_at = 0.0

today = date.today().isoformat()
tf = TimezoneFinder()
BASE_DIR = os.path.dirname(__file__)

# Geocoding configured cities
def geocode_city(city_name):
    try:
        services_cfg = load_section("services", {})
        url = services_cfg.get("nominatim_search_url", "https://nominatim.openstreetmap.org/search")
        params = {"format": "json", "q": city_name}
        headers = {"User-Agent": "CoBien-App"} 
        resp = requests.get(url, params=params, headers=headers, timeout=5).json()
        
        if not resp:
            print(f"[GEO] Aucun résultat pour : {city_name}")
            return None
        lat = float(resp[0]["lat"])
        lon = float(resp[0]["lon"])
        tz = tf.timezone_at(lat=lat, lng=lon) or "UTC"
        print(f"[GEO] {city_name} → {lat:.2f}, {lon:.2f}, {tz}")
        return {"name": city_name, "lat": lat, "lon": lon, "tz": tz}
    except Exception as e:
        print(f"[GEO] Erreur géocodage {city_name}: {e}")
        return None

# Loading the configured weather cities
def load_primary_weather_city():
    try:
        data = load_section("settings", {})
        return (data.get("weather_primary_city", "") or "").strip()
    except Exception as e:
        print(f"[CONFIG] Weather primary city read error: {e}")
        return ""


def load_weather_config():
    settings = load_section("settings", {})
    configured = settings.get("weather_cities", [])
    if isinstance(configured, list) and configured:
        cities = [str(c).strip() for c in configured if str(c).strip()]
        primary_city = load_primary_weather_city()
        if primary_city and primary_city in cities:
            cities = [primary_city] + [c for c in cities if c != primary_city]
            print(f"[CONFIG] ⭐ Ville prioritaire météo: {primary_city}")
        return cities

    return []

#Charging the contacts
def load_contacts_map():
    """Charge contact_display -> contact_user depuis list_contacts.txt"""
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "contact", "list_contacts.txt"),
        os.path.join(base, "contacts", "list_contacts.txt"),
        os.path.join(base, "videocall", "contact", "list_contacts.txt"),
        os.path.join(base, "videocall", "contacts", "list_contacts.txt"),
        os.path.join(base, "list_contacts.txt"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        print("[CONTACTS] Fichier list_contacts.txt introuvable")
        return {}

    m = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            display, user = [x.strip() for x in line.split("=", 1)]
            if display and user:
                m[display.lower()] = user
    print(f"[CONTACTS] {len(m)} contacts chargés depuis {path}")
    return m

# Loading the configured RFID cards actions
def load_rfid_config():
    settings = load_section("settings", {})
    configured = settings.get("rfid_actions", {})
    if isinstance(configured, dict) and configured:
        contacts_map = load_contacts_map()
        actions = {}
        valid_cities = [str(c).strip() for c in settings.get("weather_cities", []) if str(c).strip()]
        for card_id_str, payload in configured.items():
            try:
                card_id = int(card_id_str)
            except Exception:
                continue
            action = (payload or {}).get("action", "day_events")
            extra = (payload or {}).get("extra", "")

            if action == "weather":
                city = str(extra).strip()
                if not city or (valid_cities and city not in valid_cities):
                    continue
                geo = geocode_city(city)
                if geo:
                    actions[card_id] = {"target": "weather", "extra": geo}
            elif action == "videocall":
                out = {"target": "videocall"}
                contact_display = str(extra).strip()
                if contact_display:
                    user = contacts_map.get(contact_display.lower())
                    if user:
                        out["extra"] = {"to_user": user, "label": contact_display}
                actions[card_id] = out
            else:
                actions[card_id] = {
                    "target": "day_events",
                    "extra": {"day": date.today().isoformat()}
                }
        return actions

    return {}

# Charging the cities while loading the app
global WEATHER_CITIES_RAW
global RFID_ACTIONS
global WEATHER_CITIES_GEO

WEATHER_CITIES_RAW = load_weather_config()
RFID_ACTIONS = load_rfid_config()

# Geocoding the cities
WEATHER_CITIES_GEO = []
for city_name in WEATHER_CITIES_RAW:
    geo = geocode_city(city_name)
    if geo:
        WEATHER_CITIES_GEO.append(geo)
print(f"\n[INIT] {len(WEATHER_CITIES_GEO)} villes géocodées avec succès\n")

# Correspondances actions - buttons
BUTTON_ACTIONS = {
    1: { 
        "target": "main",
        "source": "home_button"
    },
    2: {  
        "target": "voice_cmd",
        "source": "vocal_assistant"
    },
}

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connecté rc={rc}")
    client.subscribe(TOPIC_RFID_IN)
    client.subscribe(TOPIC_SENSORS_IN)
    client.subscribe(TOPIC_IMU)
    client.subscribe(TOPIC_WEATHER_RELOAD)
    client.subscribe(TOPIC_RFID_RELOAD)
    client.subscribe(TOPIC_EVENTS_RELOAD)   # ✅ NEW
    client.subscribe(TOPIC_BOARD_RELOAD)    # ✅ NEW
    print(f"[MQTT] Abonné à : {TOPIC_RFID_IN}, {TOPIC_SENSORS_IN}, {TOPIC_IMU}, "
          f"{TOPIC_WEATHER_RELOAD}, {TOPIC_RFID_RELOAD}, {TOPIC_EVENTS_RELOAD}, {TOPIC_BOARD_RELOAD}")
    
    # Sending the cities via MQTT
    if WEATHER_CITIES_GEO:
        payload = {
            "type": "nav",
            "target": "weather_list",
            "extra": {"cities": WEATHER_CITIES_GEO}
        }
        client.publish(TOPIC_APP_NAV_OUT, json.dumps(payload))
        print(f"[MQTT] Liste météo envoyée : {len(WEATHER_CITIES_GEO)} villes")
    else:
        print("[WARN] Aucune ville à envoyer !")

def on_message(client, userdata, msg):
    global WEATHER_CITIES_RAW, WEATHER_CITIES_GEO, RFID_ACTIONS
    global _last_rfid_card_id, _last_rfid_at
    
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        payload = {}
    
    # --- RFID ---
    if msg.topic == TOPIC_RFID_IN:
        try:
            if isinstance(payload.get("data"), dict):
                card_id = int(payload["data"].get("id", 0))
            else:
                card_id = int(payload.get("id", 0))
        except:
            card_id = 0
        now = time.time()
        if card_id and card_id == _last_rfid_card_id and (now - _last_rfid_at) < RFID_DEBOUNCE_SECONDS:
            print(f"[RFID] Duplicate card ignored during debounce window: {card_id}")
            return
        _last_rfid_card_id = card_id
        _last_rfid_at = now
        action = RFID_ACTIONS.get(card_id)
        if action:
            out = {
                "type": "nav",
                "source": "rfid",
                "target": action["target"],
                "extra": action.get("extra", {})
            }
            client.publish(TOPIC_APP_NAV_OUT, json.dumps(out))
        else:
            print(f"[WARN] RFID inconnue : {card_id}")
        return
    
    # --- RFID ACTIONS RELOAD ---
    elif msg.topic == TOPIC_RFID_RELOAD:
        print("[MQTT] ⚡ Rechargement actions RFID demandé")
        
        RFID_ACTIONS = load_rfid_config()
        
        print(f"[MQTT] ✅ {len(RFID_ACTIONS)} actions RFID rechargées")
        print(f"[MQTT] Actions actuelles : {list(RFID_ACTIONS.keys())}")
        return
    
    # --- WEATHER RELOAD ---
    elif msg.topic == TOPIC_WEATHER_RELOAD:
        print("[MQTT] ⚡ Rechargement météo demandé")
        WEATHER_CITIES_RAW = load_weather_config()
        
        WEATHER_CITIES_GEO = []
        for city_name in WEATHER_CITIES_RAW:
            geo = geocode_city(city_name)
            if geo:
                WEATHER_CITIES_GEO.append(geo)
        
        if WEATHER_CITIES_GEO:
            payload_out = {
                "type": "nav",
                "target": "weather_list",
                "extra": {"cities": WEATHER_CITIES_GEO}
            }
            client.publish(TOPIC_APP_NAV_OUT, json.dumps(payload_out))
            print(f"[MQTT] ✅ {len(WEATHER_CITIES_GEO)} villes rechargées et envoyées")
        return
    
    # ========== EVENTS RELOAD (NEW) ==========
    elif msg.topic == TOPIC_EVENTS_RELOAD:
        print("[MQTT] ⚡ Rechargement événements demandé")
        # Publish reload signal to events screen
        payload_out = {
            "type": "reload",
            "target": "events",
            "timestamp": datetime.now().isoformat()
        }
        client.publish(TOPIC_APP_NAV_OUT, json.dumps(payload_out))
        print(f"[MQTT] 📤 Signal de rechargement événements envoyé")
        return
    
    # ========== BOARD RELOAD (NEW) ==========
    elif msg.topic == TOPIC_BOARD_RELOAD:
        print("[MQTT] ⚡ Rechargement pizarra demandé")
        # Publish reload signal to board screen
        payload_out = {
            "type": "reload",
            "target": "board",
            "timestamp": datetime.now().isoformat()
        }
        client.publish(TOPIC_APP_NAV_OUT, json.dumps(payload_out))
        print(f"[MQTT] 📤 Signal de rechargement pizarra envoyé")
        return
    
    # --- Buttons ---
    elif msg.topic == TOPIC_SENSORS_IN:
        try:
            if isinstance(payload.get("data"), dict):
                pic_id = int(payload["data"].get("PIC", 0))
            else:
                pic_id = int(payload.get("PIC", 0))
        except:
            pic_id = 0
        action = BUTTON_ACTIONS.get(pic_id)
        if action:
            out = {
                "type": "nav",
                "source": action.get("source", "capacitive_buttons"),
                "target": action.get("target", "")
            }
            client.publish(TOPIC_APP_NAV_OUT, json.dumps(out))
        else:
            print(f"[WARN] Bouton inconnu : {pic_id}")
    
        return

    # --- IMU ---
    elif msg.topic == TOPIC_IMU:
        try:
            state = load_state()
            if state["imu"]["state"] == "idle":
                log_imu_event("movement_start")
            else:
                log_imu_event("movement_stop")
            print("[MQTT] IMU event logged")
        except Exception as e:
            print("[MQTT] IMU logging error:", e)
        return

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        print("[MQTT] Loop démarré...")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[MQTT] Arrêt")
    except Exception as e:
        print(f"[MQTT] Erreur : {e}")

if __name__ == "__main__":
    main()
