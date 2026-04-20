import os
import json
import random
import importlib.util
import subprocess
import sys
import unicodedata
from glob import glob
from datetime import date, datetime

from kivy.config import Config
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle


# Voice (if you use it in your orchestrator)
from vosk import Model, KaldiRecognizer  # noqa
import pyaudio  # noqa
import paho.mqtt.client as mqtt

# Pantallas // Ecrans
from weather.weatherScreen import WeatherScreenWidget
from weather.weather_data import fetch_weather_bundle
from tts_service import tts_service
from events.eventsScreen import EventsScreen
from events.dayEventsScreen import DayEventsScreen
#from videocall.videocallScreen import VideoCallScreen
from board.boardScreen import BoardScreen
from mqtt_publisher import WEATHER_CITIES_GEO
from videocall.confirmation_popup import show_call_sent_popup
from videocall.contactScreen import ContactScreen, list_contact_path
from settings.settingsScreen import SettingsScreen
from settings.weatherChoice import WeatherChoice
from app_config import AppConfig
from settings.languageScreen import LanguageScreen
from settings.buttonColorsScreen import ButtonColorsScreen
from settings.notificationsScreen import NotificationsScreen
from settings.logsScreen import LogsMenuScreen, LogsViewerScreen
from settings.launcherConfigScreen import LauncherConfigScreen
from settings.rfidActionsScreen import RFIDActionsScreen
from settings.jokeCategoryScreen import JokeCategoryScreen
from jokes.jokesScreen import JokesScreen
from settings.pinCodeScreen import PinCodeScreen, PinDisplay, PinButton, PINBACK_BUTTON_KV
from device_heartbeat_service import send_device_heartbeat_async
from popup_style import wrap_popup_content, popup_theme_kwargs
from config_store import load_section

# Logs ICSO
from icso_data.navigation_logger import log_navigation
from icso_data.videocall_logger import log_call_request
from icso_data.wakeup_logger import log_wakeup
from icso_data.sync_service import schedule_icso_sync

# Virtual assistant
from virtual_assistant.actions import ActionExecutor
from virtual_assistant.recognizer import SpeechRecognizer
from virtual_assistant.main_assistant import AssistantOrchestrator

# Sleep screen
from black_overlay import BlackOverlay

# HTTP
import requests
from requests import HTTPError
import threading

# ✅ ÉTAPE 7 : Translation
from translation import _, change_language, get_current_language

# Notifications
from notifications.notification_manager import NotificationManager
from contact_sync_service import sync_contacts_for_device
from virtual_assistant.commands import refresh_contact_keywords

Builder.load_string(PINBACK_BUTTON_KV)

RUNTIME_STATE_DIR = os.path.join(os.path.dirname(__file__), "runtime_state")
UPDATE_MARKER_FILE = os.path.join(RUNTIME_STATE_DIR, "system_updated.json")
LAUNCHER_STOP_REQUEST_FILE = os.path.join(RUNTIME_STATE_DIR, "launcher_stop_requested.flag")

# Prevent Kivy from closing the app directly when Escape is pressed.
Config.set("kivy", "exit_on_escape", "0")

# Ventana
Window.fullscreen = 'auto'
Window.clearcolor = (1, 1, 1, 1)

KV = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

# ====== CONSTANTES ======
#:set CARD_R dp(24)
#:set CARD_BORDER 3
#:set HEADER_ALPHA 0.72
#:set CARD_ALPHA 0.72
#:set BUTTON_ALPHA 1
#:set BORDER_ALPHA 0.28
#:set SEP_ALPHA 0.28
#:set ICON_RADIUS dp(18)
#:set HEADER_ICON_RADIUS dp(14)
#:set BADGE_ICON_RADIUS dp(8)
#:set TITLE_H dp(56)
#:set CONTENT_H dp(170)
#:set PAD_L dp(16)

# ====== WIDGETS AUXILIARES ======
<RoundedButtonImage@Image>:
    canvas.before:
        StencilPush
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [ICON_RADIUS, ICON_RADIUS, ICON_RADIUS, ICON_RADIUS]
        StencilUse
    canvas.after:
        StencilUnUse
        StencilPop

<RoundedHeaderImage@Image>:
    canvas.before:
        StencilPush
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [HEADER_ICON_RADIUS, HEADER_ICON_RADIUS, HEADER_ICON_RADIUS, HEADER_ICON_RADIUS]
        StencilUse
    canvas.after:
        StencilUnUse
        StencilPop

<RoundedBadgeImage@Image>:
    canvas.before:
        StencilPush
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [BADGE_ICON_RADIUS, BADGE_ICON_RADIUS, BADGE_ICON_RADIUS, BADGE_ICON_RADIUS]
        StencilUse
    canvas.after:
        StencilUnUse
        StencilPop

<VSeparator@Widget>:
    size_hint_x: None
    width: dp(2)
    canvas:
        Color:
            rgba: 0, 0, 0, SEP_ALPHA
        Rectangle:
            size: self.size
            pos: self.pos

<RoundCardNoBorder@BoxLayout>:
    canvas.before:
        Color:
            rgba: 1, 1, 1, CARD_ALPHA
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [CARD_R, CARD_R, CARD_R, CARD_R]

<PanelOutlined@BoxLayout>:
    padding: dp(16)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(20), dp(20), dp(20), dp(20)]
        Color:
            rgba: 0, 0, 0, BORDER_ALPHA
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(20))

<NavButton@ButtonBehavior+BoxLayout>:
    padding: dp(32)
    spacing: dp(20)
    icon_source: ""
    text: ""
    on_release: app.on_nav(self.text)
    canvas.before:
        Color:
            rgba: 1, 1, 1, BUTTON_ALPHA
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [CARD_R, CARD_R, CARD_R, CARD_R]
        Color:
            rgba: 0, 0, 0, BORDER_ALPHA
        Line:
            width: CARD_BORDER
            rounded_rectangle: (self.x, self.y, self.width, self.height, CARD_R)
    BoxLayout:
        size_hint_x: None
        width: dp(70)
        padding: dp(2)
        RoundedButtonImage:
            source: root.icon_source if root.icon_source else app.placeholder_icon
            allow_stretch: True
            keep_ratio: True
            mipmap: True
            size_hint: None, None
            width: dp(200)
            height: dp(200)
    Label:
        text: root.text
        font_size: sp(70)
        color: 0, 0, 0, 1
        halign: "center"
        valign: "middle"
        text_size: self.size

<HeaderCard@BoxLayout>:
    padding: [dp(24), dp(12), dp(24), dp(12)]
    canvas.before:
        Color:
            rgba: 1, 1, 1, HEADER_ALPHA
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(28), dp(28), dp(28), dp(28)]

<VoiceBadge@ButtonBehavior+BoxLayout>:
    size_hint: None, None
    size: dp(100), dp(100)
    padding: dp(6)
    on_release: app.start_assistant()
    canvas.before:
        Color:
            rgba: 1, 1, 1, BUTTON_ALPHA
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(16), dp(16), dp(16), dp(16)]
        Color:
            rgba: 0, 0, 0, BORDER_ALPHA
        Line:
            width: 2.2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
    RoundedBadgeImage:
        source: app.mic_icon
        allow_stretch: True
        keep_ratio: True
        mipmap: True

<SettingsBadge@ButtonBehavior+BoxLayout>:
    size_hint: None, None
    size: dp(100), dp(100)
    padding: dp(6)
    on_release: app.root.current = "pin_code"
    canvas.before:
        Color:
            rgba: 1, 1, 1, BUTTON_ALPHA
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(16), dp(16), dp(16), dp(16)]
        Color:
            rgba: 0, 0, 0, BORDER_ALPHA
        Line:
            width: 2.2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
    RoundedBadgeImage:
        source: app.settings_icon
        allow_stretch: True
        keep_ratio: True
        mipmap: True

# ====== PANTALLA PRINCIPAL ======
<MainScreen>:
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if app.has_bg_image else ""

    BoxLayout:
        orientation: "vertical"
        padding: [dp(20), 0, dp(20), 0]
        spacing: 0

        Widget:
            size_hint_y: 1

        HeaderCard:
            size_hint_y: None
            height: dp(300)

            BoxLayout:
                orientation: "vertical"

                Widget:
                    size_hint_y: 1

                GridLayout:
                    cols: 5
                    size_hint_y: None
                    height: TITLE_H
                    spacing: 0
                    padding: 0

                    Label:
                        id: lbl_fecha
                        text: root.fecha_texto
                        markup: True
                        bold: True
                        font_size: sp(40)
                        color: 0, 0, 0, 1
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, None
                        size_hint_x: 1.30
                    VSeparator:

                    BoxLayout:
                        size_hint_x: 1.00
                        padding: [PAD_L, 0, 0, 0]
                        Label:
                            text: root.condicion_texto
                            markup: True
                            bold: True
                            font_size: sp(34)
                            color: 0, 0, 0, 1
                            halign: "left"
                            valign: "middle"
                            text_size: self.size
                    VSeparator:

                    BoxLayout:
                        size_hint_x: 1.45
                        padding: [PAD_L, 0, 0, 0]
                        Label:
                            id: lbl_proximos_eventos
                            text: root.proximos_eventos_texto
                            markup: True
                            bold: True
                            font_size: sp(34)
                            color: 0, 0, 0, 1
                            halign: "left"
                            valign: "top"
                            text_size: self.size

                GridLayout:
                    cols: 5
                    size_hint_y: None
                    height: CONTENT_H
                    spacing: 0
                    padding: 0

                    AnchorLayout:
                        size_hint_x: 1.30
                        anchor_x: "left"
                        anchor_y: "center"
                        Label:
                            text: root.hora_texto
                            font_size: sp(160)
                            color: 0, 0, 0, 1
                            halign: "left"
                            valign: "middle"
                            size_hint_y: None
                            height: self.texture_size[1]
                            text_size: self.width, None
                    VSeparator:

                    BoxLayout:
                        size_hint_x: 1.00
                        padding: [PAD_L, 0, 0, 0]
                        AnchorLayout:
                            anchor_y: "center"
                            BoxLayout:
                                orientation: "horizontal"
                                size_hint_y: None
                                height: self.minimum_height
                                spacing: dp(14)
                                RoundedHeaderImage:
                                    source: app.weather_icon
                                    size_hint: None, None
                                    size: dp(110), dp(110)
                                    allow_stretch: True
                                    keep_ratio: True
                                    mipmap: True
                                BoxLayout:
                                    orientation: "vertical"
                                    size_hint_y: None
                                    height: self.minimum_height
                                    Label:
                                        text: root.temp_texto
                                        font_size: sp(60)
                                        bold: True
                                        color: 0, 0, 0, 1
                                        halign: "left"
                                        valign: "middle"
                                        size_hint_y: None
                                        height: self.texture_size[1]
                                        text_size: self.width, None
                                    Label:
                                        text: root.minmax_texto
                                        font_size: sp(30)
                                        color: 0, 0, 0, 1
                                        halign: "left"
                                        valign: "middle"
                                        size_hint_y: None
                                        height: self.texture_size[1]
                                        text_size: self.width, None
                    VSeparator:

                    BoxLayout:
                        size_hint_x: 1.45
                        padding: [PAD_L, 0, 0, 0]
                        RelativeLayout:
                            BoxLayout:
                                orientation: "vertical"
                                size_hint: 1, None
                                height: self.minimum_height
                                pos_hint: {"top": 1}
                                spacing: dp(8)
                                Label:
                                    text: root.evento_1
                                    font_size: sp(30)
                                    color: 0, 0, 0, 1
                                    halign: "left"
                                    valign: "middle"
                                    size_hint_y: None
                                    height: self.texture_size[1]
                                    text_size: self.width, None

                                Label:
                                    id: lbl_joke_title
                                    text: root.joke_title
                                    bold: True
                                    font_size: sp(34)
                                    color: 0, 0, 0, 1
                                    halign: "left"
                                    valign: "middle"
                                    size_hint_y: None
                                    height: dp(48)
                                    text_size: self.size

                                ScrollView:
                                    do_scroll_x: False
                                    bar_width: dp(6)
                                    size_hint_y: None
                                    height: dp(120)
                                    BoxLayout:
                                        orientation: "vertical"
                                        size_hint_y: None
                                        height: self.minimum_height
                                        Label:
                                            text: root.joke_text
                                            font_size: sp(30)
                                            color: 0, 0, 0, 1
                                            halign: "left"
                                            valign: "top"
                                            text_size: self.width, None
                                            size_hint_y: None
                                            height: self.texture_size[1]

                            BoxLayout:
                                size_hint: None, None
                                size: dp(180), dp(100)
                                pos_hint: {"right": 0.95, "top": 1.4}
                                spacing: dp(10)

                                SettingsBadge:
                                VoiceBadge:

                Widget:
                    size_hint_y: 1

        Widget:
            size_hint_y: 0.2

        RoundCardNoBorder:
            size_hint_y: None
            height: dp(650)
            padding: [dp(22), dp(18), dp(22), dp(18)]

            GridLayout:
                cols: 2
                spacing: dp(20)
                padding: [0, 0, 0, 0]

                GridLayout:
                    cols: 2
                    spacing: dp(20)
                    size_hint_x: 1.15
                    row_default_height: dp(290)
                    row_force_default: True
                    padding: [dp(15), 0, 0, 0]

                    NavButton:
                        id: btn_tiempo
                        icon_source: app.icon_weather
                        text: root.btn_tiempo_texto
                    NavButton:
                        id: btn_eventos
                        icon_source: app.icon_calendar
                        text: root.btn_eventos_texto
                    NavButton:
                        id: btn_pizarra
                        icon_source: app.icon_board
                        text: root.btn_pizarra_texto
                    NavButton:
                        id: btn_llamame
                        icon_source: app.icon_videocall
                        text: root.btn_llamame_texto

        Widget:
            size_hint_y: 1
"""

#----------------------- CONTACT NAME --------------------------

def resolve_display_name(username):
    try:
        from videocall.contactScreen import list_contact_path
        with open(list_contact_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    display, user = map(str.strip, line.split("=", 1))
                    if user == username:
                        return display
    except Exception as e:
        print(f"[CONTACT] Erreur résolution nom: {e}")
    return username  # fallback propre

# -------------------------- LÓGICA --------------------------
class MainScreen(Screen):
    fecha_texto = StringProperty("")
    hora_texto = StringProperty("")
    # ✅ FIX 1 : Valeurs par défaut vides (pas de fausses données)
    condicion_texto = StringProperty("")
    temp_texto = StringProperty("—°")
    minmax_texto = StringProperty("—")
    evento_1 = StringProperty("")
    evento_2 = StringProperty("")
    estado_texto = StringProperty("Bienvenido a la aplicación")
    joke_title = StringProperty("Frase del día")
    joke_text = StringProperty("Cargando…")
    
    # ✅ ÉTAPE 7 : Properties pour les labels traduits
    proximos_eventos_texto = StringProperty("Próximos eventos")
    btn_tiempo_texto = StringProperty("Tiempo")
    btn_eventos_texto = StringProperty("Eventos")
    btn_pizarra_texto = StringProperty("Pizarra")
    btn_llamame_texto = StringProperty("Llámame")

    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = AppConfig()

        # Load device identity from settings.json
        self.DEVICE_ID = self.cfg.get_device_id()
        self.VIDEOCALL_ROOM = self.cfg.get_videocall_room()
        self.DEVICE_LOCATION = self.cfg.get_device_location()
        
        print(f"[MAIN] ========================================")
        print(f"[MAIN] Device configuration loaded from settings.json:")
        print(f"[MAIN]    Device ID: '{self.DEVICE_ID}' (case-sensitive)")
        print(f"[MAIN]    Videocall Room: '{self.VIDEOCALL_ROOM}' (case-sensitive)")
        print(f"[MAIN]    Location: '{self.DEVICE_LOCATION}'")
        print(f"[MAIN] ========================================")
        
        # ✅ ÉTAPE 7 : Charger traduction au démarrage
        
        self.action_executor = None
        #self.recognizer = SpeechRecognizer()
        # Local MQTT for furniture sensors/buttons
        random_id = "kivy_local_client"
        self.mqtt_client_local = mqtt.Client(client_id=random_id, clean_session=True)
        services_cfg = load_section("services", {})
        self.mqtt_broker_local = services_cfg.get("mqtt_local_broker", "localhost")
        self.mqtt_port_local = int(services_cfg.get("mqtt_local_port", 1883))
        self.mqtt_client_local.on_connect = self.on_connect_local
        self.mqtt_client_local.on_message = self.on_message_local
        self._subscribed_local = False
        self._processing_mqtt = False
        self.mqtt_topic_nav = "app/nav"

        try:
            self.mqtt_client_local.connect(self.mqtt_broker_local, self.mqtt_port_local, 60)
            self.mqtt_client_local.loop_start()
            print(f"[MQTT LOCAL] Connected to localhost (ID: {random_id})")
        except Exception as e:
            print(f"[MQTT LOCAL] Connection error: {e}")

        # Backend device-poll channel for web notifications
        backend_base_url = (services_cfg.get("backend_base_url", "") or "").strip().rstrip("/")
        self.backend_notification_client = None
        self.backend_poll_url = (
            services_cfg.get("device_poll_url")
            or (f"{backend_base_url}/pizarra/api/device/poll/" if backend_base_url else "")
        ).strip()
        self.backend_poll_interval_sec = max(float(services_cfg.get("device_poll_interval_sec", 5) or 5), 1.0)
        self.backend_poll_timeout_sec = float(services_cfg.get("http_timeout_sec", 8) or 8)
        self.backend_poll_api_key = (services_cfg.get("notify_api_key", "") or "").strip()
        self._backend_poll_event = None
        self._backend_poll_in_flight = False
        self.backend_poll_connected = False
        self.backend_poll_last_success_at = ""
        self.backend_poll_last_failure_at = ""
        self.backend_poll_last_status = None
        self.backend_poll_last_error = ""
        if self.backend_poll_url:
            print(
                f"[BACKEND POLL] Configured endpoint {self.backend_poll_url} "
                f"(interval={self.backend_poll_interval_sec}s)"
            )
            if self.backend_poll_api_key:
                print("[BACKEND POLL] Notify API key configured")
            else:
                print("[BACKEND POLL] Notify API key missing; polling may fail if backend auth is enabled")
        else:
            self.backend_poll_last_error = "device poll URL not configured"
            print("[BACKEND POLL] No poll URL configured; backend notifications disabled")

        # Gestionnaire de notifications
        self.notification_manager = NotificationManager(sm, self)
        self.last_backend_delivery_diagnostic = None

        # Reloj
        Clock.schedule_interval(self._update_datetime, 1)

        # ====== Clima ====== 
        # ✅ FIX 2 : Charger première ville de la liste
        self.cache_dir = os.path.join(os.path.dirname(__file__), "weather")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, "weather_today.json")

        # ✅ Charger ville prioritaire (ou fallback sur la première active)
        if WEATHER_CITIES_GEO:
            configured_primary_city = (self.cfg.data.get("weather_primary_city", "") or "").strip()
            selected_city = None

            if configured_primary_city:
                selected_city = next(
                    (c for c in WEATHER_CITIES_GEO if c.get("name") == configured_primary_city),
                    None,
                )
                if selected_city:
                    print(f"[MAIN] Primary weather city from settings: {configured_primary_city}")
                else:
                    print(
                        f"[MAIN] Configured primary city '{configured_primary_city}' not found in active weather list, "
                        "falling back to first active city."
                    )

            if selected_city is None:
                selected_city = WEATHER_CITIES_GEO[0]

            self.weather_city = selected_city["name"]
            self.weather_lat = selected_city["lat"]
            self.weather_lon = selected_city["lon"]
            self.weather_tz = selected_city.get("tz", "UTC")
            print(f"[MAIN] Active weather city for home screen: {self.weather_city}")
        else:
            # Fallback si liste vide
            self.weather_city = "Bilbao"
            self.weather_lat = 43.263
            self.weather_lon = -2.935
            self.weather_tz = "Europe/Madrid"
            print(f"[MAIN] No configured cities found, using fallback: {self.weather_city}")

        services_cfg = load_section("services", {})
        self.owm_api_key = (services_cfg.get("owm_api_key", "") or "").strip()

        Clock.schedule_once(lambda dt: self._update_weather_async(), 0)
        Clock.schedule_interval(lambda dt: self._update_weather_async(), 600)

        # ==== Chistes ====
        self._last_joke_date = None
        self._last_joke_change_time = None  # ✅ NOUVEAU : Pour éviter changements multiples
        self._current_joke_category = self.cfg.data.get("joke_category", "general")
        self._current_joke_language = get_current_language()

        # ⏰ HEURE DE CHANGEMENT DE LA BLAGUE (modifiez ici)
        self.JOKE_CHANGE_HOUR = 7    # ✅ Heure (0-23)
        self.JOKE_CHANGE_MINUTE = 0  # ✅ Minute (0-59)

        # Charger blagues au démarrage
        self.jokes = self._load_jokes()

        # Rafraîchir immédiatement
        Clock.schedule_once(lambda dt: self._maybe_refresh_joke(force=True), 0)

        # ✅ MODIFIÉ : Vérifier toutes les 30 secondes si l'heure est atteinte
        Clock.schedule_interval(lambda dt: self._check_joke_time(), 30)
        
        # ✅ ÉTAPE 7 : Mettre à jour les labels traduits
        self.update_labels()

        self._assistant_overlay = AssistantOverlay()
        self._assistant_init_lock = threading.Lock()

       
    def _maybe_refresh_joke(self, force=False):
        """✅ Rafraîchir blague si jour, langue OU catégorie changent"""
        today = datetime.now().date().isoformat()
        current_lang = get_current_language()
        current_category = self.cfg.data.get("joke_category", "general")
        
        # ✅ Vérifier si langue ou catégorie ont changé
        language_changed = self._current_joke_language != current_lang
        category_changed = self._current_joke_category != current_category
        day_changed = getattr(self, "_last_joke_date", None) != today
        
        if force or day_changed or language_changed or category_changed:
            # ✅ Recharger blagues si langue ou catégorie ont changé
            if language_changed or category_changed:
                print(f"[JOKES] Reloading jokes (lang={current_lang}, category={current_category})")
                self.jokes = self._load_jokes()
            
            # ✅ Afficher nouvelle blague
            self._last_joke_date = today
            if self.jokes:
                self.joke_text = random.choice(self.jokes)
                print(f"[JOKES] New joke displayed: {self.joke_text[:50]}...")
            else:
                self.joke_text = "..."

    def _check_joke_time(self):
        """✅ Vérifie si l'heure de changement est atteinte (ex: 10h25)"""
        now = datetime.now()
        today = now.date().isoformat()
        current_hour = now.hour
        current_minute = now.minute
        
        # Clé unique pour aujourd'hui + cette heure précise
        time_key = f"{today}_{self.JOKE_CHANGE_HOUR:02d}:{self.JOKE_CHANGE_MINUTE:02d}"
        
        # Si déjà changé à cette heure aujourd'hui, ne rien faire
        if self._last_joke_change_time == time_key:
            return
        
        # Si l'heure actuelle correspond exactement à l'heure configurée
        if current_hour == self.JOKE_CHANGE_HOUR and current_minute == self.JOKE_CHANGE_MINUTE:
            print(f"[JOKES] Automatic refresh at {self.JOKE_CHANGE_HOUR:02d}:{self.JOKE_CHANGE_MINUTE:02d}")
            self._last_joke_change_time = time_key
            
            # Recharger blagues (au cas où catégorie/langue auraient changé)
            self.jokes = self._load_jokes()
            
            # Forcer nouvelle blague
            self.reload_joke()

    def reload_joke(self):
        """✅ AMÉLIORÉ : Force le rechargement IMMÉDIAT d'une nouvelle blague"""
        print("[JOKES] Forced reload...")
        
        # 1. Sauvegarder l'ancienne blague
        old_joke = getattr(self, 'joke_text', None)
        
        # 2. Recharger les blagues avec la configuration actuelle
        self.jokes = self._load_jokes()
        
        # 3. Afficher immédiatement une nouvelle blague différente
        if self.jokes:
            # ✅ FORCER une blague différente (pas juste éviter, mais GARANTIR)
            if len(self.jokes) > 1 and old_joke:
                # Filtrer l'ancienne blague
                available = [j for j in self.jokes if j != old_joke]
                if available:
                    new_joke = random.choice(available)
                else:
                    # Si toutes les blagues sont identiques (impossible), prendre la première
                    new_joke = self.jokes[0]
            else:
                # Pas assez de blagues ou première fois
                new_joke = random.choice(self.jokes)
            
            self.joke_text = new_joke
            print(f"[JOKES] New joke displayed")
            print(f"[JOKES]    Previous: {old_joke[:30] if old_joke else 'None'}...")
            print(f"[JOKES]    New: {new_joke[:30]}...")
            print(f"[JOKES]    Category: {self.cfg.data.get('joke_category', 'general')}")
        else:
            self.joke_text = "..."
            print("[JOKES] No joke available")

    def update_labels(self):
        """✅ Met à jour tous les labels traduits"""
        
        # Mettre à jour labels
        self.proximos_eventos_texto = _("Próximos eventos")
        self.btn_tiempo_texto = _("Tiempo")
        self.btn_eventos_texto = _("Eventos")
        self.btn_pizarra_texto = _("Pizarra")
        self.btn_llamame_texto = _("Llámame")
        self.joke_title = _("Frase del día")
        
        # Forcer mise à jour date/heure
        self._update_datetime(0)
        
        # Recharger événements
        self._refresh_events()
        
        # Recharger météo
        self._update_weather_async()
        
        # ✅ NOUVEAU : Recharger blague si langue a changé
        self._maybe_refresh_joke(force=True)
        
        print("[MAIN] Labels updated")


    # ========== Callbacks MQTT LOCAL (capteurs/boutons du meuble) ==========
    def on_connect_local(self, client, userdata, flags, rc):
        print(f"[DEBUG] on_connect_local called - rc={rc}, flags={flags}")
        print(f"[DEBUG] _subscribed_local = {getattr(self, '_subscribed_local', 'UNDEFINED')}")
        
        if rc == 0:
            if self._subscribed_local:
                return
            
            result = client.subscribe(self.mqtt_topic_nav, qos=0)
            self._subscribed_local = True

    def on_message_local(self, client, userdata, msg):
        if self._processing_mqtt:
            return

        self._processing_mqtt = True
        """Traite les messages des capteurs locaux"""
        message = msg.payload.decode()
        topic = msg.topic
        print(f"[MQTT LOCAL] Message received on {topic}: {message[:50]}...")
        Clock.schedule_once(lambda dt: self._process_safe(message, topic))

    def _process_safe (self, message, topic):
        self.process_mqtt_message(message, topic)
        self._processing_mqtt = False

    # ========== Backend Polling (notifications du site web) ==========
    def _start_backend_polling(self):
        if not self.backend_poll_url:
            return
        if getattr(self, "_backend_poll_event", None):
            return
        self._backend_poll_event = Clock.schedule_interval(
            lambda dt: self._trigger_backend_poll(),
            self.backend_poll_interval_sec,
        )
        self._trigger_backend_poll()

    def _stop_backend_polling(self):
        event = getattr(self, "_backend_poll_event", None)
        if event:
            event.cancel()
            self._backend_poll_event = None

    def _trigger_backend_poll(self):
        if self._backend_poll_in_flight or not self.backend_poll_url:
            return
        self._backend_poll_in_flight = True
        threading.Thread(target=self._poll_backend_notifications, daemon=True).start()

    # Backward-compatible aliases for older launcher/runtime integrations that
    # still call the public method names without the leading underscore.
    def start_backend_polling(self):
        self._start_backend_polling()

    def stop_backend_polling(self):
        self._stop_backend_polling()

    def trigger_backend_poll(self):
        self._trigger_backend_poll()

    # Legacy typo compatibility kept temporarily for already deployed launchers.
    def start_bakend_polling(self):
        self._start_backend_polling()

    def _poll_backend_notifications(self):
        try:
            headers = {}
            if self.backend_poll_api_key:
                headers["X-API-KEY"] = self.backend_poll_api_key

            response = requests.get(
                self.backend_poll_url,
                params={"device_id": self.DEVICE_ID},
                headers=headers,
                timeout=self.backend_poll_timeout_sec,
            )
            response.raise_for_status()
            body = response.json()
            notifications = body.get("notifications", []) if isinstance(body, dict) else []

            self.backend_poll_connected = True
            self.backend_poll_last_success_at = datetime.now().isoformat()
            self.backend_poll_last_status = 0
            self.backend_poll_last_error = ""

            if notifications:
                Clock.schedule_once(
                    lambda dt, items=list(notifications): self._process_polled_backend_notifications(items)
                )
        except HTTPError as exc:
            status_code = getattr(exc.response, "status_code", -1)
            response_text = ""
            try:
                response_text = (exc.response.text or "").strip()
            except Exception:
                response_text = ""
            self.backend_poll_connected = False
            self.backend_poll_last_failure_at = datetime.now().isoformat()
            self.backend_poll_last_status = status_code
            self.backend_poll_last_error = response_text[:300] or str(exc)
            print(
                f"[BACKEND POLL] Poll failed with HTTP {status_code}: "
                f"{self.backend_poll_last_error}"
            )
        except Exception as exc:
            self.backend_poll_connected = False
            self.backend_poll_last_failure_at = datetime.now().isoformat()
            self.backend_poll_last_status = -1
            self.backend_poll_last_error = str(exc)
            print(f"[BACKEND POLL] Poll failed: {exc}")
        finally:
            self._backend_poll_in_flight = False

    def _process_polled_backend_notifications(self, notifications):
        for item in notifications:
            if not isinstance(item, dict):
                continue
            try:
                message = json.dumps(item)
            except Exception:
                continue
            print(f"[BACKEND POLL] Notification received: {message}")
            self.process_backend_notification(message, "device_poll")

    # ---------------- Fecha/Hora ----------------
    def on_pre_enter(self, *args):
        """✅ ÉTAPE 7 : Appelé avant d'afficher l'écran"""
        self.update_labels()
        self._update_datetime(0)

    def _update_datetime(self, dt):
        now = datetime.now()
        meses = [
            _("enero"), _("febrero"), _("marzo"), _("abril"), _("mayo"), _("junio"),
            _("julio"), _("agosto"), _("septiembre"), _("octubre"), _("noviembre"), _("diciembre")
        ]
        dias = [
            _("lunes"), _("martes"), _("miércoles"), _("jueves"), _("viernes"), _("sábado"), _("domingo")
        ]
        self.fecha_texto = f"{dias[now.weekday()].capitalize()}, {now.day} {_('de')} {meses[now.month-1]}, {now.year}"
        self.hora_texto = now.strftime("%H:%M")

    #  ================ CHISTES - NOUVEAU CODE ================
    def _load_jokes(self):
        """✅ Charge les blagues selon langue ET catégorie"""
        try:
            lang = get_current_language()
            category = self.cfg.data.get("joke_category", "general")
            
            # ✅ Sauvegarder état actuel
            self._current_joke_language = lang
            self._current_joke_category = category
            
            jokes_file = f"jokes_{'fr' if lang == 'fr' else 'es'}.json"
            jokes_path = os.path.join(os.path.dirname(__file__), "jokes", jokes_file)
            
            print(f"[JOKES] 📖 Chargement: {jokes_file} (cat={category})")
            
            if not os.path.exists(jokes_path):
                print(f"[JOKES] ❌ Fichier introuvable: {jokes_path}")
                return self._load_jokes_fallback(lang)
            
            with open(jokes_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Charger toutes les catégories si demandé
            if category == "all":
                jokes = []
                for cat_jokes in data.values():
                    if isinstance(cat_jokes, list):
                        jokes.extend(cat_jokes)
            else:
                # Charger catégorie demandée
                jokes = data.get(category, [])
            
            # Si catégorie vide, prendre "general"
            if not jokes and category not in ("general", "all"):
                print(f"[JOKES] ⚠️ Catégorie '{category}' vide, fallback 'general'")
                jokes = data.get("general", [])
            
            # Si toujours vide, prendre toutes les blagues
            if not jokes:
                print(f"[JOKES] ⚠️ Aucune blague trouvée, chargement complet")
                jokes = []
                for cat_jokes in data.values():
                    if isinstance(cat_jokes, list):
                        jokes.extend(cat_jokes)
            
            # Normaliser format
            normalized_jokes = []
            for joke in jokes:
                if isinstance(joke, str):
                    normalized_jokes.append(joke.strip())
                elif isinstance(joke, dict):
                    if "text" in joke:
                        normalized_jokes.append(str(joke["text"]).strip())
                    elif "setup" in joke and "punchline" in joke:
                        normalized_jokes.append(f"{joke['setup'].strip()} — {joke['punchline'].strip()}")
            
            jokes = [j for j in normalized_jokes if j]
            
            print(f"[JOKES] ✅ {len(jokes)} blagues chargées ({lang}, {category})")
            return jokes if jokes else self._load_jokes_fallback(lang)
        
        except Exception as e:
            print(f"[JOKES] ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return self._load_jokes_fallback(lang)
    
    def _load_jokes_fallback(self, lang):
        """Blagues par défaut si le fichier n'existe pas"""
        if lang == "fr":
            return [
                "Qu'est-ce qu'un jardinier dit à un autre ? On se voit quand on peut.",
                "Pourquoi les oiseaux n'utilisent pas Facebook ? Parce qu'ils ont déjà Twitter.",
                "Quel est le comble pour un électricien ? Que sa femme s'appelle Ampoule."
            ]
        else:
            return [
                "¿Qué le dice un jardinero a otro? Nos vemos cuando podamos.",
                "¿Por qué los pájaros no usan Facebook? Porque ya tienen Twitter.",
                "¿Cuál es el colmo de un electricista? Que su mujer se llame Luz."
            ]

    def _maybe_refresh_joke(self, force=False):
        """✅ Rafraîchir blague si jour, langue OU catégorie changent"""
        today = datetime.now().date().isoformat()
        current_lang = get_current_language()
        current_category = self.cfg.data.get("joke_category", "general")
        
        # ✅ Vérifier si langue ou catégorie ont changé
        language_changed = self._current_joke_language != current_lang
        category_changed = self._current_joke_category != current_category
        day_changed = getattr(self, "_last_joke_date", None) != today
        
        if force or day_changed or language_changed or category_changed:
            # ✅ Recharger blagues si langue ou catégorie ont changé
            if language_changed or category_changed:
                print(f"[JOKES] 🔄 Rechargement blagues (lang={current_lang}, cat={current_category})")
                self.jokes = self._load_jokes()
            
            # ✅ Afficher nouvelle blague
            self._last_joke_date = today
            if self.jokes:
                self.joke_text = random.choice(self.jokes)
                print(f"[JOKES] 🎭 Nouvelle blague affichée")
            else:
                self.joke_text = "..."

    def reload_joke(self):
        """✅ Force le rechargement d'une nouvelle blague (appelé depuis settings)"""
        print("[JOKES] 🔄 Rechargement forcé...")
    
        # 1. Sauvegarder l'ancienne blague
        old_joke = getattr(self, 'joke_text', None)
        
        # 2. ✅ FORCER la mise à jour de l'état actuel AVANT de recharger
        self._current_joke_language = get_current_language()
        self._current_joke_category = self.cfg.data.get("joke_category", "general")
        
        # 3. Recharger les blagues avec la configuration actuelle
        self.jokes = self._load_jokes()
        
        # 4. Afficher immédiatement une nouvelle blague différente
        if self.jokes:
            # ✅ FORCER une blague différente
            if len(self.jokes) > 1 and old_joke:
                available = [j for j in self.jokes if j != old_joke]
                if available:
                    new_joke = random.choice(available)
                else:
                    new_joke = self.jokes[0]
            else:
                new_joke = random.choice(self.jokes)
            
            self.joke_text = new_joke
            print(f"[JOKES] ✅ Nouvelle blague affichée")
            print(f"[JOKES]    Langue: {self._current_joke_language}")
            print(f"[JOKES]    Catégorie: {self._current_joke_category}")
            print(f"[JOKES]    Blague: {new_joke[:30]}...")
        else:
            self.joke_text = "..."
            print("[JOKES] ⚠️ Aucune blague disponible")
    #  ========== FIN CHISTES ==========

    # ================= EVENTOS =================
    def _refresh_events_on_day_change(self):
        today = datetime.now().date().isoformat()
        if getattr(self, "_last_event_date", None) != today:
            self._last_event_date = today
            self._refresh_events()

    def _refresh_events(self):
        events = self._load_local_events(limit=2)
        if len(events) < 2:
            events += self._gather_from_other_sources(limit=4)
            future = [e for e in events if e.get("dt") and e["dt"] >= datetime.now()]
            future.sort(key=lambda x: x["dt"])
            unique, seen = [], set()
            for e in future:
                key = (e["title"], e["dt"])
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            events = unique[:2]

        if events:
            def fmt_display(d: datetime, had_time: bool):
                if d.date() == datetime.now().date():
                    return d.strftime("%H:%M") if had_time else _("Hoy")
                return d.strftime("%d/%m %H:%M") if had_time else d.strftime("%d/%m")

            self.evento_1 = f"{events[0]['title']}  -  {fmt_display(events[0]['dt'], events[0]['had_time'])}"
            self.evento_2 = f"{events[1]['title']}  -  {fmt_display(events[1]['dt'], events[1]['had_time'])}" if len(events) > 1 else ""
        else:
            self.evento_1 = _("Sin eventos próximos")
            self.evento_2 = ""

    def _load_local_events(self, limit=2):
        base = os.path.join(os.path.dirname(__file__), "events")
        path = os.path.join(base, "eventos_local.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[EVENTS] Error abriendo eventos_local.json: {e}")
            return []

        if isinstance(raw, dict):
            merged = []
            for k in ("azul", "rojo", "blue", "red", "bleu", "rouge", "eventos", "events", "évènements", "items", "lista", "liste", "data", "all"):
                v = raw.get(k)
                if isinstance(v, list):
                    merged.extend(v)
            if not merged:
                for v in raw.values():
                    if isinstance(v, list):
                        merged.extend(v)
            raw = merged

        items = self._normalize_events(raw, 1024)
        future = [e for e in items if e["dt"] >= datetime.now()]
        future.sort(key=lambda x: x["dt"])
        return future[:limit]

    def _gather_from_other_sources(self, limit=4):
        pool = []
        pool += self._collect_from_screen('events')
        pool += self._collect_from_screen('day_events')
        pool += self._collect_from_events_folder()
        future = [e for e in pool if e.get("dt") and e["dt"] >= datetime.now() and e.get("title")]
        future.sort(key=lambda x: x["dt"])
        return future[:limit]

    def _collect_from_screen(self, screen_name):
        out = []
        try:
            if not self.sm.has_screen(screen_name):
                return out
            sw = self.sm.get_screen(screen_name).children[0]
            if hasattr(sw, "get_upcoming_events"):
                out += self._normalize_events(sw.get_upcoming_events(n=128), 128)
            if hasattr(sw, "get_all_events"):
                out += self._normalize_events(sw.get_all_events(), 512)
            for attr in ["events_blue", "blue_events", "events_red", "red_events",
                         "events", "all_events", "data", "items"]:
                if hasattr(sw, attr):
                    out += self._normalize_events(getattr(sw, attr), 512)
        except Exception as e:
            print(f"[EVENTS] Screen '{screen_name}': {e}")
        return out

    def _collect_from_events_folder(self):
        out = []
        try:
            base = os.path.join(os.path.dirname(__file__), "events")
            for p in glob(os.path.join(base, "*.json")):
                if os.path.basename(p).lower() == "eventos_local.json":
                    continue
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                out += self._normalize_events(data, 2048)
        except Exception as e:
            print(f"[EVENTS] Carpeta events: {e}")
        return out

    def _normalize_events(self, data, limit):
        def parse_dt(val_date, val_time=None):
            if isinstance(val_date, dict):
                d = val_date.get("dia") or val_date.get("date") or val_date.get("fecha")
                t = val_date.get("hora") or val_date.get("time")
                if d:
                    return parse_dt(d, t)
            if isinstance(val_date, datetime):
                return val_date, True
            if isinstance(val_date, str) and val_time:
                s = f"{val_date.strip()} {str(val_time).strip()}"
            else:
                s = str(val_date).strip() if val_date is not None else ""
            s = s.replace("T", " ")
            formats = [
                "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%Y-%m-%d",
                "%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(s, fmt)
                    if fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        return dt.replace(hour=0, minute=0), False
                    return dt, True
                except Exception:
                    pass
            try:
                dt = datetime.fromisoformat(s)
                return dt, True
            except Exception:
                return None, False

        normalized = []
        for e in (data or []):
            title, dt, had_time = None, None, False
            if isinstance(e, dict):
                title = e.get("title") or e.get("titulo") or e.get("name")
                if "datetime" in e:
                    dt, had_time = parse_dt(e["datetime"])
                elif "start" in e:
                    dt, had_time = parse_dt(e["start"])
                elif "dt" in e:
                    dt, had_time = parse_dt(e["dt"])
                elif "fecha" in e and "hora" in e:
                    dt, had_time = parse_dt(e["fecha"], e["hora"])
                elif "dia" in e and "hora" in e:
                    dt, had_time = parse_dt(e["dia"], e["hora"])
                elif "date" in e and ("time" in e or "hora" in e):
                    dt, had_time = parse_dt(e["date"], e.get("time") or e.get("hora"))
                elif "date" in e or "fecha" in e:
                    dt, had_time = parse_dt(e.get("date") or e.get("fecha"))
                elif isinstance(e.get("fecha"), dict):
                    dt, had_time = parse_dt(e["fecha"])
            if title and dt:
                normalized.append({"title": str(title).strip(), "dt": dt, "had_time": had_time})
            if len(normalized) >= limit:
                break
        return normalized

    # ---------------- CLIMA ----------------
    # ✅ FIX 4 : Nouvelle méthode _fetch_weather_and_update COMPLÈTE
    def _update_weather_async(self):
        threading.Thread(target=self._fetch_weather_and_update, daemon=True).start()

    def _fetch_weather_and_update(self):
        """Récupère la météo principale avec la même base de calcul que l'écran météo."""
        try:
            lang = get_current_language()
            print(f"[MAIN_WEATHER] 🌐 Fetching {self.weather_city} (lang={lang})")
            bundle = fetch_weather_bundle(
                city_name=self.weather_city,
                lat=self.weather_lat,
                lon=self.weather_lon,
                tz_name=self.weather_tz,
                api_lang=lang,
                owm_api_key=self.owm_api_key,
                forecast_days=2,
            )
            temp = bundle["temp"]
            temp_min = bundle["temp_min"]
            temp_max = bundle["temp_max"]
            description = bundle["description"]
            icon_path = bundle["icon"]
            
            # Mettre à jour l'interface (dans le thread UI)
            def _update_ui(dt):
                self.temp_texto = f"{temp}°"
                self.minmax_texto = f"{_('Min')} {temp_min}°   {_('Max')} {temp_max}°"
                self.condicion_texto = description
                
                # Mettre à jour l'icône
                app = App.get_running_app()
                if os.path.exists(icon_path):
                    app.weather_icon = icon_path
                
                print(f"[MAIN_WEATHER] ✅ {temp}°, {description}")
            
            Clock.schedule_once(_update_ui, 0)
            
            # Sauvegarder en cache
            cache_data = {
                "city": bundle["city"],
                "temp": temp,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "description": description,
                "icon": icon_path,
                "timestamp": datetime.now().isoformat()
            }
            self._save_day_cache(cache_data)
            
        except Exception as e:
            print(f"[MAIN_WEATHER] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            # Charger depuis cache en cas d'erreur
            self._load_weather_from_cache()

    # ✅ FIX 5 : Nouvelle méthode _load_weather_from_cache
    def _load_weather_from_cache(self):
        """Charge météo depuis cache si API indisponible"""
        try:
            cache = self._load_day_cache()
            if cache and "temp" in cache:
                def _update_ui(dt):
                    self.temp_texto = f"{cache['temp']}°"
                    self.minmax_texto = f"{_('Min')} {cache['temp_min']}°   {_('Max')} {cache['temp_max']}°"
                    self.condicion_texto = cache.get("description", "")
                    
                    app = App.get_running_app()
                    icon = cache.get("icon", "data/images/nubes.png")
                    if os.path.exists(icon):
                        app.weather_icon = icon
                    
                    print(f"[MAIN_WEATHER] 📦 Loaded from cache")
                
                Clock.schedule_once(_update_ui, 0)
        except Exception as e:
            print(f"[MAIN_WEATHER] ❌ Cache error: {e}")

    def _get_today_minmax_open_meteo(self):
        return None, None

    def _load_day_cache(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[CLIMA] Error leyendo caché: {e}")
        return {}

    def _save_day_cache(self, data: dict):
        try:
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
        except Exception as e:
            print(f"[CLIMA] Error guardando caché: {e}")

    def _map_weather_icon(self, weather_id: int, icon_code: str) -> str:
        is_day = icon_code.endswith("d")
        if weather_id // 100 == 2:
            return "data/images/tormenta.png"
        elif weather_id // 100 == 3:
            return "data/images/lluvia.png"
        elif weather_id // 100 == 5:
            return "data/images/lluvia.png"
        elif weather_id // 100 == 6:
            return "data/images/nieve.png"
        elif weather_id // 100 == 7:
            return "data/images/neblina.png"
        elif weather_id == 800:
            return "data/images/sol.png" if is_day else "data/images/noche.png"
        elif 801 <= weather_id <= 802:
            return "data/images/parcial.png"
        elif 803 <= weather_id <= 804:
            return "data/images/nubes.png"
        return "data/images/nubes.png"

    def _apply_home_weather_city_list(self, cities):
        """Refresh home-screen weather city from a runtime city list payload."""
        if not cities:
            print("[MAIN] Weather list update ignored: empty list")
            return

        configured_primary_city = (self.cfg.data.get("weather_primary_city", "") or "").strip()
        selected_city = None

        if configured_primary_city:
            selected_city = next(
                (city for city in cities if city.get("name") == configured_primary_city),
                None,
            )
            if selected_city:
                print(f"[MAIN] Weather list update matched primary city: {configured_primary_city}")
            else:
                print(
                    f"[MAIN] Primary city '{configured_primary_city}' missing from refreshed list, "
                    "falling back to first active city."
                )

        if selected_city is None:
            selected_city = cities[0]

        self.weather_city = selected_city["name"]
        self.weather_lat = selected_city["lat"]
        self.weather_lon = selected_city["lon"]
        self.weather_tz = selected_city.get("tz", "UTC")
        print(f"[MAIN] Home weather city refreshed: {self.weather_city}")
        self._update_weather_async()

    # ---------------- MQTT / navegación ----------------
    def process_mqtt_message(self, message, topic):
        """Traite les messages MQTT des capteurs locaux"""
        
        # Configuration to wakeup the app if needed
        app = App.get_running_app()
        if (
            app
            and getattr(app, "black_overlay", None)
            and app.black_overlay.parent
        ):
            print("[WAKEUP] Wakeup via MQTT")
            app.black_overlay.dismiss()
            app._on_wakeup()

        if topic == self.mqtt_topic_nav:
            try:
                data = json.loads(message)
                msg_type = data.get("type", "").lower()
                if msg_type != "nav":
                    return
                target = data.get("target", "").lower()
                source = data.get("source", "unknown")
                extra = data.get("extra", {})

                if source == "home_button":
                    log_navigation("home_button", target)
                    self.sm.current = "main"
                    return

                elif source == "vocal_assistant":
                    self.start_assistant()
                    return

                elif source == "rfid":
                    log_navigation("rfid_cards", target)
                
                if target == "events":
                    self.sm.current = "events"
                elif target == "day_events":
                    try:
                        day_str = extra.get("day", date.today().isoformat())
                        day = datetime.fromisoformat(day_str).date()
                    except Exception:
                        day = date.today()

                    day_screen = self.sm.get_screen('day_events').children[0]
                    if hasattr(day_screen, "show_day"):
                        day_screen.show_day(day)

                    self.sm.current = "day_events"

                elif target == "main":
                    self.sm.current = "main"

                elif target == "voice_cmd":
                    self.start_assistant()
                
                elif target == "videocall":
                    to_user = (extra or {}).get("to_user")
                    if to_user:
                        print(f"[MQTT] Demande d'appel → {to_user}")
                        from videocall.request_call import send_pizarra_notification
                        threading.Thread(
                            target=send_pizarra_notification,
                            args=(to_user,),
                            daemon=True
                        ).start()
                        display_name = resolve_display_name(to_user)
                        show_call_sent_popup(contact_name=display_name)
                        log_call_request()
                        print(f"[CONTACT] Notification envoyée à {display_name}")
                    else:
                        # fallback: comportement actuel (l'utilisateur choisit manuellement)
                        self.sm.current = "contacts"

                elif target == "weather":
                    self.sm.current = "weather"
                    w = self.sm.get_screen("weather").children[0]
                    name = extra.get("name")
                    lat = extra.get("lat")
                    lon = extra.get("lon")
                    tz = extra.get("tz")
                    if name and lat and lon and tz:
                        print(f"[MQTT] Météo → {name}")
                        w.set_city_dynamic(name, lat, lon, tz)
                    else:
                        print("[MQTT] Données météo invalides :", extra)

                elif target == "weather_list":
                    cities = extra.get("cities", [])
                    if isinstance(cities, list):
                        self._apply_home_weather_city_list(cities)
                    else:
                        print("[MQTT] Weather list payload invalid:", extra)

                print(f"[MQTT] Navigation vers {target}")
                return

            except Exception as e:
                print(f"[MQTT] Erreur générale: {e}")

    def process_backend_notification(self, message, topic):
        """Traite uniquement les notifications venant du BACKEND"""
        
        print(f"[BACKEND_NOTIF] ========================================")
        print(f"[BACKEND_NOTIF] 📩 Topic: {topic}")
        print(f"[BACKEND_NOTIF] 📩 Message: {message[:100]}...")
        
        # ========== PARSE JSON ==========
        try:
            data = json.loads(message)
            print(f"[BACKEND_NOTIF] ✅ JSON parsé: {data}")
        except json.JSONDecodeError as e:
            print(f"[BACKEND_NOTIF] ❌ JSON invalide: {e}")
            print(f"[BACKEND_NOTIF] ========================================")
            return
        
        # Detect type early because some backend-originating admin events
        # (for example contact synchronization) can come from ignored accounts.
        notif_type = data.get("type", "").lower()

        # ✅ ============================================================
        # ✅ IGNORER COMPTES DU MEUBLE (CASE-SENSITIVE)
        # ✅ ============================================================
        sender = data.get("from", "")  # ✅ PAS de .lower() !
        
        # Liste des comptes à ignorer (EXACTEMENT avec cette casse)
        ignored_accounts = [
            self.DEVICE_ID,           # Ex: "CoBien1" (exact)
            self.VIDEOCALL_ROOM,      # Ex: "CoBien1" (exact)
            "cobien",                 # Compte portail (exact)
            "CoBien",                 # Compte portail (exact)
        ]
        
        if sender in ignored_accounts and notif_type not in {"contacts_updated", "contacts_sync", "contacts_refresh"}:
            print(f"[BACKEND_NOTIF] ⚠️ Message ignoré (compte du meuble)")
            print(f"[BACKEND_NOTIF]    From: '{sender}' (exact match)")
            print(f"[BACKEND_NOTIF]    Ignored: {ignored_accounts}")
            print(f"[BACKEND_NOTIF] ========================================")
            return
        # ✅ ============================================================
        
        # ========== VÉRIFIER LE DESTINATAIRE (CASE-SENSITIVE) ==========
        recipient = data.get("to") or data.get("target_device") or data.get("recipient")

        if recipient:
            # ✅ CAS 1 : Message pour "all" → Tout le monde reçoit
            if recipient == "all":
                print(f"[BACKEND_NOTIF] ✅ Message pour tous les meubles")
            
            # ✅ CAS 2 : Liste de destinataires (CASE-SENSITIVE)
            elif isinstance(recipient, list):
                if self.DEVICE_ID not in recipient:  # ✅ Comparaison EXACTE
                    print(f"[BACKEND_NOTIF] ⚠️ Message ignoré (pas destinataire)")
                    print(f"[BACKEND_NOTIF]    Pour: {recipient}")
                    print(f"[BACKEND_NOTIF]    Device: '{self.DEVICE_ID}' (exact)")
                    print(f"[BACKEND_NOTIF] ========================================")
                    return
            
            # ✅ CAS 3 : Destinataire unique (CASE-SENSITIVE STRICT)
            else:
                if recipient != self.DEVICE_ID:  # ✅ Comparaison EXACTE (pas de .lower())
                    print(f"[BACKEND_NOTIF] ⚠️ Message ignoré (destinataire différent)")
                    print(f"[BACKEND_NOTIF]    Pour: '{recipient}' (exact)")
                    print(f"[BACKEND_NOTIF]    Device: '{self.DEVICE_ID}' (exact)")
                    print(f"[BACKEND_NOTIF]    Match: {recipient == self.DEVICE_ID}")
                    print(f"[BACKEND_NOTIF] ========================================")
                    return
        else:
            # ⚠️ Pas de destinataire : afficher quand même (rétro-compatibilité)
            print(f"[BACKEND_NOTIF] ⚠️ Pas de champ 'to' spécifié")
            print(f"[BACKEND_NOTIF] ⚠️ Affichage par défaut")
        
        # ========== TRAITER PAR TYPE ==========
        
        # ✅ ========== APPEL MANQUÉ ==========
        if notif_type == "missed_call":
            timestamp = data.get("timestamp", "")
            caller = data.get("from") or _("Alguien")
            
            # Parser l'heure
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                local_time = dt.astimezone()
                time_str = local_time.strftime("%H:%M")
            except:
                time_str = _("recientemente")
            
            print(f"[BACKEND_NOTIF] 📞 Appel manqué")
            print(f"[BACKEND_NOTIF]    Caller: {caller}")
            print(f"[BACKEND_NOTIF]    Time: {time_str}")
            print(f"[BACKEND_NOTIF] ========================================")
            
            # Afficher notification
            self.notification_manager.show_missed_call_notification(caller, time_str)
            return
        # =========================================
        
        # ✅ VIDEOCALL (CASE-SENSITIVE STRICT)
        if notif_type == "videocall":
            caller = data.get("from") or _("Desconocido")
            room = data.get("room", self.VIDEOCALL_ROOM)  # ✅ Depuis settings.json
            
            print(f"[BACKEND_NOTIF] 📞 Videocall")
            print(f"[BACKEND_NOTIF]    From: '{caller}'")
            print(f"[BACKEND_NOTIF]    Room: '{room}' (case-sensitive)")
            print(f"[BACKEND_NOTIF] ========================================")
            
            self.notification_manager.show_videocall_notification(caller, room)
            return
        
        # ✅ NEW MESSAGE
        elif notif_type == "new_message":
            sender_msg = data.get("from") or _("Desconocido")
            has_image = bool(data.get("image"))
            has_text = bool(data.get("text"))
            
            print(f"[BACKEND_NOTIF] 💌 Message de {sender_msg}")
            print(f"[BACKEND_NOTIF]    Image: {has_image}")
            print(f"[BACKEND_NOTIF]    Texte: {has_text}")
            print(f"[BACKEND_NOTIF] ========================================")
            
            self.notification_manager.show_message_notification(
                sender_msg, has_image, has_text
            )
            return
        
        # ✅ NEW EVENT
        elif notif_type == "new_event":
            title = data.get("title") or _("Nuevo evento")
            date_str = data.get("date", "")
            location = data.get("location", "")
            
            # ✅ FILTRER PAR VILLE (CASE-SENSITIVE)
            if location:
                # Normaliser (minuscules, sans espaces superflus)
                location_normalized = location.lower().strip()
                configured_normalized = self.DEVICE_LOCATION.lower().strip()
                
                # Si l'événement n'est pas pour notre ville, ignorer
                if location_normalized != configured_normalized:
                    print(f"[BACKEND_NOTIF] ⚠️ Événement ignoré (mauvaise ville)")
                    print(f"[BACKEND_NOTIF]    Lieu événement: '{location}'")
                    print(f"[BACKEND_NOTIF]    Lieu meuble: '{self.DEVICE_LOCATION}'")
                    print(f"[BACKEND_NOTIF] ========================================")
                    return
            
            print(f"[BACKEND_NOTIF] 📅 Événement: {title}")
            print(f"[BACKEND_NOTIF]    Date: {date_str}")
            print(f"[BACKEND_NOTIF]    Lieu: {location}")
            print(f"[BACKEND_NOTIF] ========================================")
            
            self.notification_manager.show_event_notification(title, date_str)
            return

        # ✅ CONTACTS UPDATED
        elif notif_type in {"contacts_updated", "contacts_sync", "contacts_refresh"}:
            print(f"[BACKEND_NOTIF] 👥 Contacts sync requested")
            threading.Thread(
                target=self._sync_contacts_from_backend_notification,
                args=(data,),
                daemon=True,
            ).start()
            return

        elif notif_type == "backend_delivery_diagnostic":
            self.last_backend_delivery_diagnostic = {
                "check_id": data.get("check_id", ""),
                "from": data.get("from", ""),
                "timestamp": data.get("timestamp", ""),
            }
            print(f"[BACKEND_NOTIF] ✅ Backend delivery diagnostic received: {self.last_backend_delivery_diagnostic}")
            return
        
        # ❌ TYPE INCONNU
        else:
            print(f"[BACKEND_NOTIF] ⚠️ Type inconnu: {notif_type}")
            print(f"[BACKEND_NOTIF] ========================================")

    def _sync_contacts_from_backend_notification(self, payload):
        try:
            result = sync_contacts_for_device(device_id=self.DEVICE_ID, payload=payload)
            print(
                f"[CONTACTS_SYNC] ✅ Contacts synchronized: {result['count']} "
                f"(images: {result['images_downloaded']})"
            )

            # Refresh assistant keyword list so voice navigation uses fresh contacts.
            try:
                refresh_contact_keywords()
            except Exception as refresh_exc:
                print(f"[CONTACTS_SYNC] ⚠️ Could not refresh assistant contact keywords: {refresh_exc}")

            def _refresh_ui(_dt):
                if self.sm.has_screen("contacts"):
                    contacts_screen = self.sm.get_screen("contacts")
                    if hasattr(contacts_screen, "reload_contacts_from_disk"):
                        contacts_screen.reload_contacts_from_disk()
                if self.sm.has_screen("settings"):
                    settings_screen = self.sm.get_screen("settings")
                    if hasattr(settings_screen, "rfid_actions_screen"):
                        rfid_screen = settings_screen.rfid_actions_screen
                        if hasattr(rfid_screen, "load_available_contacts"):
                            rfid_screen.load_available_contacts()

            Clock.schedule_once(_refresh_ui, 0)
        except Exception as exc:
            print(f"[CONTACTS_SYNC] ❌ Contacts synchronization failed: {exc}")

    def on_nav(self, destino, source: str = "touchscreen", recognized_text: str = None):
        d = self._normalize_nav_text(destino)
        target = None
        if "tiempo" in d or "meteo" in d:
            target = "weather"
        elif "eventos" in d or "evenements" in d:
            target = "events"
        elif "pizarra" in d or "galerie" in d:
            target = "board"
        elif "llamame" in d or "appelle" in d:
            target = "contacts"
        elif "main" in d or "acceuil" in d or "accueil" in d:
            target = "main"
        if target:
            if target == "contacts":
                if not self.sm.has_screen("contacts"):
                    self._show_nav_reason_popup(_("La pantalla de videollamada no está disponible."))
                    return

                contacts_screen = self.sm.get_screen("contacts")
                contacts = getattr(contacts_screen, "contacts", [])
                if not contacts:
                    self._show_nav_reason_popup(_("No hay contactos configurados para videollamada."))
                    return

            # Log with the originating source (touchscreen by default).
            log_navigation(source, target, recognized_text)
            self.sm.current = target

    def _normalize_nav_text(self, text: str) -> str:
        if text is None:
            return ""
        base = str(text).strip().lower()
        return "".join(
            c for c in unicodedata.normalize("NFD", base)
            if unicodedata.category(c) != "Mn"
        )

    def _show_nav_reason_popup(self, message: str):
        popup = ModalView(
            auto_dismiss=True,
            size_hint=(1, 1),
            background="",
            background_color=(0, 0, 0, 0.55),
        )
        card = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(920), dp(360)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            padding=dp(28),
        )
        with card.canvas.before:
            Color(1, 1, 1, 0.98)
            bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(24)])
        card.bind(pos=lambda inst, *_: setattr(bg, "pos", inst.pos))
        card.bind(size=lambda inst, *_: setattr(bg, "size", inst.size))

        lbl = Label(
            text=message or _("No se puede abrir esta opción."),
            font_size=sp(36),
            color=(0.08, 0.08, 0.08, 1),
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        card.add_widget(lbl)
        popup.add_widget(card)
        popup.open()
    """
    def start_assistant(self):
        # Configuration to wakeup the app if needed
        app = App.get_running_app()
        if (
            app
            and getattr(app, "black_overlay", None)
            and app.black_overlay.parent
        ):
            print("[WAKEUP] Wakeup via MQTT")
            app.black_overlay.dismiss()
            app._on_wakeup()
        log_navigation("vocal_assistant", "assistant_triggered")
        #AssistantOrchestrator(self).start()
        self.assistant = AssistantOrchestrator(self)
        self.assistant.start()
    """
    ### SIMONA
    def start_assistant(self):
        # Configuration to wakeup the app if needed
        app = App.get_running_app()
        if (
            app
            and getattr(app, "black_overlay", None)
            and app.black_overlay.parent
        ):
            print("[WAKEUP] Wakeup via MQTT")
            app.black_overlay.dismiss()
            app._on_wakeup()

        log_navigation("vocal_assistant", "assistant_triggered")

        # Create assistant exactly once, protected against concurrent calls.
        with self._assistant_init_lock:
            if not hasattr(app, "assistant") or app.assistant is None:
                app.assistant = AssistantOrchestrator(self)

        # ✅ Garder un alias local si tu en as besoin
        self.assistant = app.assistant

        # ✅ Lancer (start() est déjà protégé contre le double démarrage)
        self.assistant.start()

    def reset_assistant(self):
        assistant = getattr(self, "assistant", None)
        if assistant is not None:
            try:
                assistant.cancel()
            except Exception:
                pass
        self.assistant = None

    def cancel_assistant(self):
        assistant = getattr(self, "assistant", None)
        if assistant is not None:
            try:
                assistant.cancel()
            except Exception as exc:
                print(f"[ASR] Cancel failed: {exc}")
        self.set_assistant_overlay(False, "")

    # SIMONA
    # Méthode relais pour pouvoir appeler la méthode _speak définie dans l'assistant virtuel
    """
    def speak(self, text: str):
        #Relais vers le TTS de l'assistant
        if hasattr(self, "assistant") and self.assistant:
            self.assistant._speak(text)
        else:
            print("[WARN] Assistant non initialisé, TTS ignoré")
    """
    """
    def speak(self, text: str):
        #Relais vers le TTS de l'assistant (NON BLOQUANT UI)
        
        if not hasattr(self, "assistant") or not self.assistant:
            print("[WARN] Assistant non initialisé, TTS ignoré")
            return

        import threading
        threading.Thread(
            target=self.assistant._speak,
            args=(text,),
            daemon=True
        ).start()
    """

    """
    def speak(self, text: str):
        #TTS global, toujours disponible si possible
        try:
            if not hasattr(self, "assistant") or self.assistant is None:
                from virtual_assistant.assistant_orchestrator import AssistantOrchestrator
                self.assistant = AssistantOrchestrator(self)

            import threading
            threading.Thread(
                target=self.assistant._speak,
                args=(text,),
                daemon=True
            ).start()

        except Exception as e:
            print(f"[WARN] Assistant indisponible, TTS ignoré: {e}")
    """

    def speak(self, text: str):
        app = App.get_running_app()
        if hasattr(app, "speak"):
            app.speak(text)

    def set_assistant_overlay(self, active: bool, message: str = ""):
        if active:
            self._assistant_overlay.set_message(message or _("Escuchando…"))
            if not self._assistant_overlay.parent:
                self._assistant_overlay.open()
            return

        if self._assistant_overlay.parent:
            self._assistant_overlay.dismiss()
        self._assistant_overlay.set_level(0.0)

    def update_assistant_audio_level(self, level: float):
        self._assistant_overlay.set_level(level)


    
class Root(ScreenManager):
    pass


class AssistantOverlay(ModalView):
    def __init__(self, **kwargs):
        super().__init__(auto_dismiss=False, **kwargs)
        self.size_hint = (1, 1)
        self.background_color = (0, 0, 0, 0.55)

        card = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(1040), dp(620)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            padding=[dp(56), dp(42), dp(56), dp(42)],
            spacing=dp(16),
        )
        with card.canvas.before:
            Color(1, 1, 1, 0.98)
            self._card_bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(24)])
        card.bind(pos=self._sync_card_bg, size=self._sync_card_bg)

        self._title = Label(
            text="Asistente",
            font_size=sp(54),
            bold=True,
            color=(0.08, 0.08, 0.08, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(88),
        )
        self._title.bind(size=lambda inst, value: setattr(inst, "text_size", value))

        self._message = Label(
            text="",
            font_size=sp(40),
            color=(0.12, 0.12, 0.12, 1),
            halign="center",
            valign="middle",
            size_hint_y=1,
        )
        self._message.bind(size=lambda inst, value: setattr(inst, "text_size", value))

        self._level = Label(
            text="Mic: [..........] 0%",
            markup=False,
            font_size=sp(30),
            color=(0.18, 0.18, 0.18, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(72),
        )
        self._level.bind(size=lambda inst, value: setattr(inst, "text_size", value))

        self._cancel_btn = Button(
            text=_("Cancelar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(30),
            bold=True,
        )
        self._cancel_btn.bind(on_release=self._cancel_assistant_now)

        card.add_widget(self._title)
        card.add_widget(self._message)
        card.add_widget(self._level)
        card.add_widget(self._cancel_btn)
        self.add_widget(card)

    def set_message(self, message: str):
        self._message.text = message

    def set_level(self, level: float):
        try:
            value = max(0.0, min(1.0, float(level)))
        except Exception:
            value = 0.0
        filled = int(round(value * 10))
        bar = ("#" * filled) + ("." * (10 - filled))
        self._level.text = f"Mic: [{bar}] {int(value * 100)}%"

    def _sync_card_bg(self, widget, *_args):
        self._card_bg.pos = widget.pos
        self._card_bg.size = widget.size

    def _cancel_assistant_now(self, *_args):
        app = App.get_running_app()
        main_ref = getattr(app, "main_ref", None)
        if main_ref and hasattr(main_ref, "cancel_assistant"):
            main_ref.cancel_assistant()


class MyApp(App):
    header_bg = StringProperty("assets/gradient_header.png")
    has_header_bg = BooleanProperty(False)
    bg_image = StringProperty("data/images/Cobien_ImagenFondoInterfaz.png")
    has_bg_image = BooleanProperty(False)
    placeholder_icon = StringProperty("")
    icon_weather = StringProperty("data/images/parcial.png")
    icon_calendar = StringProperty("data/images/eventos.png")
    icon_board = StringProperty("data/images/pizarra.png")
    icon_videocall = StringProperty("data/images/videollamada.png")
    weather_icon = StringProperty("data/images/sol.png")
    mic_icon = StringProperty("data/images/voice.png")
    settings_icon = StringProperty("data/images/settings.png")

    def _start_orchestrator(self):
        script = os.path.join(os.path.dirname(__file__), "mqtt_publisher.py")
        if not os.path.isfile(script):
            print("[WARN] mqtt_publisher.py introuvable:", script)
            return
        if getattr(self, "_orchestrator", None) and self._orchestrator.poll() is None:
            return
        print("[Orchestrator] Démarrage…")
        self._orchestrator = subprocess.Popen([sys.executable, script])
        print(f"[Orchestrator] PID = {self._orchestrator.pid}")

    def _stop_orchestrator(self):
        p = getattr(self, "_orchestrator", None)
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass


    def _start_proximity_logger(self):
        script_proximity_logger = os.path.join(os.path.dirname(__file__), "proximity_sensors_reader.py")
        if not os.path.isfile(script_proximity_logger):
            print("[WARN] proximity_sensor_logger.py introuvable:", script_proximity_logger)
            return
        if importlib.util.find_spec("can") is None:
            print("[Proximity Sensor] Skipped: python-can is not installed in this runtime.")
            return
        if not os.path.exists("/sys/class/net/can0"):
            print("[Proximity Sensor] Skipped: CAN interface can0 is not available on this device.")
            return
        if getattr(self, "_proximity_sensor", None) and self._proximity_sensor.poll() is None:
            return
        print("[Proximity Sensor] Démarrage.")
        self._proximity_sensor = subprocess.Popen([sys.executable, script_proximity_logger])
        print(f"[Proximity Sensor] PID = {self._proximity_sensor.pid}")

    def _stop_proximity_logger(self):
        p2 = getattr(self, "_proximity_sensor", None)
        if p2 and p2.poll() is None:
            try:
                p2.terminate()
            except Exception:
                pass

    def on_start(self):
        self._start_orchestrator()
        self._start_proximity_logger()
        self._start_backend_polling()
        schedule_icso_sync(force_snapshot=True)
        self._schedule_device_heartbeat()
        self._send_device_heartbeat()
        Clock.schedule_once(lambda dt: self._show_pending_system_update_notification(), 1.0)

    def on_stop(self):
        self._stop_orchestrator()
        self._stop_proximity_logger()
        self._stop_backend_polling()
        heartbeat_event = getattr(self, "_heartbeat_event", None)
        if heartbeat_event:
            heartbeat_event.cancel()

    def _show_pending_system_update_notification(self):
        if not os.path.exists(UPDATE_MARKER_FILE):
            return

        try:
            with open(UPDATE_MARKER_FILE, "r", encoding="utf-8") as marker_file:
                payload = json.load(marker_file)
        except Exception as exc:
            print(f"[APP] Failed to read update marker: {exc}")
            payload = {}

        try:
            os.remove(UPDATE_MARKER_FILE)
        except OSError as exc:
            print(f"[APP] Failed to remove update marker: {exc}")

        lang = self.cfg.data.get("language", "es")
        localized_defaults = {
            "es": {
                "title": "Sistema actualizado",
                "message": "El sistema se ha actualizado.",
            },
            "fr": {
                "title": "Système mis à jour",
                "message": "Le système a été mis à jour.",
            },
        }
        defaults = localized_defaults.get(lang, localized_defaults["es"])
        title_text = payload.get(f"title_{lang}") or defaults["title"]
        message_text = payload.get(f"message_{lang}") or defaults["message"]
        version_text = "unknown"
        try:
            version_path = os.path.join(os.path.dirname(__file__), "VERSION")
            with open(version_path, "r", encoding="utf-8") as vf:
                version_text = (vf.read().strip() or "unknown")
        except Exception:
            pass

        try:
            if getattr(self.main_ref, "notification_manager", None):
                self.main_ref.notification_manager.show_system_info_notification(
                    title_text=title_text,
                    message_text=message_text,
                    version_text=version_text,
                )
        except Exception as exc:
            print(f"[APP] Failed to show update notification: {exc}")

    def _schedule_device_heartbeat(self):
        services_cfg = load_section("services", {}) or {}
        interval_sec = int(services_cfg.get("device_heartbeat_interval_sec", 60) or 60)
        if getattr(self, "_heartbeat_event", None):
            self._heartbeat_event.cancel()
        self._heartbeat_event = Clock.schedule_interval(lambda dt: self._send_device_heartbeat(), interval_sec)

    def _send_device_heartbeat(self):
        current_screen = ""
        try:
            current_screen = getattr(self.root, "current", "") or ""
        except Exception:
            current_screen = ""
        send_device_heartbeat_async(
            screen_name=current_screen,
            extra_payload={
                "videocall_room": self.cfg.get_videocall_room(),
                "device_location": self.cfg.get_device_location(),
            },
        )

    def _reset_idle_timer(self, *args, **kwargs):
        """
        Réinitialise le timer de veille.
        Recharge le timeout depuis settings.json à chaque appel.
        """
        if self._handle_escape_request(*args):
            return True

        # Si l'overlay est déjà affiché, ne rien faire
        if getattr(self, "black_overlay", None) and self.black_overlay.parent:
            return
        
        # Annuler l'ancien timer
        if getattr(self, "_idle_event", None):
            self._idle_event.cancel()
        
        # RECHARGER le timeout depuis settings.json
        timeout = self.cfg.get_idle_timeout()
        
        # Logger UNIQUEMENT si le timeout a changé
        if timeout != getattr(self, '_last_timeout', None):
            print(f"[APP] ⏱️ Timeout veille mis à jour: {timeout}s")
            self._last_timeout = timeout
        
        from kivy.clock import Clock
        self._idle_event = Clock.schedule_once(self._show_black_overlay, timeout)

    def _on_first_user_input(self, *args):
        Window.unbind(
            on_touch_down=self._on_first_user_input,
            on_touch_move=self._on_first_user_input,
            on_mouse_move=self._on_first_user_input
        )

        Window.bind(
            on_touch_down=self._reset_idle_timer,
            on_touch_move=self._reset_idle_timer,
            on_key_down=self._reset_idle_timer,
            on_mouse_move=self._reset_idle_timer
        )

        self._reset_idle_timer()
        return False

    def _extract_window_keycode(self, *args):
        if len(args) >= 2 and isinstance(args[1], int):
            return args[1]
        return None

    def _load_settings_pin(self):
        env_pin = os.getenv("COBIEN_SETTINGS_PIN", "").strip()
        if env_pin:
            return env_pin

        try:
            security = load_section("security", {"settings_pin": "1234"}) or {"settings_pin": "1234"}
            pin = str(security.get("settings_pin", "")).strip()
            if pin:
                return pin
        except Exception:
            pass
        return "1234"

    def _close_exit_pin_popup(self):
        popup = getattr(self, "_exit_pin_popup", None)
        if popup:
            try:
                popup.dismiss()
            except Exception:
                pass
        self._exit_pin_popup = None

    def _show_exit_pin_popup(self):
        print("[APP] Exit request blocked outside administration")

    def _close_reboot_popup(self):
        popup = getattr(self, "_reboot_popup", None)
        if popup:
            try:
                popup.dismiss()
            except Exception:
                pass
        self._reboot_popup = None

    def request_admin_reboot(self):
        if getattr(self, "_reboot_popup", None):
            return

        root = BoxLayout(orientation="vertical", spacing=dp(18))
        title = Label(
            text=_("Confirmar reinicio"),
            font_size=sp(28),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(44),
        )
        info = Label(
            text=_("Ubuntu se reiniciará inmediatamente y la aplicación se cerrará durante el proceso."),
            font_size=sp(20),
            color=(0.2, 0.2, 0.2, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(84),
        )
        info.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))

        feedback = Label(
            text="",
            font_size=sp(18),
            color=(0.85, 0.1, 0.1, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(56),
        )
        feedback.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))

        def _cancel(*_args):
            self._close_reboot_popup()

        def _confirm(*_args):
            commands = [
                ["systemctl", "reboot"],
                ["loginctl", "reboot"],
                ["reboot"],
            ]

            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    print(f"[APP] Reboot command launched: {' '.join(cmd)}")
                    self._close_reboot_popup()
                    return
                except Exception as exc:
                    print(f"[APP] Reboot command failed ({' '.join(cmd)}): {exc}")

            feedback.text = _("No se ha podido reiniciar Ubuntu. Revisa los permisos del sistema.")

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None, height=dp(58))
        cancel_btn = Button(text=_("Cancelar"), font_size=sp(22))
        confirm_btn = Button(text=_("Reiniciar"), font_size=sp(22), background_color=(0.89, 0.57, 0.12, 1))
        btn_row.add_widget(Widget())
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)

        root.add_widget(title)
        root.add_widget(info)
        root.add_widget(feedback)
        root.add_widget(btn_row)

        popup = Popup(
            title="",
            content=wrap_popup_content(root),
            size_hint=(0.58, 0.42),
            auto_dismiss=False,
            **popup_theme_kwargs(),
        )

        cancel_btn.bind(on_release=_cancel)
        confirm_btn.bind(on_release=_confirm)
        popup.bind(on_dismiss=lambda *_: setattr(self, "_reboot_popup", None))

        self._reboot_popup = popup
        popup.open()

    def request_admin_exit(self):
        if getattr(self, "_exit_pin_popup", None):
            return

        root = BoxLayout(orientation="vertical", spacing=dp(18))
        title = Label(
            text=_("Confirmar salida"),
            font_size=sp(28),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(44),
        )
        info = Label(
            text=_("La aplicación se cerrará y quedará detenida hasta que el launcher la vuelva a iniciar."),
            font_size=sp(20),
            color=(0.2, 0.2, 0.2, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(84),
        )
        info.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))

        feedback = Label(
            text="",
            font_size=sp(18),
            color=(0.85, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(30),
        )

        def _cancel(*_args):
            self._close_exit_pin_popup()

        def _confirm(*_args):
            try:
                os.makedirs(RUNTIME_STATE_DIR, exist_ok=True)
                with open(LAUNCHER_STOP_REQUEST_FILE, "w", encoding="utf-8") as flag_file:
                    flag_file.write(f"{datetime.now().isoformat()}\n")
            except Exception as exc:
                print(f"[APP] Failed to write launcher stop request flag: {exc}")
                feedback.text = _("No se ha podido preparar la salida")
                return

            self._close_exit_pin_popup()
            app = App.get_running_app()
            try:
                setattr(app, "_force_exit", True)
            except Exception:
                pass
            app.stop()

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None, height=dp(58))
        cancel_btn = Button(text=_("Cancelar"), font_size=sp(22))
        confirm_btn = Button(text=_("Salir"), font_size=sp(22), background_color=(0.85, 0.18, 0.18, 1))
        btn_row.add_widget(Widget())
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)

        root.add_widget(title)
        root.add_widget(info)
        root.add_widget(feedback)
        root.add_widget(btn_row)

        popup = Popup(
            title="",
            content=wrap_popup_content(root),
            size_hint=(0.58, 0.42),
            auto_dismiss=False,
            **popup_theme_kwargs(),
        )

        cancel_btn.bind(on_release=_cancel)
        confirm_btn.bind(on_release=_confirm)
        popup.bind(on_dismiss=lambda *_: setattr(self, "_exit_pin_popup", None))

        self._exit_pin_popup = popup
        popup.open()

    def _handle_escape_request(self, *args):
        keycode = self._extract_window_keycode(*args)
        if keycode != 27:
            return False
        print("[APP] Escape ignored in kiosk mode")
        return True

    def _on_window_request_close(self, *args):
        return not bool(getattr(self, "_force_exit", False))


    def _show_black_overlay(self, *args):
        # Never suspend the OS on idle; only show black overlay.
        if not getattr(self, "black_overlay", None):
            return
        if self.black_overlay.parent:
            return
        self.black_overlay.open()

    def _on_wakeup(self):
        Clock.schedule_once(lambda dt: self._reset_idle_timer(), 0)
        log_wakeup()


    def speak(self, text: str):
        """
        TTS global, toujours disponible si possible
        """
        if not text:
            return

        try:
            import threading
            threading.Thread(
                target=self.speak_text,
                args=(text,),
                daemon=True
            ).start()

        except Exception as e:
            print(f"[WARN] Assistant indisponible, TTS ignoré: {e}")

    def speak_text(self, text: str):
        if not text:
            return
        language = self.cfg.data.get("language", "es")
        tts_service.speak_sync(text, language=language)


    def build(self):
        self.black_overlay = BlackOverlay(on_wakeup=self._on_wakeup)
        self._idle_event = None
        self._exit_pin_popup = None

        Window.bind(
            on_touch_down=self._on_first_user_input,
            on_touch_move=self._on_first_user_input,
            on_key_down=self._handle_escape_request,
            on_keyboard=self._handle_escape_request,
            on_mouse_move=self._on_first_user_input,
            on_request_close=self._on_window_request_close,
        )
        # Charger config et traduction
        self.cfg = AppConfig()

        # Charger timeout depuis settings.json
        self.IDLE_TIMEOUT_SEC = self.cfg.get_idle_timeout()
        print(f"[APP] ⏱️ Timeout veille: {self.IDLE_TIMEOUT_SEC}s")
        
        # Charger traduction selon config
        lang = self.cfg.data.get("language", "es")
        change_language(lang)
        print(f"[APP] 🌍 Langue chargée: {lang}")
        
        self.has_header_bg = os.path.exists(self.header_bg)
        self.has_bg_image = os.path.exists(self.bg_image)
        for name in ["icon_weather", "icon_calendar", "icon_board", "icon_videocall",
                     "weather_icon", "mic_icon"]:
            p = getattr(self, name)
            if not os.path.exists(p):
                setattr(self, name, "")
        
        Builder.load_string(KV)
        sm = Root()
        
        # Créer MainScreen avec traduction
        main_screen_widget = MainScreen(sm)
        self.action_executor = ActionExecutor(main_screen_widget)
        main_screen_widget.action_executor = self.action_executor
        main = Screen(name='main')
        main.add_widget(main_screen_widget)
        sm.add_widget(main)
        
        # Autres écrans
        weather_screen_widget = WeatherScreenWidget(sm)
        # ajout pour faire le lien avec weatherScreen et faire fonctionner la méthode speak de main_assistant
        weather_screen_widget.main_ref = main_screen_widget
        weather_screen_widget.set_city_list(WEATHER_CITIES_GEO)
        weather = Screen(name='weather')
        weather.add_widget(weather_screen_widget)
        sm.add_widget(weather)
        
        events = EventsScreen(sm, name='events')
        sm.add_widget(events)
        
        day_events = Screen(name='day_events')
        day_events.add_widget(DayEventsScreen())
        sm.add_widget(day_events)
        
        board = Screen(name='board')
        board.add_widget(BoardScreen(sm))
        sm.add_widget(board)
        
        contacts_screen = ContactScreen(sm, contacts_file=list_contact_path)
        contacts_screen.name = 'contacts'  # Important !
        sm.add_widget(contacts_screen)
        
        settings = Screen(name='settings')
        settings.add_widget(SettingsScreen(sm, self.cfg))
        sm.add_widget(settings)
        
        # Écran langue
        sm.add_widget(Screen(name='settings_language'))
        sm.get_screen('settings_language').add_widget(LanguageScreen(sm, self.cfg))
        
        # Écran couleurs boutons
        sm.add_widget(Screen(name='button_colors'))
        sm.get_screen('button_colors').add_widget(ButtonColorsScreen(sm, self.cfg))
        
        sm.add_widget(Screen(name='settings_notifications'))
        sm.get_screen('settings_notifications').add_widget(NotificationsScreen(sm, self.cfg))
        logs_menu = LogsMenuScreen(sm, self.cfg, name='settings_logs_menu')
        sm.add_widget(logs_menu)
        logs_can = LogsViewerScreen(sm, self.cfg, log_prefix="can-bus", title_text="Log CAN Bus", name='settings_logs_can')
        sm.add_widget(logs_can)
        logs_bridge = LogsViewerScreen(
            sm, self.cfg, log_prefix="mqtt-can-bridge", title_text="Log MQTT-CAN Bridge", name='settings_logs_bridge'
        )
        sm.add_widget(logs_bridge)
        logs_app = LogsViewerScreen(
            sm, self.cfg, log_prefix="cobien-app", title_text="Log Aplicación", name='settings_logs_app'
        )
        sm.add_widget(logs_app)
        logs_icso = LogsViewerScreen(
            sm,
            self.cfg,
            log_prefix="icso",
            title_text="Log ICSO",
            explicit_files=["icso_log.txt", "icso_log.json", "icso_proximity_sensors.txt"],
            name='settings_logs_icso',
        )
        sm.add_widget(logs_icso)
        launcher_settings_screen = LauncherConfigScreen(sm, self.cfg, name='settings_launcher')
        sm.add_widget(launcher_settings_screen)
        sm.add_widget(Screen(name='joke_category'))
        sm.get_screen('joke_category').add_widget(JokeCategoryScreen(sm, self.cfg))
        sm.add_widget(Screen(name='jokes'))
        sm.get_screen('jokes').add_widget(JokesScreen(sm))
        
        sm.add_widget(Screen(name='settings_rfid'))
        sm.get_screen('settings_rfid').add_widget(RFIDActionsScreen(sm, self.cfg))
        
        weather_choice_screen = WeatherChoice(sm, self.cfg)
        weather_choice = Screen(name='weather_choice')
        weather_choice.add_widget(weather_choice_screen)
        sm.add_widget(weather_choice)

        pin_screen = PinCodeScreen(sm=sm, cfg=self.cfg, target_screen="settings", name="pin_code")
        sm.add_widget(pin_screen)

        self.main_ref = main_screen_widget
        sm.current = 'main'
        return sm
    

    def reload_main_screen(self):
        """Recharge l'écran principal avec les nouvelles traductions"""
        print("[APP] 🔄 Rechargement écran principal...")
        
        try:
            # 1. Recharger traduction globale
            lang = self.cfg.data.get("language", "es")
            change_language(lang) 
            
            # 2. Mettre à jour l'écran principal
            if self.root.has_screen('main'):
                main_screen = self.root.get_screen('main')
                if main_screen.children:
                    main_widget = main_screen.children[0]
                    
                    # ✅ Appeler update_labels() du MainScreen
                    if hasattr(main_widget, 'update_labels'):
                        main_widget.update_labels()
                        print("[APP] ✅ MainScreen mis à jour")
            
            # 3. ✅ FORCER RECHARGEMENT IMMÉDIAT DES BLAGUES
            if hasattr(self, 'main_ref') and hasattr(self.main_ref, 'reload_joke'):
                self.main_ref.reload_joke()
                print("[APP] ✅ Blague rechargée")
            
            # 4. Mettre à jour TOUS les autres écrans
            self.reload_all_screens()
            
        except Exception as e:
            print(f"[APP] ❌ Erreur reload_main_screen: {e}")
            import traceback
            traceback.print_exc()

    def reload_all_screens(self):
        """Recharge tous les écrans avec les nouvelles traductions"""
        print("[APP] 🔄 Rechargement tous les écrans...")
        
        screens_to_update = [
            'weather', 'events', 'day_events', 'board', 'contacts',
            'settings', 'button_colors', 'settings_notifications',
            'settings_logs_menu', 'settings_logs_can', 'settings_logs_bridge', 'settings_logs_app',
            'settings_launcher',
            'settings_rfid', 'weather_choice', 'joke_category', 'jokes' , 'pin_code'
        ]
        
        for screen_name in screens_to_update:
            if not self.root.has_screen(screen_name):
                continue
            
            try:
                screen = self.root.get_screen(screen_name)
                if not screen.children:
                    continue
                
                widget = screen.children[0]
                
                # Essayer update_labels
                if hasattr(widget, 'update_labels'):
                    widget.update_labels()
                    print(f"[APP] ✅ {screen_name}")
                # Sinon essayer on_pre_enter
                elif hasattr(widget, 'on_pre_enter'):
                    widget.on_pre_enter()
                    print(f"[APP] ✅ {screen_name} (on_pre_enter)")
            
            except Exception as e:
                print(f"[APP] ⚠️ {screen_name}: {e}")
        
        print("[APP] ✨ Rechargement terminé")

    def on_nav(self, destino):
        self.main_ref.on_nav(destino)

    def start_assistant(self):
        self.main_ref.start_assistant()


if __name__ == '__main__':
    MyApp().run()
