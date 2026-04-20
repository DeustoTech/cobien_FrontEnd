"""Comprehensive administration screen for launcher and unified config.

This screen exposes launcher environment values plus every field from the
unified local configuration file. Complex values are edited as JSON and the
content is hosted inside a scroll view to remain usable on furniture devices.
"""

import json
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput

from config_store import load_config, load_section, save_config
from translation import _


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<LauncherConfigScreen>:
"""


DEFAULT_PIPER_MODEL_ES_MALE = "es_ES-davefx-medium"
DEFAULT_PIPER_MODEL_ES_FEMALE = "es_ES-mls_10246-low"
DEFAULT_PIPER_MODEL_FR_MALE = "fr_FR-mls_1840-low"
DEFAULT_PIPER_MODEL_FR_FEMALE = "fr_FR-siwis-medium"
DEFAULT_PIPER_MODEL_ES_MALE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"
DEFAULT_PIPER_MODEL_ES_FEMALE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/mls_10246/low/es_ES-mls_10246-low.onnx"
DEFAULT_PIPER_MODEL_FR_MALE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/mls_1840/low/fr_FR-mls_1840-low.onnx"
DEFAULT_PIPER_MODEL_FR_FEMALE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"

LAUNCHER_GROUPS = [
    (
        "Identidad del mueble",
        [
            ("COBIEN_APP_LANGUAGE", "Idioma app", "choice:es,fr", "es"),
            ("COBIEN_DEVICE_ID", "Device ID", "text", "CoBien1"),
            ("COBIEN_VIDEOCALL_ROOM", "Videocall room", "text", "CoBien1"),
            ("COBIEN_DEVICE_LOCATION", "Ubicación del mueble", "text", "Bilbao"),
        ],
    ),
    (
        "Runtime y actualizaciones",
        [
            ("COBIEN_WORKSPACE_ROOT", "Workspace", "path", os.path.join(os.path.expanduser("~"), "cobien")),
            ("COBIEN_FRONTEND_REPO_NAME", "Frontend repo", "text", "cobien_FrontEnd"),
            ("COBIEN_MQTT_REPO_NAME", "MQTT/CAN repo", "text", "cobien_MQTT_Dictionnary"),
            ("COBIEN_UPDATE_BRANCH", "Git branch", "text", "development_fix"),
            ("COBIEN_UPDATE_REMOTE", "Git remote", "text", "origin"),
            ("COBIEN_UPDATE_INTERVAL_SEC", "Intervalo de update/watch (seg)", "int", "60"),
            ("COBIEN_HARDWARE_MODE", "Hardware mode", "choice:auto,real,mock", "auto"),
        ],
    ),
    (
        "Conectividad backend",
        [
            ("COBIEN_NOTIFY_API_KEY", "Notify API key", "secret", ""),
            ("COBIEN_VIDEOCALL_DEVICE_API_KEY", "Videocall device API key", "secret", ""),
            ("COBIEN_DEVICE_HEARTBEAT_URL", "Heartbeat URL", "text", "https://portal.co-bien.eu/pizarra/api/devices/heartbeat/"),
        ],
    ),
    (
        "Texto a voz",
        [
            ("COBIEN_TTS_ENGINE", "Motor TTS activo", "choice:pyttsx3,piper", "pyttsx3"),
        ],
    ),
]

LAUNCHER_FIELDS = [field for _group_name, fields in LAUNCHER_GROUPS for field in fields]
CONFIG_SECTION_TITLES = {
    "settings": "Ajustes de usuario y dispositivo",
    "notifications": "Notificaciones",
    "security": "Seguridad",
    "services": "Servicios y APIs",
    "software": "Software",
}
SKIP_CONFIG_FIELDS = {
    ("settings", "language"),
    ("settings", "device_id"),
    ("settings", "videocall_room"),
    ("settings", "device_location"),
    ("services", "notify_api_key"),
    ("services", "device_heartbeat_url"),
}

CONFIG_FIELD_METADATA = {
    ("settings", "language"): {"label": "Idioma", "kind": "choice:es,fr", "help": "Idioma principal de la interfaz del mueble."},
    ("settings", "device_id"): {"label": "Device ID", "help": "Identificador único del mueble en backend, MQTT y sincronizaciones."},
    ("settings", "videocall_room"): {"label": "Sala videollamada", "help": "Sala que usará el mueble para entrar automáticamente en videollamadas."},
    ("settings", "device_location"): {"label": "Ubicación", "help": "Ciudad o ubicación física usada por varias funciones del sistema."},
    ("settings", "microphone_device"): {"label": "Micrófono", "help": "Nombre del dispositivo de entrada preferido para voz."},
    ("settings", "weather_primary_city"): {"label": "Ciudad meteorología principal", "help": "Ciudad activa que se mostrará por defecto."},
    ("settings", "weather_cities"): {"label": "Ciudades meteorología", "help": "Listado de ciudades disponibles para el tiempo."},
    ("settings", "weather_city_catalog"): {"label": "Catálogo ciudades meteorología", "help": "Catálogo maestro usado para selección de ciudades."},
    ("settings", "button_colors"): {"label": "Colores de botones", "help": "Mapa de colores personalizado para botones de interfaz."},
    ("settings", "rfid_actions"): {"label": "Acciones RFID", "help": "Acciones configuradas para las tarjetas RFID."},
    ("settings", "joke_category"): {"label": "Categoría de frases", "help": "Categoría activa para frases o bromas del sistema."},
    ("settings", "idle_timeout_sec"): {"label": "Timeout inactividad (seg)", "help": "Tiempo antes de volver al estado principal por inactividad."},
    ("security", "settings_pin"): {"label": "PIN administración", "help": "PIN necesario para acceder a la administración."},
    ("services", "backend_base_url"): {"label": "Backend base URL", "help": "URL base del portal web y backend principal."},
    ("services", "notify_api_key"): {"label": "Notify API key", "help": "Clave usada para avisos y llamadas desde/hacia backend."},
    ("services", "videocall_device_api_key"): {"label": "Videocall device API key", "help": "Clave del mueble para entrar en videollamada sin login humano."},
    ("services", "device_videocall_session_url"): {"label": "Videocall session URL", "help": "Endpoint backend que devuelve el token Twilio del mueble."},
    ("services", "portal_videocall_device_url"): {"label": "Portal videocall device URL", "help": "Página web específica de videollamada para dispositivos."},
    ("services", "portal_call_answered_url"): {"label": "Call answered URL", "help": "Endpoint al que el mueble avisa cuando la llamada ha sido aceptada."},
    ("services", "pizarra_notify_url"): {"label": "Pizarra notify URL", "help": "Endpoint para notificaciones del mueble hacia la web."},
    ("services", "pizarra_messages_url"): {"label": "Pizarra messages URL", "help": "Endpoint para cargar mensajes desde el backend."},
    ("services", "pizarra_delete_url_template"): {"label": "Pizarra delete URL", "help": "Plantilla de borrado de mensajes usando {post_id}."},
    ("services", "contacts_api_url"): {"label": "Contacts API URL", "help": "Endpoint para sincronización de contactos del mueble."},
    ("services", "device_heartbeat_url"): {"label": "Heartbeat URL", "help": "Endpoint donde el mueble publica su latido operativo."},
    ("services", "device_heartbeat_interval_sec"): {"label": "Heartbeat interval (seg)", "help": "Frecuencia con la que el mueble reporta que sigue vivo."},
    ("services", "icso_telemetry_url"): {"label": "ICSO telemetry URL", "help": "Endpoint de envío de telemetría ICSO."},
    ("services", "icso_events_url"): {"label": "ICSO events URL", "help": "Endpoint de eventos ICSO."},
    ("services", "mqtt_local_broker"): {"label": "MQTT local broker", "help": "Broker MQTT local usado dentro del mueble."},
    ("services", "mqtt_local_port"): {"label": "MQTT local port", "help": "Puerto del broker MQTT local."},
    ("services", "mqtt_backend_broker"): {"label": "MQTT backend broker", "help": "Broker MQTT remoto/backend."},
    ("services", "mqtt_backend_port"): {"label": "MQTT backend port", "help": "Puerto del broker MQTT backend."},
    ("services", "http_timeout_sec"): {"label": "HTTP timeout (seg)", "help": "Timeout general de peticiones HTTP."},
    ("services", "tts_engine"): {"label": "Motor TTS", "kind": "choice:pyttsx3,piper", "help": "Motor de texto a voz activo."},
    ("services", "tts_rate"): {"label": "Velocidad TTS", "help": "Velocidad de lectura de voz."},
    ("services", "tts_volume"): {"label": "Volumen TTS", "help": "Volumen base de la voz sintetizada."},
    ("services", "tts_piper_bin"): {"label": "Binario Piper", "help": "Ruta al ejecutable Piper si se usa TTS Piper."},
    ("services", "tts_piper_voice_es"): {"label": "Voz Piper ES", "kind": "choice:male,female", "help": "Perfil de voz Piper para español."},
    ("services", "tts_piper_voice_fr"): {"label": "Voz Piper FR", "kind": "choice:male,female", "help": "Perfil de voz Piper para francés."},
    ("services", "disable_system_sleep"): {"label": "Desactivar suspensión", "kind": "choice:0,1", "help": "Evita que el sistema entre en suspensión automática."},
    ("services", "mongo_uri"): {"label": "Mongo URI", "help": "Cadena de conexión a MongoDB."},
    ("services", "owm_api_key"): {"label": "OpenWeather API key", "help": "Clave del proveedor meteorológico OpenWeather."},
    ("services", "news_api_key"): {"label": "News API key", "help": "Clave del proveedor de noticias."},
    ("services", "spoonacular_api_key"): {"label": "Spoonacular API key", "help": "Clave del proveedor de recetas."},
    ("software", "version"): {"label": "Versión software", "help": "Versión local mostrada en administración."},
}

CONFIG_GROUPS = [
    (
        "Identidad y experiencia",
        "Parámetros que definen el mueble y su comportamiento visible diario.",
        [
            ("settings", "language"),
            ("settings", "device_id"),
            ("settings", "videocall_room"),
            ("settings", "device_location"),
            ("settings", "microphone_device"),
            ("settings", "idle_timeout_sec"),
            ("settings", "weather_primary_city"),
            ("settings", "weather_cities"),
            ("settings", "weather_city_catalog"),
            ("settings", "joke_category"),
            ("settings", "button_colors"),
            ("settings", "rfid_actions"),
        ],
    ),
    (
        "Videollamada y backend",
        "Todo lo necesario para que el mueble se conecte con el portal y pueda entrar en llamada automáticamente.",
        [
            ("services", "backend_base_url"),
            ("services", "notify_api_key"),
            ("services", "videocall_device_api_key"),
            ("services", "pizarra_notify_url"),
            ("services", "pizarra_messages_url"),
            ("services", "pizarra_delete_url_template"),
            ("services", "contacts_api_url"),
            ("services", "device_heartbeat_url"),
            ("services", "device_heartbeat_interval_sec"),
            ("services", "portal_videocall_url"),
            ("services", "portal_videocall_device_url"),
            ("services", "device_videocall_session_url"),
            ("services", "portal_call_answered_url"),
            ("services", "icso_telemetry_url"),
            ("services", "icso_events_url"),
        ],
    ),
    (
        "Conectividad y voz",
        "Parámetros técnicos de MQTT, TTS y servicios auxiliares.",
        [
            ("services", "mqtt_local_broker"),
            ("services", "mqtt_local_port"),
            ("services", "mqtt_backend_broker"),
            ("services", "mqtt_backend_port"),
            ("services", "http_timeout_sec"),
            ("services", "tts_engine"),
            ("services", "tts_rate"),
            ("services", "tts_volume"),
            ("services", "tts_piper_bin"),
            ("services", "tts_piper_voice_es"),
            ("services", "tts_piper_voice_fr"),
            ("services", "tts_piper_model_es"),
            ("services", "tts_piper_model_fr"),
            ("services", "tts_piper_model_es_male"),
            ("services", "tts_piper_model_es_female"),
            ("services", "tts_piper_model_fr_male"),
            ("services", "tts_piper_model_fr_female"),
            ("services", "tts_piper_model_es_url"),
            ("services", "tts_piper_model_fr_url"),
            ("services", "tts_piper_model_es_male_url"),
            ("services", "tts_piper_model_es_female_url"),
            ("services", "tts_piper_model_fr_male_url"),
            ("services", "tts_piper_model_fr_female_url"),
            ("services", "disable_system_sleep"),
        ],
    ),
    (
        "Seguridad y sistema",
        "Credenciales sensibles y metadatos locales del software.",
        [
            ("security", "settings_pin"),
            ("services", "mongo_uri"),
            ("services", "owm_api_key"),
            ("services", "news_api_key"),
            ("services", "spoonacular_api_key"),
            ("software", "version"),
        ],
    ),
]


class LauncherConfigScreen(Screen):
    """Screen used to edit launcher env values and the full unified config."""

    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        if not hasattr(LauncherConfigScreen, "_kv_loaded"):
            Builder.load_string(KV)
            LauncherConfigScreen._kv_loaded = True
        self._launcher_inputs: Dict[str, Any] = {}
        self._config_inputs: Dict[Tuple[str, str], Any] = {}
        self._config_types: Dict[Tuple[str, str], str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(18))
        with root.canvas.before:
            Color(0.96, 0.97, 0.98, 1)
            self._root_bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(24)])
        root.bind(pos=lambda instance, _value: setattr(self._root_bg, "pos", instance.pos))
        root.bind(size=lambda instance, _value: setattr(self._root_bg, "size", instance.size))
        self.add_widget(root)

        header = BoxLayout(size_hint_y=None, height=dp(92), spacing=dp(14))
        with header.canvas.before:
            Color(1, 1, 1, 0.98)
            self._header_bg = RoundedRectangle(pos=header.pos, size=header.size, radius=[dp(20)])
        header.bind(pos=lambda instance, _value: setattr(self._header_bg, "pos", instance.pos))
        header.bind(size=lambda instance, _value: setattr(self._header_bg, "size", instance.size))
        title = Label(
            text=_("Administración del mueble"),
            font_size=sp(34),
            bold=True,
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        back_btn = Button(
            text=_("Volver"),
            size_hint=(None, None),
            size=(dp(140), dp(74)),
            background_normal="",
            background_color=(0.88, 0.9, 0.94, 1),
            font_size=sp(24),
            color=(0.08, 0.1, 0.14, 1),
        )
        back_btn.bind(on_release=lambda *_args: self.go_back())
        header.add_widget(title)
        header.add_widget(back_btn)
        root.add_widget(header)

        self.tabs = TabbedPanel(do_default_tab=False, tab_width=dp(220))
        self.tabs.background_color = (0.94, 0.95, 0.97, 1)
        self.tabs.tab_height = dp(58)
        root.add_widget(self.tabs)

        form_tab = TabbedPanelItem(text=_("Campos"))
        raw_config_tab = TabbedPanelItem(text=_("JSON completo"))
        raw_env_tab = TabbedPanelItem(text=_("Parámetros texto"))
        for tab in (form_tab, raw_config_tab, raw_env_tab):
            tab.background_normal = ""
            tab.background_down = ""
            tab.background_disabled_normal = ""
            tab.background_disabled_down = ""
            tab.background_color = (0.9, 0.93, 0.97, 1)
            tab.color = (0.1, 0.12, 0.16, 1)
        self.tabs.add_widget(form_tab)
        self.tabs.add_widget(raw_config_tab)
        self.tabs.add_widget(raw_env_tab)
        self.tabs.default_tab = form_tab

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True, bar_width=dp(12))
        form_tab.add_widget(scroll)

        self.form = BoxLayout(
            orientation="vertical",
            spacing=dp(18),
            size_hint_y=None,
            padding=(dp(8), dp(8), dp(8), dp(24)),
        )
        with self.form.canvas.before:
            Color(1, 1, 1, 0.98)
            self._form_bg = RoundedRectangle(pos=self.form.pos, size=self.form.size, radius=[dp(20)])
        self.form.bind(pos=lambda instance, _value: setattr(self._form_bg, "pos", instance.pos))
        self.form.bind(size=lambda instance, _value: setattr(self._form_bg, "size", instance.size))
        self.form.bind(minimum_height=self.form.setter("height"))
        scroll.add_widget(self.form)

        self._build_launcher_section()
        self._build_config_section()
        self._build_raw_tabs(raw_config_tab, raw_env_tab)

        self.lbl_status = Label(
            text="",
            size_hint_y=None,
            height=dp(54),
            font_size=sp(18),
            color=(0.1, 0.1, 0.1, 0.8),
            halign="left",
            valign="middle",
        )
        self.lbl_status.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        root.add_widget(self.lbl_status)

        actions = BoxLayout(size_hint_y=None, height=dp(66), spacing=dp(14))
        save_btn = Button(
            text=_("Guardar configuración"),
            background_normal="",
            background_color=(0.23, 0.67, 0.33, 1),
            font_size=sp(24),
            color=(1, 1, 1, 1),
        )
        reload_btn = Button(
            text=_("Actualizar y recargar ahora"),
            background_normal="",
            background_color=(0.24, 0.48, 0.86, 1),
            font_size=sp(22),
            color=(1, 1, 1, 1),
        )
        save_btn.bind(on_release=lambda *_args: self.save_changes())
        reload_btn.bind(on_release=lambda *_args: self.run_full_update_reload())
        actions.add_widget(save_btn)
        actions.add_widget(reload_btn)
        root.add_widget(actions)

    def _section_title(self, text: str) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(40),
            font_size=sp(28),
            bold=True,
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        return label

    def _field_label(self, text: str) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(34),
            font_size=sp(20),
            color=(0, 0, 0, 0.9),
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        return label

    def _field_help(self, text: str) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(30),
            font_size=sp(15),
            color=(0.22, 0.25, 0.31, 0.78),
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        return label

    def _field_height(self, kind: str) -> int:
        return dp(56) if kind in {"text", "int", "float", "bool", "secret", "path"} or kind.startswith("choice:") else dp(180)

    def _build_input(self, kind: str, value: str):
        if kind.startswith("choice:"):
            values = tuple(item.strip() for item in kind.split(":", 1)[1].split(",") if item.strip())
            widget = Spinner(
                text=value or (values[0] if values else ""),
                values=values,
                size_hint_y=None,
                height=self._field_height(kind),
                font_size=sp(18),
                background_normal="",
                background_color=(0.97, 0.98, 0.99, 1),
                color=(0.08, 0.1, 0.14, 1),
                sync_height=True,
            )
            return widget
        widget = TextInput(
            text=value,
            multiline=kind in {"json", "list", "dict"},
            password=kind == "secret",
            size_hint_y=None,
            height=self._field_height(kind),
            font_size=sp(18),
            hint_text="JSON" if kind in {"json", "list", "dict"} else "",
            background_normal="",
            background_active="",
            background_color=(0.98, 0.99, 1, 1),
            foreground_color=(0.08, 0.1, 0.14, 1),
            hint_text_color=(0.45, 0.49, 0.56, 1),
            cursor_color=(0.16, 0.35, 0.78, 1),
        )
        return widget

    def _build_launcher_section(self) -> None:
        self.form.add_widget(self._section_title(_("Parámetros del launcher")))
        for group_name, fields in LAUNCHER_GROUPS:
            self.form.add_widget(self._section_title(_(group_name)))
            for key, label_text, kind, default in fields:
                self.form.add_widget(self._field_label(label_text))
                widget = self._build_input(kind, "")
                self._launcher_inputs[key] = widget
                self.form.add_widget(widget)
                if key == "COBIEN_VIDEOCALL_DEVICE_API_KEY":
                    self.form.add_widget(self._field_help(_("Clave del mueble para entrar en videollamada sin pedir usuario y contraseña.")))
                elif key == "COBIEN_NOTIFY_API_KEY":
                    self.form.add_widget(self._field_help(_("Clave general para notificaciones seguras entre mueble y backend.")))
                elif key == "COBIEN_DEVICE_ID":
                    self.form.add_widget(self._field_help(_("Identificador único del mueble. Debe coincidir con el configurado en backend.")))
                elif key == "COBIEN_VIDEOCALL_ROOM":
                    self.form.add_widget(self._field_help(_("Sala de videollamada que usará el mueble por defecto.")))
                elif key == "COBIEN_DEVICE_HEARTBEAT_URL":
                    self.form.add_widget(self._field_help(_("Endpoint al que el mueble reporta periódicamente que sigue operativo.")))

        self.extra_env_title = self._section_title(_("Variables extra del launcher"))
        self.form.add_widget(self.extra_env_title)
        self.extra_env_input = TextInput(
            text="",
            multiline=True,
            size_hint_y=None,
            height=dp(220),
            font_size=sp(18),
            hint_text="KEY=value",
        )
        self.form.add_widget(self.extra_env_input)

    def _build_config_section(self) -> None:
        self.form.add_widget(self._section_title(_("Configuración local del mueble")))
        full_config = load_config()
        rendered = set()

        for group_title, group_help, fields in CONFIG_GROUPS:
            self.form.add_widget(self._section_title(_(group_title)))
            self.form.add_widget(self._field_help(_(group_help)))
            for section_name, key in fields:
                if (section_name, key) in SKIP_CONFIG_FIELDS:
                    continue
                value = (full_config.get(section_name, {}) or {}).get(key)
                meta = CONFIG_FIELD_METADATA.get((section_name, key), {})
                kind, text_value = self._serialize_config_value(section_name, key, value)
                if meta.get("kind"):
                    kind = meta["kind"]
                self.form.add_widget(self._field_label(meta.get("label", f"{section_name}.{key}")))
                widget = self._build_input(kind, text_value)
                self._config_inputs[(section_name, key)] = widget
                self._config_types[(section_name, key)] = kind
                self.form.add_widget(widget)
                if meta.get("help"):
                    self.form.add_widget(self._field_help(_(meta["help"])))
                rendered.add((section_name, key))

        for section_name in ("settings", "notifications", "security", "services", "software"):
            section = full_config.get(section_name, {}) or {}
            remaining_keys = [key for key in sorted(section.keys()) if (section_name, key) not in rendered and (section_name, key) not in SKIP_CONFIG_FIELDS]
            if not remaining_keys:
                continue
            self.form.add_widget(self._section_title(_(f"Otros parámetros: {CONFIG_SECTION_TITLES.get(section_name, section_name)}")))
            for key in remaining_keys:
                value = section.get(key)
                meta = CONFIG_FIELD_METADATA.get((section_name, key), {})
                kind, text_value = self._serialize_config_value(section_name, key, value)
                if meta.get("kind"):
                    kind = meta["kind"]
                self.form.add_widget(self._field_label(meta.get("label", f"{section_name}.{key}")))
                widget = self._build_input(kind, text_value)
                self._config_inputs[(section_name, key)] = widget
                self._config_types[(section_name, key)] = kind
                self.form.add_widget(widget)
                if meta.get("help"):
                    self.form.add_widget(self._field_help(_(meta["help"])))

    def _build_raw_tabs(self, raw_config_tab: TabbedPanelItem, raw_env_tab: TabbedPanelItem) -> None:
        raw_config_box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        with raw_config_box.canvas.before:
            Color(1, 1, 1, 0.98)
            self._raw_config_bg = RoundedRectangle(pos=raw_config_box.pos, size=raw_config_box.size, radius=[dp(20)])
        raw_config_box.bind(pos=lambda instance, _value: setattr(self._raw_config_bg, "pos", instance.pos))
        raw_config_box.bind(size=lambda instance, _value: setattr(self._raw_config_bg, "size", instance.size))
        raw_config_tab.add_widget(raw_config_box)
        raw_config_box.add_widget(self._field_label(_("JSON completo de configuración local")))
        self.raw_config_input = TextInput(
            text="",
            multiline=True,
            font_size=sp(18),
            hint_text="{ ... }",
            background_normal="",
            background_active="",
            background_color=(0.98, 0.99, 1, 1),
            foreground_color=(0.08, 0.1, 0.14, 1),
            hint_text_color=(0.45, 0.49, 0.56, 1),
            cursor_color=(0.16, 0.35, 0.78, 1),
        )
        raw_config_box.add_widget(self.raw_config_input)

        raw_env_box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        with raw_env_box.canvas.before:
            Color(1, 1, 1, 0.98)
            self._raw_env_bg = RoundedRectangle(pos=raw_env_box.pos, size=raw_env_box.size, radius=[dp(20)])
        raw_env_box.bind(pos=lambda instance, _value: setattr(self._raw_env_bg, "pos", instance.pos))
        raw_env_box.bind(size=lambda instance, _value: setattr(self._raw_env_bg, "size", instance.size))
        raw_env_tab.add_widget(raw_env_box)
        raw_env_box.add_widget(self._field_label(_("Parámetros completos del launcher en texto plano")))
        self.raw_env_input = TextInput(
            text="",
            multiline=True,
            font_size=sp(18),
            hint_text="KEY=value",
            background_normal="",
            background_active="",
            background_color=(0.98, 0.99, 1, 1),
            foreground_color=(0.08, 0.1, 0.14, 1),
            hint_text_color=(0.45, 0.49, 0.56, 1),
            cursor_color=(0.16, 0.35, 0.78, 1),
        )
        raw_env_box.add_widget(self.raw_env_input)

    def _serialize_config_value(self, section_name: str, key: str, value: Any):
        meta = CONFIG_FIELD_METADATA.get((section_name, key), {})
        if meta.get("kind"):
            kind = meta["kind"]
            if kind in {"choice:0,1", "choice:es,fr", "choice:pyttsx3,piper", "choice:male,female"}:
                return kind, str(value or "").strip()
        if isinstance(value, bool):
            return "choice:true,false", "true" if value else "false"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int", str(value)
        if isinstance(value, float):
            return "float", str(value)
        if isinstance(value, dict):
            return "dict", json.dumps(value, ensure_ascii=False, indent=2)
        if isinstance(value, list):
            return "list", json.dumps(value, ensure_ascii=False, indent=2)
        if section_name == "security" or key.endswith("_key") or "password" in key.lower() or "token" in key.lower():
            return "secret", str(value or "")
        return "text", str(value or "")

    def _normalized_runtime_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = json.loads(json.dumps(config))
        services = normalized.setdefault("services", {})
        settings = normalized.setdefault("settings", {})

        if not settings.get("videocall_room"):
            settings["videocall_room"] = settings.get("device_id", "CoBien1")
        if not settings.get("device_id"):
            settings["device_id"] = "CoBien1"
        if not settings.get("language"):
            settings["language"] = "es"

        models_dir = os.path.join(os.path.dirname(__file__), "..", "models", "piper")
        models_dir = os.path.abspath(models_dir)
        default_paths = {
            "tts_piper_model_es_male": os.path.join(models_dir, f"{DEFAULT_PIPER_MODEL_ES_MALE}.onnx"),
            "tts_piper_model_es_female": os.path.join(models_dir, f"{DEFAULT_PIPER_MODEL_ES_FEMALE}.onnx"),
            "tts_piper_model_fr_male": os.path.join(models_dir, f"{DEFAULT_PIPER_MODEL_FR_MALE}.onnx"),
            "tts_piper_model_fr_female": os.path.join(models_dir, f"{DEFAULT_PIPER_MODEL_FR_FEMALE}.onnx"),
        }
        default_urls = {
            "tts_piper_model_es_male_url": DEFAULT_PIPER_MODEL_ES_MALE_URL,
            "tts_piper_model_es_female_url": DEFAULT_PIPER_MODEL_ES_FEMALE_URL,
            "tts_piper_model_fr_male_url": DEFAULT_PIPER_MODEL_FR_MALE_URL,
            "tts_piper_model_fr_female_url": DEFAULT_PIPER_MODEL_FR_FEMALE_URL,
        }

        for key, value in default_paths.items():
            if not services.get(key):
                services[key] = value
        for key, value in default_urls.items():
            if not services.get(key):
                services[key] = value

        if not services.get("tts_piper_voice_es"):
            services["tts_piper_voice_es"] = "male"
        if not services.get("tts_piper_voice_fr"):
            services["tts_piper_voice_fr"] = "male"
        if not services.get("tts_piper_model_es"):
            services["tts_piper_model_es"] = services["tts_piper_model_es_male"]
        if not services.get("tts_piper_model_fr"):
            services["tts_piper_model_fr"] = services["tts_piper_model_fr_male"]
        if not services.get("tts_piper_model_es_url"):
            services["tts_piper_model_es_url"] = services["tts_piper_model_es_male_url"]
        if not services.get("tts_piper_model_fr_url"):
            services["tts_piper_model_fr_url"] = services["tts_piper_model_fr_male_url"]
        return normalized

    def _parse_value(self, kind: str, raw_value: str):
        text = str(raw_value or "").strip()
        if kind == "bool":
            return text.lower() in {"1", "true", "yes", "si", "sí", "on"}
        if kind == "int":
            return int(text or "0")
        if kind == "float":
            return float(text or "0")
        if kind in {"dict", "list"}:
            if not text:
                return {} if kind == "dict" else []
            value = json.loads(text)
            if kind == "dict" and not isinstance(value, dict):
                raise ValueError(_("Debe ser un objeto JSON"))
            if kind == "list" and not isinstance(value, list):
                raise ValueError(_("Debe ser una lista JSON"))
            return value
        return raw_value

    def _env_path(self) -> str:
        env_from_var = os.getenv("COBIEN_UPDATE_ENV_FILE", "").strip()
        if env_from_var:
            return env_from_var
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "ubuntu", "cobien-update.env")
        )

    def _read_env(self) -> Dict[str, str]:
        values = {}
        path = self._env_path()
        if not os.path.exists(path):
            return values
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as file_obj:
                for line in file_obj:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            pass
        return values

    def _write_env(self, data: Dict[str, str]) -> None:
        def _quote_env(value: str) -> str:
            text = str(value or "")
            text = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{text}"'

        path = self._env_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file_obj:
            for key in sorted(data.keys()):
                file_obj.write(f"{key}={_quote_env(data[key])}\n")

    def _load_extra_env_text(self, env: Dict[str, str]) -> str:
        known_keys = {key for key, *_rest in LAUNCHER_FIELDS}
        lines = []
        for key in sorted(env.keys()):
            if key in known_keys:
                continue
            if not key.startswith("COBIEN_"):
                continue
            lines.append(f"{key}={env[key]}")
        return "\n".join(lines)

    def _parse_extra_env_text(self) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for line in str(self.extra_env_input.text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(_("Cada línea extra debe tener formato KEY=value"))
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(_("Las variables extra necesitan una clave"))
            parsed[key] = value.strip()
        return parsed

    def go_back(self) -> None:
        self.sm.current = "settings"

    def load_values(self) -> None:
        env = self._read_env()
        runtime_cfg = self._normalized_runtime_config(load_config())

        for key, _label, _kind, default in LAUNCHER_FIELDS:
            widget = self._launcher_inputs[key]
            value = env.get(key, default)
            widget.text = value

        self.extra_env_input.text = self._load_extra_env_text(env)

        for (section_name, key), widget in self._config_inputs.items():
            current_value = runtime_cfg.get(section_name, {}).get(key)
            kind, text_value = self._serialize_config_value(section_name, key, current_value)
            self._config_types[(section_name, key)] = kind
            widget.text = text_value

        self.raw_config_input.text = json.dumps(runtime_cfg, ensure_ascii=False, indent=4)
        self.raw_env_input.text = "\n".join(f"{key}={env[key]}" for key in sorted(env.keys()))

        self.lbl_status.text = f"{_('Configuración cargada desde')}: {self._env_path()}"

    def save_changes(self) -> None:
        try:
            env = self._read_env()
            raw_env_text = str(self.raw_env_input.text or "").strip()
            if raw_env_text:
                raw_env: Dict[str, str] = {}
                for line in raw_env_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        raise ValueError(_("Cada línea del texto plano debe tener formato KEY=value"))
                    key, value = line.split("=", 1)
                    raw_env[key.strip()] = value.strip()
                env = raw_env

            for key, _label, _kind, default in LAUNCHER_FIELDS:
                widget = self._launcher_inputs[key]
                env[key] = (widget.text or default or "").strip()

            known_launcher_keys = {key for key, *_rest in LAUNCHER_FIELDS}
            for key in list(env.keys()):
                if key.startswith("COBIEN_") and key not in known_launcher_keys:
                    env.pop(key, None)
            env.update(self._parse_extra_env_text())
            self._write_env(env)

            raw_config_text = str(self.raw_config_input.text or "").strip()
            if raw_config_text:
                config = json.loads(raw_config_text)
                if not isinstance(config, dict):
                    raise ValueError(_("El JSON completo debe ser un objeto"))
            else:
                config = self._normalized_runtime_config(load_config())

            for (section_name, key), widget in self._config_inputs.items():
                kind = self._config_types[(section_name, key)]
                config.setdefault(section_name, {})
                config[section_name][key] = self._parse_value(kind, widget.text)

            config = self._normalized_runtime_config(config)
            save_config(config)

            self.cfg.data["language"] = config.get("settings", {}).get("language", self.cfg.data.get("language", "es"))
            self.cfg.data["device_id"] = config.get("settings", {}).get("device_id", self.cfg.data.get("device_id", "CoBien1"))
            self.cfg.data["videocall_room"] = config.get("settings", {}).get("videocall_room", self.cfg.data.get("videocall_room", "CoBien1"))
            self.cfg.data["device_location"] = config.get("settings", {}).get("device_location", self.cfg.data.get("device_location", "Bilbao"))
            self.cfg.save()

            app = App.get_running_app()
            if app and hasattr(app, "main_ref") and app.main_ref:
                app.main_ref.DEVICE_ID = self.cfg.get_device_id()
                app.main_ref.VIDEOCALL_ROOM = self.cfg.get_videocall_room()
                app.main_ref.DEVICE_LOCATION = self.cfg.get_device_location()

            self.lbl_status.text = f"{_('Configuración guardada en')}: {self._env_path()}"
            self.raw_config_input.text = json.dumps(self._normalized_runtime_config(load_config()), ensure_ascii=False, indent=4)
            saved_env = self._read_env()
            self.raw_env_input.text = "\n".join(f"{key}={saved_env[key]}" for key in sorted(saved_env.keys()))
        except Exception as exc:
            self.lbl_status.text = f"{_('Error guardando configuración')}: {exc}"
            return

    def _launcher_script_path(self) -> str:
        workspace = (self._launcher_inputs["COBIEN_WORKSPACE_ROOT"].text or "").strip() or os.path.join(os.path.expanduser("~"), "cobien")
        frontend_name = (self._launcher_inputs["COBIEN_FRONTEND_REPO_NAME"].text or "").strip() or "cobien_FrontEnd"
        return os.path.join(workspace, frontend_name, "deploy", "ubuntu", "cobien-launcher.sh")

    def _systemd_launcher_active(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", "cobien-launcher.service"],
                check=False,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def run_full_update_reload(self) -> None:
        self.save_changes()
        launcher_script = self._launcher_script_path()
        if not os.path.isfile(launcher_script):
            self.lbl_status.text = f"{_('Error')}: launcher no encontrado: {launcher_script}"
            return

        env = self._read_env()
        use_systemd_restart = self._systemd_launcher_active()
        cmd = (
            ["systemctl", "--user", "restart", "cobien-launcher.service"]
            if use_systemd_restart
            else [
                "/bin/bash", launcher_script,
                "--non-interactive",
                "--yes",
                "--force-restart",
                "--run-update-once",
                "--mode", "run",
                "--workspace", env.get("COBIEN_WORKSPACE_ROOT", os.path.join(os.path.expanduser("~"), "cobien")),
                "--frontend-name", env.get("COBIEN_FRONTEND_REPO_NAME", "cobien_FrontEnd"),
                "--mqtt-name", env.get("COBIEN_MQTT_REPO_NAME", "cobien_MQTT_Dictionnary"),
                "--branch", env.get("COBIEN_UPDATE_BRANCH", "development_fix"),
                "--app-language", env.get("COBIEN_APP_LANGUAGE", "es"),
                "--device-id", env.get("COBIEN_DEVICE_ID", self.cfg.get_device_id()),
                "--videocall-room", env.get("COBIEN_VIDEOCALL_ROOM", self.cfg.get_videocall_room()),
                "--device-location", env.get("COBIEN_DEVICE_LOCATION", self.cfg.get_device_location()),
                "--tts-engine", env.get("COBIEN_TTS_ENGINE", "pyttsx3"),
            ]
        )

        piper_bin = shutil.which("piper")
        if env.get("COBIEN_TTS_ENGINE", "pyttsx3") == "piper" and not piper_bin:
            self.lbl_status.text = _("Piper no detectado. El launcher intentará configurarlo durante la recarga...")
        elif use_systemd_restart:
            self.lbl_status.text = _("Guardado completado. Reiniciando servicio del mueble...")
        else:
            self.lbl_status.text = _("Guardando y relanzando runtime...")

        def _run() -> None:
            try:
                completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if completed.returncode == 0:
                    Clock.schedule_once(lambda _dt: setattr(self.lbl_status, "text", _("Secuencia completada. Runtime recargado.")), 0)
                    return
                stderr_tail = (completed.stderr or "").strip().splitlines()[-1:] or [""]
                error_msg = stderr_tail[0] if stderr_tail[0] else f"return code {completed.returncode}"
                Clock.schedule_once(lambda _dt: setattr(self.lbl_status, "text", f"{_('Error en actualización')}: {error_msg}"), 0)
            except Exception as exc:
                Clock.schedule_once(lambda _dt: setattr(self.lbl_status, "text", f"{_('Error en actualización')}: {exc}"), 0)

        threading.Thread(target=_run, daemon=True).start()

    def on_pre_enter(self, *args: Any) -> None:
        self.load_values()
