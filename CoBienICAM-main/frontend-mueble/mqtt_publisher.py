# mqtt_publisher.py
import requests
import os
import json
import paho.mqtt.client as mqtt
from datetime import date, datetime
from timezonefinder import TimezoneFinder
from icso_data.imu_logger import log_imu_event
from icso_data.log_writer import load_full_state as load_state

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC_RFID_IN = "rfid/read"
TOPIC_SENSORS_IN = "sensors/update"
TOPIC_APP_NAV_OUT = "app/nav"
TOPIC_IMU = "imu/update"
TOPIC_WEATHER_RELOAD = "weather/reload"
TOPIC_RFID_RELOAD = "rfid/actions_reload"
TOPIC_EVENTS_RELOAD = "events/reload"  
TOPIC_BOARD_RELOAD = "board/reload"    

today = date.today().isoformat()
tf = TimezoneFinder()

# Geocoding the cities in config_weather.txt
def geocode_city(city_name):
    try:
        url = "https://nominatim.openstreetmap.org/search"
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

# Loading the cities in config_weather.txt
def load_weather_config(path="config/config_weather.txt"):
    cities = []
    import os
    if not os.path.exists(path):
        print(f"[CONFIG] Fichier météo introuvable : {path}")
        return cities
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                cities.append(line)
                print(f"[CONFIG]   + Ville : {line}")
    except Exception as e:
        print("[CONFIG WEATHER ERROR]", e)
    return cities

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

# Loading the RFID cards actions in config_rfid.txt
def load_rfid_config(path="config/config_rfid.txt"):
    contacts_map = load_contacts_map()
    actions = {}
    import os
    if not os.path.exists(path):
        print(f"[CONFIG] Fichier RFID introuvable : {path}")
        return actions
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                left, right = line.split("=", 1)
                card_id = int(left.strip())
                action_text = right.strip().lower()

                # --- Weather
                # Charger la liste des villes valides depuis config_weather.txt
                valid_cities = []
                try:
                    with open("config/config_weather.txt", "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):  # lignes commentées = villes inactives
                                continue
                            valid_cities.append(line)
                except Exception as e:
                    print(f"[WARN] Impossible de charger config_weather.txt : {e}")

                # --- Weather
                if action_text.lower().startswith("weather") or action_text.lower().startswith("meteo"):
                    if ":" in action_text:
                        city = action_text.split(":", 1)[1].strip()
                        city = city[0].upper() + city[1:] if city else city
                        if city not in valid_cities:
                            print(f"[WARN] Ville {city} ignorée (non listée dans config_weather.txt)")
                            continue  # on saute cette carte
                        geo = geocode_city(city)
                        if geo:
                            actions[card_id] = {
                                "target": "weather",
                                "extra": geo
                            }

                # --- Events
                elif action_text == "events" or action_text == "eventos":
                    actions[card_id] = {
                        "target": "day_events",
                        "extra": {"day": date.today().isoformat()}
                    }
                # --- Videocall
                elif action_text.startswith("videocall") or action_text.startswith("videollamada"):
                    contact_display = None
                    if ":" in action_text:
                        contact_display = action_text.split(":", 1)[1].strip()

                    payload = {"target": "videocall"}

                    # Si on a un nom de contact (ex: "Capucine"), on le résout en user (ex: "capucine")
                    if contact_display:
                        user = contacts_map.get(contact_display.lower())
                        if user:
                            payload["extra"] = {"to_user": user, "label": contact_display}
                        else:
                            print(f"[RFID] Contact inconnu : {contact_display} (pas dans list_contacts.txt)")

                    actions[card_id] = payload
                       
    except Exception as e:
        print("[CONFIG RFID ERROR]", e)
    return actions

# Charging the cities while loading the app
global WEATHER_CITIES_RAW
global RFID_ACTIONS
global WEATHER_CITIES_GEO

WEATHER_CITIES_RAW = load_weather_config("config/config_weather.txt")
RFID_ACTIONS = load_rfid_config("config/config_rfid.txt")

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
        
        RFID_ACTIONS = load_rfid_config(path="config/config_rfid.txt")
        
        print(f"[MQTT] ✅ {len(RFID_ACTIONS)} actions RFID rechargées")
        print(f"[MQTT] Actions actuelles : {list(RFID_ACTIONS.keys())}")
        return
    
    # --- WEATHER RELOAD ---
    elif msg.topic == TOPIC_WEATHER_RELOAD:
        print("[MQTT] ⚡ Rechargement météo demandé")
        WEATHER_CITIES_RAW = load_weather_config(path="config/config_weather.txt")
        
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