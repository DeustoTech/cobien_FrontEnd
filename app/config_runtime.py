"""Shared runtime configuration metadata for CoBien furniture devices.

This module centralizes the configuration contract used by:
- the Kivy application runtime
- `config_store.py`
- the Ubuntu deployment launcher

It intentionally contains only stdlib-only helpers so the launcher can import
it safely from its embedded Python block.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_DIR = os.path.abspath(
    os.getenv("COBIEN_CONFIG_DIR")
    or os.path.dirname(os.getenv("COBIEN_LOCAL_CONFIG_PATH", ""))
    or APP_CONFIG_DIR
)
DEFAULT_CONFIG_PATH = os.path.join(APP_CONFIG_DIR, "config.default.json")
LOCAL_CONFIG_PATH = os.path.abspath(
    os.getenv("COBIEN_LOCAL_CONFIG_PATH")
    or os.path.join(CONFIG_DIR, "config.local.json")
)
LEGACY_LOCAL_CONFIG_PATH = os.path.join(APP_CONFIG_DIR, "config.local.json")
LOCAL_CONFIG_EXAMPLE_PATH = os.path.join(APP_CONFIG_DIR, "config.local.example.json")
VERSION_PATH = os.path.join(BASE_DIR, "VERSION")

DEPLOYMENT_ENV_PRIMARY_FILE = "deploy/ubuntu/cobien.env"
DEPLOYMENT_ENV_RUNTIME_FILE = "deploy/ubuntu/cobien-update.env"

# These keys are seeded from `cobien.env` on the first furniture boot, but once
# the device user changes them from the admin UI they remain local state and
# should not be overwritten on each restart/update.
PRESERVED_LOCAL_CONFIG_KEYS: Dict[str, list[str]] = {
    "settings": [
        "weather_cities",
        "weather_city_catalog",
        "weather_primary_city",
        "button_colors",
        "rfid_actions",
        "microphone_device",
        "audio_output_device",
        "joke_category",
        "idle_timeout_sec",
    ],
    "notifications": [
        "videollamada",
        "nuevo_evento",
        "nueva_foto",
    ],
}

# These sections are fully driven by deployment/runtime configuration rather
# than being edited from the furniture UI.
FORCED_CONFIG_SECTIONS: tuple[str, ...] = (
    "meta",
    "security",
    "services",
    "software",
)


def load_default_unified_config() -> Dict[str, Any]:
    """Return a deep copy of the canonical config schema/defaults."""
    with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("config.default.json must contain a JSON object")
    return copy.deepcopy(data)


def read_version() -> str:
    """Return the current software version string, or an empty value."""
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""
