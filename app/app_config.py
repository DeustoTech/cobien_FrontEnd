"""High-level runtime accessor for furniture settings.

`AppConfig` wraps the unified `settings` section stored in
`app/config/config.local.json` and exposes Kivy bindings for screens that react
to local configuration changes.
"""

from __future__ import annotations

import copy
import os

from kivy.event import EventDispatcher
from kivy.properties import DictProperty

from config_runtime import LOCAL_CONFIG_PATH
from config_store import get_default_section, load_section, save_section


CONFIG_PATH = LOCAL_CONFIG_PATH
_SERVICES_CFG = load_section("services", {})
MQTT_LOCAL_BROKER = _SERVICES_CFG.get("mqtt_local_broker", os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost"))
MQTT_LOCAL_PORT = int(_SERVICES_CFG.get("mqtt_local_port", os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883")))
BACKEND_BASE_URL = _SERVICES_CFG.get("backend_base_url", os.getenv("COBIEN_BACKEND_BASE_URL", "https://portal.co-bien.eu"))
_DEFAULT_SETTINGS = get_default_section("settings", {})


def _default_config() -> dict:
    return copy.deepcopy(_DEFAULT_SETTINGS)


def _runtime_identity_overrides() -> dict:
    device_id = os.getenv("COBIEN_DEVICE_ID", "").strip()
    videocall_room = os.getenv("COBIEN_VIDEOCALL_ROOM", "").strip()

    overrides = {}
    if device_id:
        overrides["device_id"] = device_id
    if videocall_room:
        overrides["videocall_room"] = videocall_room
    elif device_id:
        overrides["videocall_room"] = device_id
    return overrides


class AppConfig(EventDispatcher):
    """Kivy-friendly wrapper around the unified `settings` section."""

    data = DictProperty({})

    def __init__(self):
        super().__init__()
        self.config_path = CONFIG_PATH
        self._last_mtime = None
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self.load()
        self._ensure_device_fields()

    def set_joke_category(self, category):
        self.data["joke_category"] = category
        self.save()

    def get_joke_category(self):
        return self.data.get("joke_category", "general")

    def _ensure_device_fields(self):
        defaults = _default_config()
        modified = False
        for key, default_value in defaults.items():
            if key in self.data:
                continue
            self.data[key] = copy.deepcopy(default_value)
            print(f"[CONFIG] Added missing '{key}' from config.local.json defaults")
            modified = True
        if modified:
            self.save()

    def _apply_runtime_identity(self) -> bool:
        overrides = _runtime_identity_overrides()
        changed = False
        for key, value in overrides.items():
            if self.data.get(key) == value:
                continue
            self.data[key] = value
            changed = True
        return changed

    def load(self):
        try:
            self.data = load_section("settings", _default_config())
            if self._apply_runtime_identity():
                save_section("settings", dict(self.data))
                print(
                    "[CONFIG] Runtime identity synchronized from "
                    "launcher environment"
                )
            if os.path.exists(self.config_path):
                self._last_mtime = os.path.getmtime(self.config_path)
            print(f"[CONFIG] Configuration loaded from {self.config_path}")
        except Exception as e:
            print(f"[CONFIG] Error reading {self.config_path}: {e}")
            self.data = _default_config()
            self._apply_runtime_identity()

    def save(self):
        try:
            self._apply_runtime_identity()
            save_section("settings", dict(self.data))
            if os.path.exists(self.config_path):
                self._last_mtime = os.path.getmtime(self.config_path)
            print(f"[CONFIG] Configuration saved to {self.config_path}")
        except Exception as e:
            print(f"[CONFIG] Error saving {self.config_path}: {e}")

    def get_device_id(self):
        return self.data.get("device_id", "") or ""

    def get_videocall_room(self):
        return self.data.get("videocall_room", self.get_device_id())

    def get_device_location(self):
        return self.data.get("device_location", _default_config().get("device_location", "Bilbao"))

    def get_idle_timeout(self):
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime != self._last_mtime:
                self.load()
        except FileNotFoundError:
            pass
        return self.data.get("idle_timeout_sec", 60)

    def get_microphone_device(self):
        return self.data.get("microphone_device", "")

    def set_microphone_device(self, device_name):
        self.data["microphone_device"] = device_name or ""
        self.save()

    def get_audio_output_device(self):
        return self.data.get("audio_output_device", "")

    def set_audio_output_device(self, device_name):
        self.data["audio_output_device"] = device_name or ""
        self.save()

