"""
notifications/notification_manager.py
Notification manager for video calls, events, and pizarra messages.
Reads LED/ringtone configuration and sends parameters to the furniture via MQTT.

IMPORTANT: Room names are CASE-SENSITIVE to distinguish between:
- 'CoBien' and 'cobien' (different rooms)
- 'Maria' and 'maria' (different rooms)
"""
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.clock import Clock
from datetime import datetime
import os
import json
from translation import _, change_language
from kivy.app import App
import threading
import paho.mqtt.publish as publish

#ICSO
from icso_data.videocall_logger import log_call_start
from icso_data.notification_logger import log_received_photos, log_added_events

# ✅ IMPORT APP CONFIG TO READ settings.json
from app_config import AppConfig, MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

# ========== IMPORT CENTRALIZED LED MODULE ==========
from notifications.mqtt_led_sender import send_led_config_from_dict, turn_off_leds

# ========== IMPORT AUDIO PLAYER (with fallback) ==========
AUDIO_AVAILABLE = False
AUDIO_BACKEND = None

# Try pygame first (more stable)
try:
    import pygame
    pygame.mixer.init()
    AUDIO_AVAILABLE = True
    AUDIO_BACKEND = "pygame"
    print("[NOTIF_MANAGER] ✓ Audio backend: pygame")
except ImportError:
    # Fallback to playsound
    try:
        from playsound import playsound
        AUDIO_AVAILABLE = True
        AUDIO_BACKEND = "playsound"
        print("[NOTIF_MANAGER] ✓ Audio backend: playsound")
    except ImportError:
        AUDIO_AVAILABLE = False
        AUDIO_BACKEND = None
        print("[NOTIF_MANAGER] ⚠ No audio backend available")
        print("[NOTIF_MANAGER]   Install with: pip install pygame")

# ========== MQTT CONFIGURATION ==========
TOPIC_EVENTS_RELOAD = "events/reload"
TOPIC_BOARD_RELOAD = "board/reload"

# ========== CONFIGURATION ==========
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "config", 
    "notifications_config.json"
)
print(f"[NOTIF_MANAGER] Config file: {CONFIG_FILE}")

# Ringtones directory
RINGTONES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "settings",
    "ringtones"
)

# Global variable to store active audio thread
_active_audio_thread = None
_audio_stop_event = threading.Event()
NONE_RINGTONE = ""
NOTIFICATION_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "notifications",
    "cache",
)
NOTIFICATION_CACHE_FILE = os.path.join(NOTIFICATION_CACHE_DIR, "active_notifications.json")


def normalize_ringtone_name(ringtone):
    if ringtone is None:
        return NONE_RINGTONE

    ringtone_name = str(ringtone).strip()
    if not ringtone_name:
        return NONE_RINGTONE

    if ringtone_name in {"Ninguna", "Aucune", _("Ninguna")}:
        return NONE_RINGTONE

    return ringtone_name


def _notification_cache_key(kind, data):
    return json.dumps({"kind": kind, "data": data}, ensure_ascii=False, sort_keys=True, default=str)


def load_cached_notifications():
    if not os.path.exists(NOTIFICATION_CACHE_FILE):
        return []
    try:
        with open(NOTIFICATION_CACHE_FILE, "r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
        return payload.get("notifications", [])
    except Exception as e:
        print(f"[NOTIF_CACHE] ⚠️ Error loading cache: {e}")
        return []


def save_cached_notifications(items):
    try:
        os.makedirs(NOTIFICATION_CACHE_DIR, exist_ok=True)
        tmp_path = NOTIFICATION_CACHE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as cache_file:
            json.dump({"notifications": items}, cache_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, NOTIFICATION_CACHE_FILE)
    except Exception as e:
        print(f"[NOTIF_CACHE] ⚠️ Error saving cache: {e}")


def append_cached_notification(kind, data):
    cached = load_cached_notifications()
    entry_key = _notification_cache_key(kind, data)
    filtered = [item for item in cached if _notification_cache_key(item.get("kind"), item.get("data")) != entry_key]
    filtered.insert(0, {"kind": kind, "data": data, "saved_at": datetime.now().isoformat()})
    save_cached_notifications(filtered[:50])


def remove_cached_notification(kind, data):
    entry_key = _notification_cache_key(kind, data)
    cached = load_cached_notifications()
    filtered = [item for item in cached if _notification_cache_key(item.get("kind"), item.get("data")) != entry_key]
    if len(filtered) != len(cached):
        save_cached_notifications(filtered)

def load_notification_config():
    """Load notification configuration from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        print(f"[NOTIF_CONFIG] File not found: {CONFIG_FILE}")
        return {
            "videollamada": {
                "group": 7,
                "intensity": 255,
                "color": "#00FF00",
                "mode": "ON",
                "ringtone": NONE_RINGTONE
            },
            "nuevo_evento": {
                "group": 7,
                "intensity": 255,
                "color": "#FF0000",
                "mode": "ON",
                "ringtone": NONE_RINGTONE
            },
            "nueva_foto": {
                "group": 7,
                "intensity": 255,
                "color": "#0000FF",
                "mode": "BLINK",
                "ringtone": NONE_RINGTONE
            }
        }
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        for value in config.values():
            if isinstance(value, dict):
                value["ringtone"] = normalize_ringtone_name(value.get("ringtone"))
        print(f"[NOTIF_CONFIG] Configuration loaded from {CONFIG_FILE}")
        return config
    except Exception as e:
        print(f"[NOTIF_CONFIG] Error reading file: {e}")
        return {}

def stop_notification_ringtone():
    """Stop the currently playing ringtone"""
    global _audio_stop_event
    
    if not AUDIO_AVAILABLE:
        return
    
    try:
        _audio_stop_event.set()  # Stop signal
        
        if AUDIO_BACKEND == "pygame":
            pygame.mixer.music.stop()
            print("[RINGTONE] ✓ Ringtone stopped (pygame)")
        
        print("[RINGTONE] ✓ Stop signal sent")
    except Exception as e:
        print(f"[RINGTONE] ✗ Stop error: {e}")

def play_notification_ringtone(notification_type):
    """
    Play the configured ringtone for a notification type
    
    Args:
        notification_type: 'videollamada', 'nuevo_evento', or 'nueva_foto'
    """
    global _active_audio_thread, _audio_stop_event
    
    if not AUDIO_AVAILABLE:
        print(f"[RINGTONE] ⚠ No audio backend available")
        return
    
    # Stop previous ringtone if exists
    stop_notification_ringtone()
    _audio_stop_event.clear()  # Reset signal
    
    config = load_notification_config()
    
    if notification_type not in config:
        print(f"[RINGTONE] Type '{notification_type}' not found in config")
        return
    
    ringtone = normalize_ringtone_name(config[notification_type].get("ringtone"))
    
    if ringtone == NONE_RINGTONE or not ringtone or ringtone.strip() == "":
        print(f"[RINGTONE] No ringtone configured for {notification_type}")
        return
    
    ringtone_path = os.path.join(RINGTONES_DIR, ringtone)
    
    if not os.path.exists(ringtone_path):
        print(f"[RINGTONE] File not found: {ringtone_path}")
        return
    
    def _play_sound():
        try:
            print(f"[RINGTONE] Playing ({AUDIO_BACKEND}): {ringtone} for {notification_type}")
            
            if AUDIO_BACKEND == "pygame":
                pygame.mixer.music.load(ringtone_path)
                pygame.mixer.music.play()
                # Wait for playback end or stop signal
                while pygame.mixer.music.get_busy():
                    if _audio_stop_event.is_set():
                        pygame.mixer.music.stop()
                        print("[RINGTONE] ⏹ Playback interrupted")
                        return
                    pygame.time.Clock().tick(10)
            
            elif AUDIO_BACKEND == "playsound":
                # Note: playsound cannot be easily interrupted
                if not _audio_stop_event.is_set():
                    playsound(ringtone_path)
            
            print(f"[RINGTONE] ✓ Playback finished")
        except Exception as e:
            print(f"[RINGTONE] ✗ Playback error: {e}")
            import traceback
            traceback.print_exc()
    
    # Launch in separate thread to avoid blocking UI
    _active_audio_thread = threading.Thread(target=_play_sound, daemon=True)
    _active_audio_thread.start()

def send_led_mqtt(notification_type):
    """
    Send LED configuration to furniture via MQTT using centralized module
    
    Args:
        notification_type: 'videollamada', 'nuevo_evento', or 'nueva_foto'
    """
    print(f"[NOTIF_MANAGER] Sending LED for type: {notification_type}")
    
    config = load_notification_config()
    
    if notification_type not in config:
        print(f"[NOTIF_MANAGER] ⚠ Type '{notification_type}' not found in config")
        return
    
    params = config[notification_type]
    
    # Use centralized module
    send_led_config_from_dict(params)

def publish_events_reload():
    """Publish MQTT event to request events screen reload"""
    try:
        payload = {
            "target": "events",
            "type": "reload",
            "timestamp": datetime.now().isoformat()
        }
        publish.single(
            "app/nav",
            payload=json.dumps(payload),
            hostname=MQTT_LOCAL_BROKER,
            port=MQTT_LOCAL_PORT
        )
        print("[NOTIF_MANAGER] 📤 Events reload event published")
    except Exception as e:
        print(f"[NOTIF_MANAGER] ⚠️ MQTT publish error: {e}")

def publish_board_reload():
    """Publish MQTT event to request board screen reload"""
    try:
        payload = {
            "action": "reload",
            "timestamp": datetime.now().isoformat()
        }
        publish.single(
            TOPIC_BOARD_RELOAD,
            payload=json.dumps(payload),
            hostname=MQTT_LOCAL_BROKER,
            port=MQTT_LOCAL_PORT
        )
        print("[NOTIF_MANAGER] 📤 Board reload event published")
    except Exception as e:
        print(f"[NOTIF_MANAGER] ⚠️ MQTT publish error: {e}")

def publish_board_reload_last():
    """
    Publish MQTT event to request board screen reload AND show last message.
    """
    try:
        payload = {
            "target": "board",
            "type": "reload_last",
            "timestamp": datetime.now().isoformat()
        }
        
        publish.single(
            "app/nav",
            payload=json.dumps(payload),
            hostname=MQTT_LOCAL_BROKER,
            port=MQTT_LOCAL_PORT
        )
        
        print("[NOTIF_MANAGER] 📤 Board reload_last event published")
    
    except Exception as e:
        print(f"[NOTIF_MANAGER] ⚠️ MQTT publish error: {e}")

class NotificationPopup(ModalView):
    """Customizable notification popup based on type"""
    
    def __init__(self, notification_type, data, callback=None, **kwargs):
        print(f"[NOTIF] __init__ NotificationPopup for {notification_type}")
        
        # ✅ CRITIQUE : FORCER LA LANGUE AVANT super().__init__
        app = App.get_running_app()
        current_lang = app.cfg.data.get("language", "es")
        change_language(current_lang)
        print(f"[NOTIF] 🌍 Language forced to: {current_lang} BEFORE building popup")
        
        super().__init__(**kwargs)
        print(f"[NOTIF] super().__init__ OK")
        
        self.notification_type = notification_type
        self.data = data
        self.callback = callback
        
        # Modal configuration
        self.size_hint = (0.9, 0.7)
        self.auto_dismiss = False
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0)
        print(f"[NOTIF] Modal configuration OK")
        
        # Build content (maintenant _() utilisera la bonne langue)
        print(f"[NOTIF] Starting build_content...")
        self.content = self._build_content()
        print(f"[NOTIF] build_content OK")
        
        self.add_widget(self.content)
        print(f"[NOTIF] add_widget OK")
        
        print(f"[NOTIF] __init__ completed successfully")
    
    def _build_content(self):
        """Build content based on notification type"""
        main_layout = BoxLayout(orientation='vertical', padding=dp(40), spacing=dp(30))
        
        # White rounded background with border - CORRECT ORDER
        with main_layout.canvas.before:
            # 1. Draw border FIRST (behind)
            Color(0.2, 0.2, 0.2, 1)  # Dark gray border
            self.border_rect = RoundedRectangle(
                pos=(main_layout.x - 3, main_layout.y - 3),
                size=(main_layout.width + 6, main_layout.height + 6),
                radius=[dp(30)]
            )
            
            # 2. Draw white background ON TOP
            Color(1, 1, 1, 1)  # Pure white
            self.bg_rect = RoundedRectangle(
                pos=main_layout.pos,
                size=main_layout.size,
                radius=[dp(30)]
            )
        
        main_layout.bind(pos=self._update_rect, size=self._update_rect)
        
        if self.notification_type == 'videocall':
            return self._build_videocall_content(main_layout)
        elif self.notification_type == 'event':
            return self._build_event_content(main_layout)
        elif self.notification_type == 'message':
            return self._build_message_content(main_layout)
        
        return main_layout
    
    def _build_videocall_content(self, main_layout):
        """Build popup for video call"""
        caller = self.data.get('caller', _('Desconocido'))
        
        # Icon at top
        icon_path = "images/videollamada.png"
        if os.path.exists(icon_path):
            icon = Image(
                source=icon_path,
                size_hint=(None, None),
                size=(dp(140), dp(140)),
                pos_hint={'center_x': 0.5}
            )
            main_layout.add_widget(icon)
        
        # Space
        main_layout.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Title
        title = Label(
            text=_("Videollamada entrante"),
            font_size=sp(52),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(80),
            halign='center'
        )
        main_layout.add_widget(title)
        
        # Message
        message = Label(
            text=f"[b]{caller}[/b] {_('te está llamando')}",
            markup=True,
            font_size=sp(42),
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(70),
            halign='center'
        )
        main_layout.add_widget(message)
        
        # Space
        main_layout.add_widget(BoxLayout(size_hint_y=0.5))
        
        # Buttons
        buttons = BoxLayout(size_hint_y=None, height=dp(140), spacing=dp(40))
        
        # Decline button (red)
        decline_btn = Button(
            text=_("Rechazar"),
            font_size=sp(44),
            background_color=(0.9, 0.2, 0.2, 1),
            background_normal='',
            size_hint_x=0.45,
            color=(1, 1, 1, 1)
        )
        def on_decline(btn):
            self._on_action('decline')
        decline_btn.bind(on_release=on_decline)
        
        # Accept button (green)
        accept_btn = Button(
            text=_("Aceptar"),
            font_size=sp(44),
            background_color=(0.2, 0.8, 0.3, 1),
            background_normal='',
            size_hint_x=0.55,
            color=(1, 1, 1, 1)
        )
        def on_accept(btn):
            self._on_action('accept')
        accept_btn.bind(on_release=on_accept)
        
        buttons.add_widget(decline_btn)
        buttons.add_widget(accept_btn)
        main_layout.add_widget(buttons)
        
        return main_layout
    
    def _build_event_content(self, main_layout):
        """Build popup for new event"""
        title_text = self.data.get('title', _('Nuevo evento'))
        date_str = self.data.get('date', '')
        
        # Icon
        icon_path = "images/eventos.png"
        if os.path.exists(icon_path):
            icon = Image(
                source=icon_path,
                size_hint=(None, None),
                size=(dp(140), dp(140)),
                pos_hint={'center_x': 0.5}
            )
            main_layout.add_widget(icon)
        
        main_layout.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Title
        title = Label(
            text=_("Nuevo evento"),
            font_size=sp(52),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(80),
            halign='center'
        )
        main_layout.add_widget(title)
        
        # Details
        event_title = Label(
            text=f"[b]{title_text}[/b]",
            markup=True,
            font_size=sp(42),
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(70),
            halign='center'
        )
        main_layout.add_widget(event_title)
        
        if date_str:
            date_label = Label(
                text=date_str,
                font_size=sp(36),
                color=(0.4, 0.4, 0.4, 1),
                size_hint_y=None,
                height=dp(60),
                halign='center'
            )
            main_layout.add_widget(date_label)
        
        main_layout.add_widget(BoxLayout(size_hint_y=0.5))
        
        # Buttons
        buttons = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(30))
        
        close_btn = Button(
            text=_("Cerrar"),
            font_size=sp(38),
            background_color=(0.5, 0.5, 0.5, 1),
            background_normal='',
            size_hint_x=0.4,
            color=(1, 1, 1, 1)
        )
        def on_close(btn):
            self._on_action('ok')
        close_btn.bind(on_release=on_close)
        
        calendar_btn = Button(
            text=_("Ver calendario"),
            font_size=sp(38),
            background_color=(0.2, 0.6, 0.9, 1),
            background_normal='',
            size_hint_x=0.6,
            color=(1, 1, 1, 1)
        )
        def on_view_calendar(btn):
            self._on_action('view_calendar')
        calendar_btn.bind(on_release=on_view_calendar)
        
        buttons.add_widget(close_btn)
        buttons.add_widget(calendar_btn)
        main_layout.add_widget(buttons)
        
        return main_layout
    
    def _build_message_content(self, main_layout):
        """Build popup for new pizarra message"""
        sender = self.data.get('sender', _('Desconocido'))
        has_image = self.data.get('has_image', False)
        has_text = self.data.get('has_text', False)
        
        # Icon
        icon_path = "images/pizarra.png"
        if os.path.exists(icon_path):
            icon = Image(
                source=icon_path,
                size_hint=(None, None),
                size=(dp(140), dp(140)),
                pos_hint={'center_x': 0.5}
            )
            main_layout.add_widget(icon)
        
        main_layout.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Title
        title = Label(
            text=_("Nuevo mensaje"),
            font_size=sp(52),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(80),
            halign='center'
        )
        main_layout.add_widget(title)
        
        # Details
        content_parts = []
        if has_image:
            content_parts.append(_("una foto"))
        if has_text:
            content_parts.append(_("un mensaje"))
        
        content_str = _(" y ").join(content_parts) if content_parts else _("un mensaje")
        
        message = Label(
            text=f"[b]{sender}[/b] {_('te ha enviado')} {content_str}",
            markup=True,
            font_size=sp(42),
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(80),
            halign='center'
        )
        main_layout.add_widget(message)
        
        main_layout.add_widget(BoxLayout(size_hint_y=0.5))
        
        # Buttons
        buttons = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(30))
        
        later_btn = Button(
            text=_("Más tarde"),
            font_size=sp(38),
            background_color=(0.6, 0.6, 0.6, 1),
            background_normal='',
            size_hint_x=0.4,
            color=(1, 1, 1, 1)
        )
        def on_later(btn):
            self._on_action('later')
        later_btn.bind(on_release=on_later)
        
        view_btn = Button(
            text=_("Ver"),
            font_size=sp(38),
            background_color=(0.2, 0.6, 0.9, 1),
            background_normal='',
            size_hint_x=0.6,
            color=(1, 1, 1, 1)
        )
        def on_view(btn):
            self._on_action('view')
        view_btn.bind(on_release=on_view)
        
        buttons.add_widget(later_btn)
        buttons.add_widget(view_btn)
        main_layout.add_widget(buttons)
        
        return main_layout
    
    def _update_rect(self, *args):
        """Update background rectangle"""
        # Update white background
        self.bg_rect.pos = self.content.pos
        self.bg_rect.size = self.content.size
        
        # Update border (slightly bigger)
        self.border_rect.pos = (self.content.x - 3, self.content.y - 3)
        self.border_rect.size = (self.content.width + 6, self.content.height + 6)
    
    def _on_action(self, action):
        """Handle user actions"""        
        # ========== STOP SOUND AND LEDS ==========
        stop_notification_ringtone()
        turn_off_leds()
        
        if self.callback:
            self.callback(action, self.data)
        
        self.dismiss()

class NotificationManager:
    """Central notification manager"""
    
    def __init__(self, screen_manager, main_screen):
        self.sm = screen_manager
        self.main_screen = main_screen
        self.active_notifications = []
        
        # ✅ LOAD CONFIGURATION FROM settings.json
        self.cfg = AppConfig()
        self.device_id = self.cfg.get_device_id()
        self.videocall_room = self.cfg.get_videocall_room()
        self.device_location = self.cfg.get_device_location()
        
        print("[NOTIF_MANAGER] ========================================")
        print("[NOTIF_MANAGER] 📋 Configuration loaded from settings.json:")
        print(f"[NOTIF_MANAGER]    Device ID: {self.device_id}")
        print(f"[NOTIF_MANAGER]    Videocall Room: {self.videocall_room}")
        print(f"[NOTIF_MANAGER]    Location: {self.device_location}")
        print("[NOTIF_MANAGER] ========================================")
        
        # ✅ CASE-SENSITIVE notification history
        # Keys format: "videocall_{caller}_{room}_{minute}"
        # Preserves exact case of caller and room names
        self.notification_history = {}

        # Tracker du popup d'appel entrant actif (case-sensitive)
        self.active_videocall_popup = None
        
        print("[NOTIF_MANAGER] ✅ Notification manager initialized (CASE-SENSITIVE)")
    
    def show_videocall_notification(self, caller, room=None):
        """
        Show video call notification
        
        Args:
            caller: Caller name (CASE-SENSITIVE)
            room: Room name (CASE-SENSITIVE, optional)
        
        Note: 'CoBien' and 'cobien' are treated as DIFFERENT rooms
        """
        # ✅ CASE-SENSITIVE duplicate check
        # Include both caller AND room to distinguish between different calls
        current_time = datetime.now().strftime('%Y%m%d%H%M')
        notif_key = f"videocall_{caller}_{room}_{current_time}"
        
        if notif_key in self.notification_history:
            print(f"[NOTIF] ⚠️ Duplicate ignored (case-sensitive)")
            print(f"[NOTIF]    Key: {notif_key}")
            return
        
        self.notification_history[notif_key] = datetime.now()
        
        print(f"[NOTIF] ========================================")
        print(f"[NOTIF] 📞 New videocall notification")
        print(f"[NOTIF]    Caller: '{caller}' (case-sensitive)")
        print(f"[NOTIF]    Room: '{room}' (case-sensitive)")
        print(f"[NOTIF]    Key: {notif_key}")
        print(f"[NOTIF] ========================================")

        # Fermer popup précédent si existe
        if self.active_videocall_popup:
            print("[NOTIF] 🧹 Fermeture popup précédent")
            try:
                self.active_videocall_popup.dismiss()
            except:
                pass
            self.active_videocall_popup = None

        app = App.get_running_app()
        if app and getattr(app, "assistant", None):
            try:
                app.assistant.cancel()
                print("[NOTIF] Assistant cancelled because of incoming videocall")
            except Exception as e:
                print(f"[NOTIF] Failed to cancel assistant: {e}")
        
        # ========== SEND LED CONFIG TO FURNITURE ==========
        send_led_mqtt("videollamada")
        
        # ========== PLAY RINGTONE ==========
        play_notification_ringtone("videollamada")
        
        # ✅ PRESERVE CASE in data
        data = {
            'caller': caller,  # Exact case preserved
            'room': room,      # Exact case preserved
            'timestamp': datetime.now()
        }
        append_cached_notification('videocall', data)
        
        def _create_popup(dt):
            try:
                popup = NotificationPopup(
                    'videocall',
                    data,
                    callback=self._handle_videocall_action
                )

                # Sauvegarder référence
                self.active_videocall_popup = popup

                self.active_notifications.append(popup)
                popup.open()

                # Disable sleep mode screen
                app = App.get_running_app()
                if app and getattr(app, "black_overlay", None) and app.black_overlay.parent:
                    app.black_overlay.dismiss()
                    # relance timer + logs wakeup si tu l'as déjà dans MyApp
                    if hasattr(app, "_on_wakeup"):
                        app._on_wakeup()

                print(f"[NOTIF] ✅ Popup displayed for '{caller}' → room '{room}'")
            except Exception as e:
                print(f"[NOTIF] ❌ ERROR creating popup: {e}")
                import traceback
                traceback.print_exc()
        
        Clock.schedule_once(_create_popup, 0)
    
    def show_event_notification(self, title, date_str):
        """Show new event notification"""
        # ========== SEND LED CONFIG TO FURNITURE ==========
        send_led_mqtt("nuevo_evento")
        
        # ========== PLAY RINGTONE ==========
        play_notification_ringtone("nuevo_evento")

        # ========== PUBLISH MQTT RELOAD EVENT ==========
        publish_events_reload()
        
        data = {
            'title': title,
            'date': date_str,
            'timestamp': datetime.now()
        }
        append_cached_notification('event', data)
        
        def _create_popup(dt):
            try:
                popup = NotificationPopup(
                    'event',
                    data,
                    callback=self._handle_event_action
                )
                self.active_notifications.append(popup)
                popup.open()

                # Disable sleep mode screen
                app = App.get_running_app()
                if app and getattr(app, "black_overlay", None) and app.black_overlay.parent:
                    app.black_overlay.dismiss()
                    # relance timer + logs wakeup si tu l'as déjà dans MyApp
                    if hasattr(app, "_on_wakeup"):
                        app._on_wakeup()

                print(f"[NOTIF] Event: {title}")
            except Exception as e:
                print(f"[NOTIF] ERROR event: {e}")
        
        Clock.schedule_once(_create_popup, 0)

        #ICSO
        log_added_events()
    
    def show_message_notification(self, sender, has_image=False, has_text=False):
        """Show new pizarra message notification"""
        # ========== SEND LED CONFIG TO FURNITURE ==========
        send_led_mqtt("nueva_foto")
        
        # ========== PLAY RINGTONE ==========
        play_notification_ringtone("nueva_foto")

        # ========== PUBLISH MQTT RELOAD EVENT ==========
        publish_board_reload()
        
        data = {
            'sender': sender,
            'has_image': has_image,
            'has_text': has_text,
            'timestamp': datetime.now()
        }
        append_cached_notification('message', data)
        
        def _create_popup(dt):
            try:
                popup = NotificationPopup(
                    'message',
                    data,
                    callback=self._handle_message_action
                )
                self.active_notifications.append(popup)
                popup.open()

                # Disable sleep mode screen
                app = App.get_running_app()
                if app and getattr(app, "black_overlay", None) and app.black_overlay.parent:
                    app.black_overlay.dismiss()
                    # relance timer + logs wakeup si tu l'as déjà dans MyApp
                    if hasattr(app, "_on_wakeup"):
                        app._on_wakeup()

                print(f"[NOTIF] Message from {sender}")
            except Exception as e:
                print(f"[NOTIF] ERROR message: {e}")
        
        Clock.schedule_once(_create_popup, 0)

        #ICSO
        log_received_photos()
    
    def _handle_videocall_action(self, action, data):
        """
        Handle video call notification actions
        
        IMPORTANT: Uses exact room name from notification (CASE-SENSITIVE)
        Falls back to settings.json videocall_room if not provided
        """
        self._remove_from_active(data)
        remove_cached_notification('videocall', data)

        # Retirer du tracker
        self.active_videocall_popup = None
        
        if action == 'accept':
            caller = data.get('caller', 'Unknown')
            room = data.get('room')
            
            # ✅ USE EXACT ROOM NAME FROM NOTIFICATION OR FALLBACK TO settings.json
            if not room:
                room = self.videocall_room  # ✅ From settings.json instead of hardcoded 'CoBien1'
                print(f"[NOTIF] ⚠️ No room in notification, using settings.json: '{room}'")
            
            print(f"[NOTIF] ========================================")
            print(f"[NOTIF] 📞 Call accepted")
            print(f"[NOTIF]    From: '{caller}'")
            print(f"[NOTIF]    Room: '{room}' (case-sensitive from settings.json)")
            print(f"[NOTIF] ========================================")
            
            # ✅ CREATE TEMPORARY CONFIG FILE FOR LAUNCHER
            import tempfile
            config_data = {
                'room': room,  # Exact case preserved from settings.json
                'identity': room  # Use room as identity
            }
            
            try:
                # Create temp config file
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.json',
                    delete=False,
                    encoding='utf-8'
                ) as f:
                    json.dump(config_data, f)
                    config_file = f.name
                
                print(f"[NOTIF] 📄 Config file created: {config_file}")
                print(f"[NOTIF]    Room from settings.json: '{room}'")
                
                # Launch videocall_launcher.py with config file
                import subprocess
                import sys
                
                launcher_path = os.path.join(
                    os.path.dirname(__file__), 
                    "..", 
                    "videocall", 
                    "videocall_launcher.py"
                )
                
                launcher_path = os.path.normpath(launcher_path)
                
                if not os.path.exists(launcher_path):
                    print(f"[NOTIF] ❌ ERROR: videocall_launcher.py not found")
                    self.sm.current = 'contacts'
                    return
                
                print(f"[NOTIF] 🚀 Launching videocall_launcher.py")
                print(f"[NOTIF]    Room: '{room}' (from settings.json)")
                
                subprocess.Popen([sys.executable, launcher_path, config_file])
                
                print(f"[NOTIF] ✅ Videocall launcher started")
                log_call_start()
                
            except Exception as e:
                print(f"[NOTIF] ❌ Error launching videocall_launcher: {e}")
                import traceback
                traceback.print_exc()
                self.sm.current = 'contacts'
        
        elif action == 'decline':
            caller = data.get('caller', 'Unknown')
            room = data.get('room', 'Unknown')
            print(f"[NOTIF] ❌ Call declined")
            print(f"[NOTIF]    From: '{caller}', Room: '{room}'")
        
        elif action == 'timeout':
            caller = data.get('caller', 'Unknown')
            room = data.get('room', 'Unknown')
            print(f"[NOTIF] ⏰ Call expired")
            print(f"[NOTIF]    From: '{caller}', Room: '{room}'")
    
    def _handle_event_action(self, action, data):
        """Handle event notification actions"""
        self._remove_from_active(data)
        remove_cached_notification('event', data)
        
        if action == 'ok':
            print(f"[NOTIF] Event '{data['title']}' closed")
        elif action == 'view_calendar':
            print(f"[NOTIF] Opening calendar for '{data['title']}'")
            self.sm.current = 'events'
    
    def _handle_message_action(self, action, data):
        """Handle message notification actions"""
        self._remove_from_active(data)
        remove_cached_notification('message', data)
        
        if action == 'view':
            sender = data.get('sender', '?')
            print(f"[NOTIF] ========================================")
            print(f"[NOTIF] 📥 User clicked 'Ver' on message from '{sender}'")
            
            try:
                # 1. Changer d'écran
                print("[NOTIF] 🔄 Switching to board screen...")
                self.sm.current = 'board'
                print("[NOTIF] ✅ Switched to board screen")
                
                # 2. Attendre que l'écran soit affiché, puis recharger et scroller
                def _reload_and_scroll(dt):
                    try:
                        print("[NOTIF] 🔄 _reload_and_scroll() triggered (dt={:.3f})".format(dt))
                        
                        # Récupérer l'écran board
                        board_screen = self.sm.get_screen('board')
                        print(f"[NOTIF] ✅ Got board_screen: {board_screen}")
                        
                        # ✅ APPELER DIRECTEMENT refresh_and_show_last()
                        if hasattr(board_screen, 'refresh_and_show_last'):
                            print("[NOTIF] 🔄 Calling refresh_and_show_last()...")
                            board_screen.refresh_and_show_last()
                            print("[NOTIF] ✅ refresh_and_show_last() completed")
                        else:
                            print("[NOTIF] ⚠️ refresh_and_show_last() not found on board_screen")
                    
                    except Exception as e:
                        print(f"[NOTIF] ❌ Error in _reload_and_scroll: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Attendre 150ms que l'écran soit bien affiché
                print("[NOTIF] ⏱️ Scheduling _reload_and_scroll in 0.15s...")
                Clock.schedule_once(_reload_and_scroll, 0.15)  # ✅ Augmenter à 150ms
                
                print("[NOTIF] ========================================")
            
            except Exception as e:
                print(f"[NOTIF] ❌ Error switching to board: {e}")
                import traceback
                traceback.print_exc()
        
        elif action == 'later':
            sender = data.get('sender', '?')
            print(f"[NOTIF] ⏰ Message from '{sender}' postponed")
    
    def _remove_from_active(self, data):
        """Remove notification from active list"""
        self.active_notifications = [
            n for n in self.active_notifications 
            if n.data != data
        ]
    
    def clear_all(self):
        """Close all active notifications"""
        for popup in self.active_notifications:
            popup.dismiss()
        self.active_notifications.clear()
    
    def show_missed_call_notification(self, caller: str, time_str: str):
        """
        Affiche une notification d'appel manqué avec le nom de l'appelant.
        
        Args:
            caller: Nom de la personne qui a appelé (CASE-SENSITIVE, ex: "Ana")
            time_str: Heure de l'appel (ex: "15:30")
        
        Note: Caller name preserves exact case
        """
        from kivy.uix.modalview import ModalView
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.metrics import dp, sp
        from kivy.graphics import Color, RoundedRectangle, Line
        from translation import _
        
        print(f"[NOTIF] ========================================")
        print(f"[NOTIF] 📞 Missed call notification")
        print(f"[NOTIF]    Caller: '{caller}' (case-sensitive)")
        print(f"[NOTIF]    Time: {time_str}")
        print(f"[NOTIF] ========================================")
        append_cached_notification("missed_call", {
            "caller": caller,
            "time_str": time_str,
            "timestamp": datetime.now(),
        })
        
        # Fermer la notification "Appel entrant" si elle existe
        if self.active_videocall_popup:
            print("[NOTIF] 🧹 Fermeture notification 'Appel entrant'")
            try:
                self.active_videocall_popup.dismiss()
            except:
                pass
            self.active_videocall_popup = None

        # Créer popup
        popup = ModalView(
            size_hint=(None, None),
            size=(dp(900), dp(500)),
            auto_dismiss=False,
            background='',
            background_color=(0, 0, 0, 0.7)
        )
        
        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(25)
        )
        
        # Background blanc avec bordure
        with container.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(
                pos=container.pos,
                size=container.size,
                radius=[dp(24)]
            )
            Color(0, 0, 0, 0.2)
            border = Line(
                rounded_rectangle=(
                    container.x, container.y,
                    container.width, container.height,
                    dp(24)
                ),
                width=3
            )
        
        def _update_bg(*args):
            bg.pos = container.pos
            bg.size = container.size
            border.rounded_rectangle = (
                container.x, container.y,
                container.width, container.height,
                dp(24)
            )
        
        container.bind(pos=_update_bg, size=_update_bg)
        
        container.add_widget(BoxLayout(size_hint_y=0.15))
        
        # Titre
        container.add_widget(Label(
            text=_("Llamada perdida"),
            font_size=sp(42),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(55)
        ))
        
        # Message ligne 1 : Qui a appelé (preserves case)
        container.add_widget(Label(
            text=f"{caller} {_('intentó llamarte')}",
            font_size=sp(32),
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(45),
            halign="center",
            valign="middle"
        ))
        
        # Message ligne 2 : Heure
        container.add_widget(Label(
            text=f"{_('a las')} {time_str}",
            font_size=sp(28),
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None,
            height=dp(40),
            halign="center",
            valign="middle"
        ))
        
        # Spacer
        container.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Bouton OK
        btn_ok = Button(
            text="OK",
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal='',
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(34),
            bold=True
        )
        
        def _close(*args):
            popup.dismiss()
            print(f"[NOTIF] 📞 Missed call notification closed (caller='{caller}')")
        
        btn_ok.bind(on_release=_close)
        
        btn_wrapper = BoxLayout(size_hint_y=None, height=dp(75))
        btn_wrapper.add_widget(BoxLayout())
        btn_wrapper.add_widget(btn_ok)
        btn_wrapper.add_widget(BoxLayout())
        
        container.add_widget(btn_wrapper)
        
        popup.add_widget(container)
        
        # Ouvrir le popup
        popup.open()

        # Disable sleep mode screen
        app = App.get_running_app()
        if app and getattr(app, "black_overlay", None) and app.black_overlay.parent:
            app.black_overlay.dismiss()
            # relance timer + logs wakeup si tu l'as déjà dans MyApp
            if hasattr(app, "_on_wakeup"):
                app._on_wakeup()
        
        print("[NOTIF] ✅ Missed call notification displayed")
