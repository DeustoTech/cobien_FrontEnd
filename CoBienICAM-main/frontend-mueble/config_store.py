import copy
import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
UNIFIED_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

LEGACY_SETTINGS_PATH = os.path.join(BASE_DIR, "settings", "settings.json")
LEGACY_NOTIFICATIONS_PATH = os.path.join(CONFIG_DIR, "notifications_config.json")
LEGACY_PIN_PATH = os.path.join(BASE_DIR, "settings", "pin.txt")
LEGACY_WEATHER_PATH = os.path.join(CONFIG_DIR, "config_weather.txt")
LEGACY_RFID_PATH = os.path.join(CONFIG_DIR, "config_rfid.txt")
VERSION_PATH = os.path.join(BASE_DIR, "VERSION")

DEFAULT_UNIFIED_CONFIG = {
    "meta": {
        "schema_version": 1,
        "updated_at": "",
    },
    "settings": {
        "language": "es",
        "weather_cities": [],
        "weather_city_catalog": [],
        "weather_primary_city": "",
        "button_colors": {},
        "rfid_actions": {},
        "microphone_device": "",
        "device_id": os.getenv("COBIEN_DEVICE_ID", "CoBien1"),
        "videocall_room": os.getenv("COBIEN_VIDEOCALL_ROOM", os.getenv("COBIEN_DEVICE_ID", "CoBien1")),
        "device_location": os.getenv("COBIEN_DEVICE_LOCATION", "Bilbao"),
        "joke_category": "general",
        "idle_timeout_sec": 60,
    },
    "notifications": {
        "videollamada": {"group": 1, "intensity": 255, "color": "#00FF00", "mode": "ON", "ringtone": ""},
        "nuevo_evento": {"group": 2, "intensity": 255, "color": "#FF0000", "mode": "ON", "ringtone": ""},
        "nueva_foto": {"group": 3, "intensity": 255, "color": "#0000FF", "mode": "BLINK", "ringtone": ""},
    },
    "security": {
        "settings_pin": "1234",
    },
    "services": {
        "mqtt_local_broker": os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost"),
        "mqtt_local_port": int(os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883")),
        "mqtt_backend_broker": os.getenv("COBIEN_MQTT_BACKEND_BROKER", "broker.hivemq.com"),
        "mqtt_backend_port": int(os.getenv("COBIEN_MQTT_BACKEND_PORT", "1883")),
        "backend_base_url": os.getenv("COBIEN_BACKEND_BASE_URL", "http://portal.co-bien.eu"),
        "owm_api_key": os.getenv("OWM_API_KEY", ""),
        "news_api_key": os.getenv("NEWS_API_KEY", ""),
        "spoonacular_api_key": os.getenv("SPOONACULAR_API_KEY", ""),
        "mongo_uri": os.getenv("MONGO_URI", ""),
        "http_timeout_sec": float(os.getenv("COBIEN_HTTP_TIMEOUT", "8")),
        "tts_rate": int(os.getenv("COBIEN_TTS_RATE", "155")),
        "tts_volume": float(os.getenv("COBIEN_TTS_VOLUME", "0.85")),
        "disable_system_sleep": os.getenv("COBIEN_DISABLE_SYSTEM_SLEEP", "0"),
        "notify_api_key": os.getenv("COBIEN_NOTIFY_API_KEY", "test_jules"),
        "pizarra_notify_url": os.getenv("COBIEN_PIZARRA_NOTIFY_URL", "http://portal.co-bien.eu/pizarra/api/notify/"),
        "pizarra_messages_url": os.getenv("COBIEN_PIZARRA_API_URL", "http://portal.co-bien.eu/pizarra/api/messages/"),
        "pizarra_delete_url_template": os.getenv(
            "COBIEN_PIZARRA_DELETE_URL_TEMPLATE",
            "http://portal.co-bien.eu/pizarra/api/messages/{post_id}/delete/",
        ),
        "contacts_api_url": os.getenv("COBIEN_CONTACTS_API_URL", "http://portal.co-bien.eu/pizarra/api/contacts/"),
        "portal_videocall_url": os.getenv("COBIEN_PORTAL_VIDEOCALL_URL", "https://portal.co-bien.eu/videocall/"),
        "portal_call_answered_url": os.getenv(
            "COBIEN_PORTAL_CALL_ANSWERED_URL",
            "https://portal.co-bien.eu/videocall/call-answered/",
        ),
        "openweather_current_url": "https://api.openweathermap.org/data/2.5/weather",
        "openweather_forecast_url": "https://api.openweathermap.org/data/2.5/forecast",
        "news_api_url": "https://newsapi.org/v2/top-headlines",
        "spoonacular_search_url": "https://api.spoonacular.com/recipes/complexSearch",
        "spoonacular_info_url_template": "https://api.spoonacular.com/recipes/{id}/information",
        "open_meteo_url": "https://api.open-meteo.com/v1/forecast",
        "nominatim_search_url": "https://nominatim.openstreetmap.org/search",
    },
    "software": {
        "version": "",
    },
}


def _parse_legacy_weather_file(path):
    active = []
    catalog = []
    if not os.path.exists(path):
        return active, catalog
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    city = line[1:].strip()
                    if city and city not in catalog:
                        catalog.append(city)
                    continue
                city = line
                if city not in catalog:
                    catalog.append(city)
                if city not in active:
                    active.append(city)
    except Exception:
        pass
    return active, catalog


def _parse_legacy_rfid_file(path):
    mappings = {}
    if not os.path.exists(path):
        return mappings
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                left, right = line.split("=", 1)
                card_id = left.strip()
                action_text = right.strip()
                if not card_id.isdigit():
                    continue

                action = "day_events"
                extra = ""
                low = action_text.lower()
                if low.startswith("weather") or low.startswith("meteo"):
                    action = "weather"
                    if ":" in action_text:
                        extra = action_text.split(":", 1)[1].strip()
                elif low.startswith("video") or low.startswith("videollamada"):
                    action = "videocall"
                    if ":" in action_text:
                        extra = action_text.split(":", 1)[1].strip()

                mappings[str(card_id)] = {"action": action, "extra": extra}
    except Exception:
        pass
    return mappings


def _deep_merge_dict(base, incoming):
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _read_version_file():
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _build_initial_from_legacy():
    config = copy.deepcopy(DEFAULT_UNIFIED_CONFIG)

    if os.path.exists(LEGACY_SETTINGS_PATH):
        try:
            settings_data = _read_json(LEGACY_SETTINGS_PATH)
            if isinstance(settings_data, dict):
                _deep_merge_dict(config["settings"], settings_data)
        except Exception:
            pass

    if os.path.exists(LEGACY_NOTIFICATIONS_PATH):
        try:
            notifications_data = _read_json(LEGACY_NOTIFICATIONS_PATH)
            if isinstance(notifications_data, dict):
                _deep_merge_dict(config["notifications"], notifications_data)
        except Exception:
            pass

    try:
        pin_env = os.getenv("COBIEN_SETTINGS_PIN", "").strip()
        if pin_env:
            config["security"]["settings_pin"] = pin_env
        elif os.path.exists(LEGACY_PIN_PATH):
            with open(LEGACY_PIN_PATH, "r", encoding="utf-8") as f:
                legacy_pin = f.read().strip()
                if legacy_pin:
                    config["security"]["settings_pin"] = legacy_pin
    except Exception:
        pass

    config["software"]["version"] = _read_version_file()
    config["meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return config


def _ensure_schema(data):
    if not isinstance(data, dict):
        data = copy.deepcopy(DEFAULT_UNIFIED_CONFIG)
    merged = copy.deepcopy(DEFAULT_UNIFIED_CONFIG)
    _deep_merge_dict(merged, data)

    # One-way compatibility migration from legacy text files when unified values are missing.
    if not merged["settings"].get("weather_cities"):
        active, catalog = _parse_legacy_weather_file(LEGACY_WEATHER_PATH)
        if active:
            merged["settings"]["weather_cities"] = active
        if catalog:
            merged["settings"]["weather_city_catalog"] = catalog
    elif not merged["settings"].get("weather_city_catalog"):
        merged["settings"]["weather_city_catalog"] = list(merged["settings"]["weather_cities"])

    if not merged["settings"].get("rfid_actions"):
        legacy_rfid = _parse_legacy_rfid_file(LEGACY_RFID_PATH)
        if legacy_rfid:
            merged["settings"]["rfid_actions"] = legacy_rfid

    merged["meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    if not merged["software"].get("version"):
        merged["software"]["version"] = _read_version_file()
    return merged


def load_config():
    if os.path.exists(UNIFIED_CONFIG_PATH):
        try:
            data = _read_json(UNIFIED_CONFIG_PATH)
        except Exception:
            data = _build_initial_from_legacy()
    else:
        data = _build_initial_from_legacy()

    normalized = _ensure_schema(data)
    _write_json(UNIFIED_CONFIG_PATH, normalized)
    return normalized


def save_config(config):
    normalized = _ensure_schema(config)
    _write_json(UNIFIED_CONFIG_PATH, normalized)
    return normalized


def load_section(section_name, default=None):
    config = load_config()
    if section_name in config:
        return copy.deepcopy(config[section_name])
    return copy.deepcopy(default)


def save_section(section_name, section_data):
    config = load_config()
    config[section_name] = copy.deepcopy(section_data)
    return save_config(config)


def load_services():
    return load_section("services", {})


def get_service(key, default=None):
    services = load_services()
    return services.get(key, default)
