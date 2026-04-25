"""Unified configuration access for the furniture runtime.

`config.local.json` is the only local runtime configuration file used by the
application. Humans edit `deploy/ubuntu/cobien.env`; the launcher regenerates
`config.local.json`, and the furniture UI only mutates the subset of values
that are intended to remain device-local.
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime
from typing import Any, Dict

from config_runtime import (
    LEGACY_LOCAL_CONFIG_PATH,
    LOCAL_CONFIG_PATH,
    load_default_unified_config,
    read_version,
)


SENSITIVE_CONFIG = {
    "security": {
        "settings_pin": {"env": "COBIEN_SETTINGS_PIN"},
        "restart_pin": {"env": "COBIEN_RESTART_PIN"},
    },
    "services": {
        "owm_api_key": {"env": "OWM_API_KEY"},
        "news_api_key": {"env": "NEWS_API_KEY"},
        "mongo_uri": {"env": "MONGO_URI"},
        "notify_api_key": {"env": "COBIEN_NOTIFY_API_KEY"},
        "videocall_device_api_key": {"env": "COBIEN_VIDEOCALL_DEVICE_API_KEY"},
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


def _clone_default_config() -> Dict[str, Any]:
    return load_default_unified_config()


def _default_settings() -> Dict[str, Any]:
    return copy.deepcopy(_clone_default_config()["settings"])


def _ensure_nested_dict(root: Dict[str, Any], key: str) -> Dict[str, Any]:
    current = root.get(key)
    if isinstance(current, dict):
        return current
    root[key] = {}
    return root[key]


def _deep_merge_dict(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4, ensure_ascii=False)


def _load_local_config() -> Dict[str, Any]:
    for path in (LOCAL_CONFIG_PATH, LEGACY_LOCAL_CONFIG_PATH):
        if not path or not os.path.exists(path):
            continue
        try:
            return _read_json(path)
        except Exception:
            continue
    return {}


def _extract_sensitive_values(config: Dict[str, Any]) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {}
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


def _merge_secret_values(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
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


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    resolved = copy.deepcopy(config)
    for section, keys in SENSITIVE_CONFIG.items():
        target_section = _ensure_nested_dict(resolved, section)
        for key, meta in keys.items():
            env_value = os.getenv(meta["env"], "").strip()
            if env_value:
                target_section[key] = env_value
    return resolved


def _persist_extracted_secrets_to_local_config(config: Dict[str, Any]) -> None:
    extracted = _extract_sensitive_values(config)
    if not extracted:
        return
    local_config = _load_local_config()
    merged = _merge_secret_values(local_config, extracted)
    _write_json(LOCAL_CONFIG_PATH, merged)


def _normalize_weather_city_name(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _is_valid_weather_city(value: Any) -> bool:
    city = _normalize_weather_city_name(value)
    if not city:
        return False
    lowered = city.casefold()
    if any(pattern in lowered for pattern in _INVALID_CITY_PATTERNS):
        return False
    if lowered.startswith("#") or lowered.startswith("[") or lowered.startswith("{"):
        return False
    return bool(_CITY_ALLOWED_RE.match(city))


def _sanitize_weather_city_list(values: Any) -> list[str]:
    sanitized: list[str] = []
    seen: set[str] = set()
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


def _ensure_schema(data: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = _clone_default_config()
    if isinstance(data, dict):
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
    merged["software"]["version"] = read_version()
    return merged


def get_default_config() -> Dict[str, Any]:
    """Return a copy of the canonical default unified configuration."""
    return _ensure_schema(_clone_default_config())


def get_default_section(section_name: str, default: Any = None) -> Any:
    """Return a copy of one section from the canonical default config."""
    config = get_default_config()
    if section_name in config:
        return copy.deepcopy(config[section_name])
    return copy.deepcopy(default)


def load_config() -> Dict[str, Any]:
    """Load, normalize, persist, and return the active unified config."""
    normalized = _ensure_schema(_load_local_config())
    _persist_extracted_secrets_to_local_config(normalized)
    _write_json(LOCAL_CONFIG_PATH, normalized)
    return _apply_env_overrides(copy.deepcopy(normalized))


def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and persist the active unified config."""
    normalized = _ensure_schema(config)
    _persist_extracted_secrets_to_local_config(normalized)
    _write_json(LOCAL_CONFIG_PATH, normalized)
    return _apply_env_overrides(copy.deepcopy(normalized))


def load_section(section_name: str, default: Any = None) -> Any:
    config = load_config()
    if section_name in config:
        return copy.deepcopy(config[section_name])
    return copy.deepcopy(default)


def save_section(section_name: str, section_data: Any) -> Dict[str, Any]:
    config = load_config()
    config[section_name] = copy.deepcopy(section_data)
    return save_config(config)


def load_services() -> Dict[str, Any]:
    return load_section("services", {})


def get_service(key: str, default: Any = None) -> Any:
    services = load_services()
    return services.get(key, default)
