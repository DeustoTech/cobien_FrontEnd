import copy
import json
import os
import re
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOCAL_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.local.json")
LEGACY_UNIFIED_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

LEGACY_SETTINGS_PATH = os.path.join(BASE_DIR, "settings", "settings.json")
LEGACY_NOTIFICATIONS_PATH = os.path.join(CONFIG_DIR, "notifications_config.json")
LEGACY_PIN_PATH = os.path.join(BASE_DIR, "settings", "pin.txt")
VERSION_PATH = os.path.join(BASE_DIR, "VERSION")

SENSITIVE_CONFIG = {
    "security": {
        "settings_pin": {"env": "COBIEN_SETTINGS_PIN"},
    },
    "services": {
        "owm_api_key": {"env": "OWM_API_KEY"},
        "news_api_key": {"env": "NEWS_API_KEY"},
        "spoonacular_api_key": {"env": "SPOONACULAR_API_KEY"},
        "mongo_uri": {"env": "MONGO_URI"},
        "notify_api_key": {"env": "COBIEN_NOTIFY_API_KEY"},
        "videocall_device_api_key": {"env": "COBIEN_VIDEOCALL_DEVICE_API_KEY"},
    },
}

DEFAULT_UNIFIED_CONFIG = {
    "meta": {
        "schema_version": 1,
        "updated_at": "",
    },
    "settings": {
        "language": "es",
        "weather_cities": ["Bilbao", "Toulouse", "Logroño"],
        "weather_city_catalog": ["Bilbao", "Toulouse", "Logroño"],
        "weather_primary_city": "Bilbao",
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
        "settings_pin": "",
    },
    "services": {
        "mqtt_local_broker": os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost"),
        "mqtt_local_port": int(os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883")),
        "mqtt_backend_broker": os.getenv("COBIEN_MQTT_BACKEND_BROKER", "broker.hivemq.com"),
        "mqtt_backend_port": int(os.getenv("COBIEN_MQTT_BACKEND_PORT", "1883")),
        "mqtt_backend_topic": os.getenv("COBIEN_MQTT_BACKEND_TOPIC", "tarjeta"),
        "mqtt_backend_username": os.getenv("COBIEN_MQTT_BACKEND_USERNAME", ""),
        "mqtt_backend_password": os.getenv("COBIEN_MQTT_BACKEND_PASSWORD", ""),
        "mqtt_backend_use_tls": os.getenv("COBIEN_MQTT_BACKEND_USE_TLS", "0"),
        "mqtt_backend_keepalive_sec": int(os.getenv("COBIEN_MQTT_BACKEND_KEEPALIVE_SEC", "60")),
        "backend_base_url": os.getenv("COBIEN_BACKEND_BASE_URL", "http://portal.co-bien.eu"),
        "owm_api_key": "",
        "news_api_key": "",
        "spoonacular_api_key": "",
        "mongo_uri": "",
        "http_timeout_sec": float(os.getenv("COBIEN_HTTP_TIMEOUT", "8")),
        "tts_engine": os.getenv("COBIEN_TTS_ENGINE", "pyttsx3"),
        "tts_rate": int(os.getenv("COBIEN_TTS_RATE", "155")),
        "tts_volume": float(os.getenv("COBIEN_TTS_VOLUME", "0.85")),
        "tts_piper_bin": os.getenv("COBIEN_TTS_PIPER_BIN", ""),
        "tts_piper_model_es": os.getenv("COBIEN_TTS_PIPER_MODEL_ES", ""),
        "tts_piper_model_fr": os.getenv("COBIEN_TTS_PIPER_MODEL_FR", ""),
        "tts_piper_model_es_male": os.getenv("COBIEN_TTS_PIPER_MODEL_ES_MALE", ""),
        "tts_piper_model_es_female": os.getenv("COBIEN_TTS_PIPER_MODEL_ES_FEMALE", ""),
        "tts_piper_model_fr_male": os.getenv("COBIEN_TTS_PIPER_MODEL_FR_MALE", ""),
        "tts_piper_model_fr_female": os.getenv("COBIEN_TTS_PIPER_MODEL_FR_FEMALE", ""),
        "tts_piper_model_es_male_url": os.getenv("COBIEN_TTS_PIPER_MODEL_ES_MALE_URL", ""),
        "tts_piper_model_es_female_url": os.getenv("COBIEN_TTS_PIPER_MODEL_ES_FEMALE_URL", ""),
        "tts_piper_model_fr_male_url": os.getenv("COBIEN_TTS_PIPER_MODEL_FR_MALE_URL", ""),
        "tts_piper_model_fr_female_url": os.getenv("COBIEN_TTS_PIPER_MODEL_FR_FEMALE_URL", ""),
        "disable_system_sleep": os.getenv("COBIEN_DISABLE_SYSTEM_SLEEP", "0"),
        "notify_api_key": "",
        "videocall_device_api_key": "",
        "pizarra_notify_url": os.getenv("COBIEN_PIZARRA_NOTIFY_URL", "http://portal.co-bien.eu/pizarra/api/notify/"),
        "pizarra_messages_url": os.getenv("COBIEN_PIZARRA_API_URL", "http://portal.co-bien.eu/pizarra/api/messages/"),
        "pizarra_delete_url_template": os.getenv(
            "COBIEN_PIZARRA_DELETE_URL_TEMPLATE",
            "http://portal.co-bien.eu/pizarra/api/messages/{post_id}/delete/",
        ),
        "contacts_api_url": os.getenv("COBIEN_CONTACTS_API_URL", "http://portal.co-bien.eu/pizarra/api/contacts/"),
        "device_heartbeat_url": os.getenv(
            "COBIEN_DEVICE_HEARTBEAT_URL",
            "http://portal.co-bien.eu/pizarra/api/devices/heartbeat/",
        ),
        "device_heartbeat_interval_sec": int(os.getenv("COBIEN_DEVICE_HEARTBEAT_INTERVAL_SEC", "60")),
        "icso_telemetry_url": os.getenv(
            "COBIEN_ICSO_TELEMETRY_URL",
            "http://portal.co-bien.eu/pizarra/api/icso/telemetry/",
        ),
        "icso_events_url": os.getenv(
            "COBIEN_ICSO_EVENTS_URL",
            "http://portal.co-bien.eu/pizarra/api/icso/events/",
        ),
        "portal_videocall_url": os.getenv("COBIEN_PORTAL_VIDEOCALL_URL", "https://portal.co-bien.eu/videocall/"),
        "portal_videocall_device_url": os.getenv("COBIEN_PORTAL_VIDEOCALL_DEVICE_URL", "https://portal.co-bien.eu/videocall/device/"),
        "device_videocall_session_url": os.getenv(
            "COBIEN_DEVICE_VIDEOCALL_SESSION_URL",
            "https://portal.co-bien.eu/api/device-videocall-session/",
        ),
        "portal_call_answered_url": os.getenv(
            "COBIEN_PORTAL_CALL_ANSWERED_URL",
            "https://portal.co-bien.eu/api/call-answered/",
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

DEFAULT_WEATHER_CITIES = ["Bilbao", "Toulouse", "Logroño"]
_INVALID_CITY_PATTERNS = (
    "section",
    "ville par ligne",
    "une ville",
    "villes meteo",
    "ciudades meteorologia",
    "weather cities",
    "one city per line",
)
_CITY_ALLOWED_RE = re.compile(r"^[A-Za-zÀ-ÿ' .-]{2,60}$")


def _normalize_weather_city_name(value):
    city = " ".join(str(value or "").strip().split())
    return city


def _is_valid_weather_city(value):
    city = _normalize_weather_city_name(value)
    if not city:
        return False
    lowered = city.casefold()
    if any(pattern in lowered for pattern in _INVALID_CITY_PATTERNS):
        return False
    if lowered.startswith("#") or lowered.startswith("[") or lowered.startswith("{"):
        return False
    if not _CITY_ALLOWED_RE.match(city):
        return False
    return True


def _sanitize_weather_city_list(values):
    sanitized = []
    seen = set()
    for raw in values or []:
        city = _normalize_weather_city_name(raw)
        if not _is_valid_weather_city(city):
            continue
        key = city.casefold()
        if key in seen:
            continue
        seen.add(key)
        sanitized.append(city)
    return sanitized
def _load_local_config():
    if not os.path.exists(LOCAL_CONFIG_PATH):
        return {}
    try:
        data = _read_json(LOCAL_CONFIG_PATH)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_local_config_overlay(config):
    os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
    _write_json(LOCAL_CONFIG_PATH, config)


def _ensure_nested_dict(root, key):
    current = root.get(key)
    if isinstance(current, dict):
        return current
    root[key] = {}
    return root[key]


def _extract_sensitive_values(config):
    extracted = {}
    for section, keys in SENSITIVE_CONFIG.items():
        section_data = config.get(section)
        if not isinstance(section_data, dict):
            continue
        for key in keys:
            value = section_data.get(key)
            if value in (None, ""):
                continue
            _ensure_nested_dict(extracted, section)[key] = value
    return extracted


def _scrub_sensitive_values(config):
    for section, keys in SENSITIVE_CONFIG.items():
        section_data = config.get(section)
        if not isinstance(section_data, dict):
            continue
        for key in keys:
            section_data[key] = ""
    return config


def _merge_secret_values(base, incoming):
    for section, keys in SENSITIVE_CONFIG.items():
        incoming_section = incoming.get(section)
        if not isinstance(incoming_section, dict):
            continue
        target_section = _ensure_nested_dict(base, section)
        for key in keys:
            value = incoming_section.get(key)
            if value in (None, ""):
                continue
            target_section[key] = value
    return base


def _apply_legacy_local_secrets(config):
    resolved = copy.deepcopy(config)
    local_secrets = _load_legacy_local_secrets()

    for section, keys in SENSITIVE_CONFIG.items():
        target_section = _ensure_nested_dict(resolved, section)
        local_section = local_secrets.get(section, {}) if isinstance(local_secrets.get(section), dict) else {}

        for key, meta in keys.items():
            local_value = str(local_section.get(key, "")).strip()
            if local_value:
                target_section[key] = local_value

    return resolved


def _apply_env_overrides(config):
    resolved = copy.deepcopy(config)

    for section, keys in SENSITIVE_CONFIG.items():
        target_section = _ensure_nested_dict(resolved, section)
        for key, meta in keys.items():
            env_value = os.getenv(meta["env"], "").strip()
            if env_value:
                target_section[key] = env_value

    return resolved


def _persist_extracted_secrets_to_local_config(config):
    extracted = _extract_sensitive_values(config)
    if not extracted:
        return

    local_config = _load_local_config()
    merged = _merge_secret_values(local_config, extracted)
    _save_local_config_overlay(merged)


def _apply_local_config_overlay(config):
    resolved = copy.deepcopy(config)
    resolved = _apply_legacy_local_secrets(resolved)
    local_config = _load_local_config()
    if isinstance(local_config, dict) and local_config:
        _deep_merge_dict(resolved, local_config)
    return resolved
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

    if os.path.exists(LEGACY_UNIFIED_CONFIG_PATH):
        try:
            legacy_unified = _read_json(LEGACY_UNIFIED_CONFIG_PATH)
            if isinstance(legacy_unified, dict):
                _deep_merge_dict(config, legacy_unified)
        except Exception:
            pass

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

    settings = merged["settings"]
    active_cities = _sanitize_weather_city_list(settings.get("weather_cities", []))
    catalog_cities = _sanitize_weather_city_list(settings.get("weather_city_catalog", []))

    if not catalog_cities:
        catalog_cities = list(active_cities)

    if not active_cities:
        active_cities = [city for city in DEFAULT_WEATHER_CITIES if city in catalog_cities] or list(DEFAULT_WEATHER_CITIES)

    if not catalog_cities:
        catalog_cities = list(DEFAULT_WEATHER_CITIES)

    for city in active_cities:
        if city not in catalog_cities:
            catalog_cities.append(city)

    primary_city = _normalize_weather_city_name(settings.get("weather_primary_city", ""))
    if not _is_valid_weather_city(primary_city) or primary_city not in catalog_cities:
        primary_city = active_cities[0] if active_cities else DEFAULT_WEATHER_CITIES[0]

    settings["weather_cities"] = active_cities
    settings["weather_city_catalog"] = catalog_cities
    settings["weather_primary_city"] = primary_city

    merged["meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    if not merged["software"].get("version"):
        merged["software"]["version"] = _read_version_file()
    return merged


def load_config():
    if os.path.exists(LOCAL_CONFIG_PATH):
        try:
            data = _read_json(LOCAL_CONFIG_PATH)
        except Exception:
            data = _build_initial_from_legacy()
    else:
        data = _build_initial_from_legacy()

    normalized = _ensure_schema(data)
    _persist_extracted_secrets_to_local_config(normalized)
    _save_local_config_overlay(normalized)
    return _apply_env_overrides(copy.deepcopy(normalized))


def save_config(config):
    normalized = _ensure_schema(config)
    _persist_extracted_secrets_to_local_config(normalized)
    _save_local_config_overlay(normalized)
    return _apply_env_overrides(copy.deepcopy(normalized))


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
