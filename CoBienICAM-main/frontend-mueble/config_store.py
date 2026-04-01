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
VERSION_PATH = os.path.join(BASE_DIR, "VERSION")

DEFAULT_UNIFIED_CONFIG = {
    "meta": {
        "schema_version": 1,
        "updated_at": "",
    },
    "settings": {
        "language": "es",
        "weather_cities": [],
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
    "software": {
        "version": "",
    },
}


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
