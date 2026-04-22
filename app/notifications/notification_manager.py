"""
notifications/notification_manager.py
Notification manager for video calls, events, and pizarra messages.
Reads LED/ringtone configuration and sends parameters to the furniture via MQTT.

IMPORTANT: Room names are CASE-SENSITIVE to distinguish between:
- 'CoBien' and 'cobien' (different rooms)
- 'Maria' and 'maria' (different rooms)
"""
from typing import Any, Callable, Dict, List, Optional
import threading
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
import paho.mqtt.publish as publish

# ICSO logging
from icso_data.videocall_logger import log_call_start
from icso_data.notification_logger import log_received_photos, log_added_events

# Import app configuration values (config.local.json)
from app_config import AppConfig, MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

# ========== CENTRALIZED LED CONTROL ==========
from notifications.mqtt_led_sender import send_led_config_from_dict, turn_off_leds
from notifications.notification_runtime import (
    NONE_RINGTONE,
    load_notification_config,
    normalize_ringtone_name,
    play_ringtone_file,
    stop_ringtone,
)

# ========== MQTT TOPICS ==========
TOPIC_EVENTS_RELOAD = "events/reload"
TOPIC_BOARD_RELOAD = "board/reload"

NOTIFICATION_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "notifications",
    "cache",
)
NOTIFICATION_CACHE_FILE = os.path.join(NOTIFICATION_CACHE_DIR, "active_notifications.json")


def _notification_cache_key(kind: Any, data: Any) -> str:
    """Build a stable cache key for one notification payload.

    Args:
        kind: Notification kind identifier (`videocall`, `event`, etc.).
        data: Notification payload.

    Returns:
        str: Deterministic JSON key.
    """
    return json.dumps({"kind": kind, "data": data}, ensure_ascii=False, sort_keys=True, default=str)


def load_cached_notifications() -> List[Dict[str, Any]]:
    """Load persisted active notifications cache.

    Returns:
        List[Dict[str, Any]]: Cached notification entries, empty on failure.
    """
    if not os.path.exists(NOTIFICATION_CACHE_FILE):
        return []
    try:
        with open(NOTIFICATION_CACHE_FILE, "r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
        return payload.get("notifications", [])
    except Exception as e:
        print(f"[NOTIF_CACHE] ⚠️ Error loading cache: {e}")
        return []


def save_cached_notifications(items: List[Dict[str, Any]]) -> None:
    """Persist active notifications cache atomically.

    Args:
        items: Notification cache entries.

    Returns:
        None.
    """
    try:
        os.makedirs(NOTIFICATION_CACHE_DIR, exist_ok=True)
        tmp_path = NOTIFICATION_CACHE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as cache_file:
            json.dump({"notifications": items}, cache_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, NOTIFICATION_CACHE_FILE)
    except Exception as e:
        print(f"[NOTIF_CACHE] ⚠️ Error saving cache: {e}")


def append_cached_notification(kind: str, data: Dict[str, Any]) -> None:
    """Insert or update one notification entry in cache.

    Args:
        kind: Notification kind.
        data: Notification payload.

    Returns:
        None.
    """
    cached = load_cached_notifications()
    entry_key = _notification_cache_key(kind, data)
    filtered = [item for item in cached if _notification_cache_key(item.get("kind"), item.get("data")) != entry_key]
    filtered.insert(0, {"kind": kind, "data": data, "saved_at": datetime.now().isoformat()})
    save_cached_notifications(filtered[:50])


def remove_cached_notification(kind: str, data: Dict[str, Any]) -> None:
    """Remove one notification entry from cache.

    Args:
        kind: Notification kind.
        data: Notification payload used to derive unique cache key.

    Returns:
        None.
    """
    entry_key = _notification_cache_key(kind, data)
    cached = load_cached_notifications()
    filtered = [item for item in cached if _notification_cache_key(item.get("kind"), item.get("data")) != entry_key]
    if len(filtered) != len(cached):
        save_cached_notifications(filtered)

def play_notification_ringtone(notification_type: str) -> None:
    """Play the configured ringtone for a notification type.

    Args:
        notification_type (str): Notification key (for example:
            ``videollamada``, ``nuevo_evento``, or ``nueva_foto``).

    Returns:
        None.
    """
    config = load_notification_config()
    
    if notification_type not in config:
        print(f"[RINGTONE] Type '{notification_type}' not found in config")
        return
    
    ringtone = normalize_ringtone_name(config[notification_type].get("ringtone"))
    
    if ringtone == NONE_RINGTONE or not ringtone or ringtone.strip() == "":
        print(f"[RINGTONE] No ringtone configured for {notification_type}")
        return
    
    print(f"[RINGTONE] Playing: {ringtone} for {notification_type}")
    play_ringtone_file(ringtone)

def send_led_mqtt(notification_type: str) -> None:
    """Send LED configuration for a notification type over MQTT.

    Args:
        notification_type (str): Notification key (for example:
            ``videollamada``, ``nuevo_evento``, or ``nueva_foto``).

    Returns:
        None.
    """
    print(f"[NOTIF_MANAGER] Sending LED for type: {notification_type}")
    
    config = load_notification_config()
    
    if notification_type not in config:
        print(f"[NOTIF_MANAGER] ⚠ Type '{notification_type}' not found in config")
        return
    
    params = config[notification_type]
    
    # Use centralized module
    send_led_config_from_dict(params)

def publish_events_reload() -> None:
    """Publish MQTT event requesting events screen reload.

    Returns:
        None.
    """
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

def publish_board_reload() -> None:
    """Publish MQTT event requesting board screen reload.

    Returns:
        None.
    """
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

def publish_board_reload_last() -> None:
    """Request board reload and auto-focus on the latest message.

    Returns:
        None.
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
    
    def __init__(
        self,
        notification_type: str,
        data: Dict[str, Any],
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a typed notification popup.

        Args:
            notification_type: Popup kind (`videocall`, `event`, `message`).
            data: Popup payload.
            callback: Action callback invoked on user choice.
            **kwargs: Standard Kivy `ModalView` kwargs.
        """
        print(f"[NOTIF] __init__ NotificationPopup for {notification_type}")
        
        # Ensure translation context is applied before building UI.
        app = App.get_running_app()
        current_lang = app.cfg.data.get("language", "es")
        change_language(current_lang)
        print(f"[NOTIF] 🌍 Language forced to: {current_lang} before popup build")
        
        super().__init__(**kwargs)
        print(f"[NOTIF] super().__init__ OK")
        
        self.notification_type = notification_type
        self.data = data
        self.callback = callback
        
        # Modal setup
        self.size_hint = (0.9, 0.7)
        self.auto_dismiss = False
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0)
        print(f"[NOTIF] Modal configuration OK")
        
        # Build translated content using the active language.
        print(f"[NOTIF] Starting build_content...")
        self.content = self._build_content()
        print(f"[NOTIF] build_content OK")
        
        self.add_widget(self.content)
        print(f"[NOTIF] add_widget OK")
        
        print(f"[NOTIF] __init__ completed successfully")
    
    def _build_content(self) -> BoxLayout:
        """Build popup body according to notification type.

        Returns:
            BoxLayout: Built content layout.
        """
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


class CallLaunchingPopup(ModalView):
    """Blocking progress popup shown while the external videocall window starts."""

    def __init__(self, caller: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size_hint = (0.72, 0.34)
        self.auto_dismiss = False
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.45)

        main_layout = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(18))
        with main_layout.canvas.before:
            Color(0.97, 0.98, 1, 1)
            self.bg_rect = RoundedRectangle(pos=main_layout.pos, size=main_layout.size, radius=[dp(22)])
        main_layout.bind(pos=self._update_rect, size=self._update_rect)

        title = Label(
            text=_("Abriendo videollamada"),
            font_size=sp(36),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(52),
        )
        subtitle = Label(
            text=_("Espera unos segundos, no pulses ningún botón."),
            font_size=sp(24),
            color=(0.25, 0.25, 0.25, 1),
            size_hint_y=None,
            height=dp(44),
        )
        detail_text = _("Conectando con {}...").format(caller) if caller else _("Preparando la llamada...")
        detail = Label(
            text=detail_text,
            font_size=sp(22),
            color=(0.35, 0.35, 0.35, 1),
            size_hint_y=None,
            height=dp(40),
        )

        main_layout.add_widget(BoxLayout())
        main_layout.add_widget(title)
        main_layout.add_widget(subtitle)
        main_layout.add_widget(detail)
        main_layout.add_widget(BoxLayout())

        self.add_widget(main_layout)

    def _update_rect(self, instance: Any, _value: Any) -> None:
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
    
    def _build_videocall_content(self, main_layout: BoxLayout) -> BoxLayout:
        """Build popup content for an incoming video call."""
        caller = self.data.get('caller', _('Desconocido'))
        
        # Icon at top
        icon_path = "data/images/videollamada.png"
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
    
    def _build_event_content(self, main_layout: BoxLayout) -> BoxLayout:
        """Build popup content for a new event notification."""
        title_text = self.data.get('title', _('Nuevo evento'))
        date_str = self.data.get('date', '')
        
        # Icon
        icon_path = "data/images/eventos.png"
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
    
    def _build_message_content(self, main_layout: BoxLayout) -> BoxLayout:
        """Build popup content for a new board message notification."""
        sender = self.data.get('sender', _('Desconocido'))
        has_image = self.data.get('has_image', False)
        has_text = self.data.get('has_text', False)
        
        # Icon
        icon_path = "data/images/pizarra.png"
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
    
    def _update_rect(self, *args: Any) -> None:
        """Synchronize popup rounded rectangles with layout geometry."""
        # Update white background
        self.bg_rect.pos = self.content.pos
        self.bg_rect.size = self.content.size
        
        # Update border (slightly bigger)
        self.border_rect.pos = (self.content.x - 3, self.content.y - 3)
        self.border_rect.size = (self.content.width + 6, self.content.height + 6)
    
    def _on_action(self, action: str) -> None:
        """Handle popup actions and delegate via callback."""
        # ========== STOP SOUND AND LEDS ==========
        stop_ringtone()
        turn_off_leds()
        
        if self.callback:
            self.callback(action, self.data)
        
        self.dismiss()

class NotificationManager:
    """Central runtime manager for all user-facing notifications.

    The manager coordinates:
    - Popups and user actions.
    - Ringtone playback.
    - LED signaling via MQTT.
    - Screen navigation side-effects.
    - Notification cache bookkeeping.
    """
    
    def __init__(self, screen_manager: Any, main_screen: Any) -> None:
        """Initialize notification manager.

        Args:
            screen_manager: Kivy `ScreenManager`.
            main_screen: Main screen instance reference.
        """
        self.sm = screen_manager
        self.main_screen = main_screen
        self.active_notifications = []
        
        # ✅ LOAD CONFIGURATION FROM config.local.json
        self.cfg = AppConfig()
        self.device_id = self.cfg.get_device_id()
        self.videocall_room = self.cfg.get_videocall_room()
        self.device_location = self.cfg.get_device_location()
        
        print("[NOTIF_MANAGER] ========================================")
        print("[NOTIF_MANAGER] 📋 Configuration loaded from config.local.json:")
        print(f"[NOTIF_MANAGER]    Device ID: {self.device_id}")
        print(f"[NOTIF_MANAGER]    Videocall Room: {self.videocall_room}")
        print(f"[NOTIF_MANAGER]    Location: {self.device_location}")
        print("[NOTIF_MANAGER] ========================================")
        
        # ✅ CASE-SENSITIVE notification history
        # Keys format: "videocall_{caller}_{room}_{minute}"
        # Preserves exact case of caller and room names
        self.notification_history = {}

        # Tracker du popup d'appel entrant actif (case-sensitive)
        # Tracker for the active incoming call popup (case-sensitive)
        self.active_videocall_popup = None
        self.active_call_process = None
        self.call_launching_popup = None
        
        print("[NOTIF_MANAGER] ✅ Notification manager initialized (CASE-SENSITIVE)")

    def _wake_app_for_notification(self) -> None:
        """Wake the furniture UI if a notification arrives during black overlay."""
        app = App.get_running_app()
        if not app:
            return

        try:
            if getattr(app, "black_overlay", None) and app.black_overlay.parent:
                app.black_overlay.dismiss()
        except Exception as exc:
            print(f"[NOTIF] ⚠️ Could not dismiss black overlay for incoming notification: {exc}")

        try:
            if hasattr(app, "_on_wakeup"):
                app._on_wakeup()
            elif hasattr(app, "_reset_idle_timer"):
                app._reset_idle_timer()
        except Exception as exc:
            print(f"[NOTIF] ⚠️ Could not restore runtime after incoming notification: {exc}")
    
    def show_videocall_notification(self, caller: str, room: Optional[str] = None) -> None:
        """Display an incoming video call notification popup.

        Args:
            caller (str): Caller name (case-sensitive).
            room (Optional[str]): Target room name (case-sensitive). If missing,
                runtime fallback logic uses configured local room.

        Returns:
            None.

        Raises:
            No exception is propagated. Runtime errors are logged.

        Note:
            ``CoBien`` and ``cobien`` are intentionally treated as different rooms.
        """
        if self.active_call_process and self.active_call_process.poll() is None:
            print(f"[NOTIF] ⚠️ Active call already running, incoming call ignored")
            print(f"[NOTIF]    Caller: '{caller}'")
            print(f"[NOTIF]    Room: '{room}'")
            return

        # ✅ CASE-SENSITIVE duplicate check
        # Include both caller AND room to distinguish between different calls
        current_time = datetime.now().strftime('%Y%m%d%H%M')
        notif_key = f"videocall_{caller}_{room}_{current_time}"
        cutoff = datetime.now().timestamp() - (60 * 10)
        self.notification_history = {
            key: value
            for key, value in self.notification_history.items()
            if value.timestamp() >= cutoff
        }
        
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

        # Close previous popup if it exists
        if self.active_videocall_popup:
            print("[NOTIF] 🧹 Closing previous popup")
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

                # Save reference
                self.active_videocall_popup = popup

                self.active_notifications.append(popup)
                self._wake_app_for_notification()
                popup.open()

                print(f"[NOTIF] ✅ Popup displayed for '{caller}' → room '{room}'")
            except Exception as e:
                print(f"[NOTIF] ❌ ERROR creating popup: {e}")
                import traceback
                traceback.print_exc()
        
        Clock.schedule_once(_create_popup, 0)
    
    def show_event_notification(self, title: str, date_str: str) -> None:
        """Show a new event notification popup.

        Args:
            title: Event title.
            date_str: Human-readable event date.

        Returns:
            None.
        """
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
                self._wake_app_for_notification()
                popup.open()

                print(f"[NOTIF] Event: {title}")
            except Exception as e:
                print(f"[NOTIF] ERROR event: {e}")
        
        Clock.schedule_once(_create_popup, 0)

        #ICSO
        log_added_events()
    
    def show_message_notification(
        self,
        sender: str,
        has_image: bool = False,
        has_text: bool = False,
    ) -> None:
        """Show a new board-message notification popup.

        Args:
            sender: Sender display name.
            has_image: Whether payload includes image content.
            has_text: Whether payload includes text content.

        Returns:
            None.
        """
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
                self._wake_app_for_notification()
                popup.open()

                print(f"[NOTIF] Message from {sender}")
            except Exception as e:
                print(f"[NOTIF] ERROR message: {e}")
        
        Clock.schedule_once(_create_popup, 0)

        #ICSO
        log_received_photos()
    
    def _handle_videocall_action(self, action: str, data: Dict[str, Any]) -> None:
        """Handle user actions from an incoming video-call notification.

        Args:
            action (str): User action (`accept`, `decline`, `timeout`).
            data (Dict[str, Any]): Notification payload.

        Returns:
            None.

        Raises:
            No exception is propagated. Launch/navigation errors are logged.

        Note:
            Uses the exact room name from notification payload (case-sensitive),
            and falls back to configured `videocall_room` when unavailable.
        """
        self._remove_from_active(data)
        remove_cached_notification('videocall', data)

        # Retirer du tracker
        self.active_videocall_popup = None
        
        if action == 'accept':
            caller = data.get('caller', 'Unknown')
            room = data.get('room')
            
            # ✅ USE EXACT ROOM NAME FROM NOTIFICATION OR FALLBACK TO config.local.json
            if not room:
                room = self.videocall_room  # ✅ From config.local.json instead of hardcoded 'CoBien1'
                print(f"[NOTIF] ⚠️ No room in notification, using config.local.json: '{room}'")
            
            print(f"[NOTIF] ========================================")
            print(f"[NOTIF] 📞 Call accepted")
            print(f"[NOTIF]    From: '{caller}'")
            print(f"[NOTIF]    Room: '{room}' (case-sensitive from config.local.json)")
            print(f"[NOTIF] ========================================")
            
            # ✅ CREATE TEMPORARY CONFIG FILE FOR LAUNCHER
            import tempfile
            device_id = self.cfg.get_device_id()
            config_data = {
                'room': room,
                'identity': device_id,
                'device_id': device_id,
                'videocall_room': room,
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
                print(f"[NOTIF]    Room from config.local.json: '{room}'")
                
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
                print(f"[NOTIF]    Room: '{room}' (from config.local.json)")

                self._show_videocall_launching_popup(caller)
                self._prepare_runtime_for_videocall()
                self.active_call_process = subprocess.Popen([sys.executable, launcher_path, config_file])
                self._cleanup_videocall_temp_file_later(config_file, self.active_call_process)
                Clock.schedule_once(lambda _dt: self._dismiss_videocall_launching_popup(), 1.8)
                
                print(f"[NOTIF] ✅ Videocall launcher started")
                log_call_start()
                
            except Exception as e:
                self._dismiss_videocall_launching_popup()
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

    def _cleanup_videocall_temp_file_later(self, temp_path: str, process: Any) -> None:
        """Remove temporary launcher config once the call process finishes."""
        def _cleanup() -> None:
            try:
                process.wait(timeout=None)
            except Exception:
                pass
            self.active_call_process = None
            Clock.schedule_once(lambda _dt: self._dismiss_videocall_launching_popup(), 0)
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as exc:
                print(f"[NOTIF] ⚠️ Could not remove temporary videocall config {temp_path}: {exc}")
            self._restore_runtime_after_videocall()

        threading.Thread(target=_cleanup, daemon=True).start()

    def _prepare_runtime_for_videocall(self) -> None:
        """Pause idle blackout behaviour before opening the external call window."""
        app = App.get_running_app()
        if not app:
            return

        try:
            idle_event = getattr(app, "_idle_event", None)
            if idle_event:
                idle_event.cancel()
                app._idle_event = None
        except Exception as exc:
            print(f"[NOTIF] ⚠️ Could not pause idle timer before videocall: {exc}")

        try:
            if getattr(app, "black_overlay", None) and app.black_overlay.parent:
                app.black_overlay.dismiss()
        except Exception as exc:
            print(f"[NOTIF] ⚠️ Could not dismiss black overlay before videocall: {exc}")

    def _show_videocall_launching_popup(self, caller: str) -> None:
        """Show a blocking progress popup while the external call UI appears."""
        def _open(_dt: float) -> None:
            try:
                self._dismiss_videocall_launching_popup()
                popup = CallLaunchingPopup(caller=caller)
                popup.open()
                self.call_launching_popup = popup
            except Exception as exc:
                print(f"[NOTIF] ⚠️ Could not show videocall launching popup: {exc}")

        Clock.schedule_once(_open, 0)

    def _dismiss_videocall_launching_popup(self) -> None:
        """Close the temporary progress popup if it is visible."""
        popup = getattr(self, "call_launching_popup", None)
        if not popup:
            return
        try:
            popup.dismiss()
        except Exception as exc:
            print(f"[NOTIF] ⚠️ Could not dismiss videocall launching popup: {exc}")
        self.call_launching_popup = None

    def _restore_runtime_after_videocall(self) -> None:
        """Restore Kivy visibility and idle handling once the call window closes."""
        def _restore(_dt: float) -> None:
            app = App.get_running_app()
            if not app:
                return

            self._dismiss_videocall_launching_popup()

            try:
                if getattr(app, "black_overlay", None) and app.black_overlay.parent:
                    app.black_overlay.dismiss()
            except Exception as exc:
                print(f"[NOTIF] ⚠️ Could not dismiss black overlay after videocall: {exc}")

            try:
                if hasattr(app, "_on_wakeup"):
                    app._on_wakeup()
                elif hasattr(app, "_reset_idle_timer"):
                    app._reset_idle_timer()
            except Exception as exc:
                print(f"[NOTIF] ⚠️ Could not restore idle timer after videocall: {exc}")

        Clock.schedule_once(_restore, 0)
    
    def _handle_event_action(self, action: str, data: Dict[str, Any]) -> None:
        """Handle event-notification user actions."""
        self._remove_from_active(data)
        remove_cached_notification('event', data)
        
        if action == 'ok':
            print(f"[NOTIF] Event '{data['title']}' closed")
        elif action == 'view_calendar':
            print(f"[NOTIF] Opening calendar for '{data['title']}'")
            self.sm.current = 'events'
    
    def _handle_message_action(self, action: str, data: Dict[str, Any]) -> None:
        """Handle message-notification user actions."""
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
    
    def _remove_from_active(self, data: Dict[str, Any]) -> None:
        """Remove one notification payload from active in-memory list."""
        self.active_notifications = [
            n for n in self.active_notifications 
            if n.data != data
        ]
    
    def clear_all(self) -> None:
        """Close all active popup notifications and clear active list."""
        for popup in self.active_notifications:
            popup.dismiss()
        self.active_notifications.clear()

    def show_system_info_notification(
        self,
        title_text: str,
        message_text: str,
        version_text: Optional[str] = None,
    ) -> None:
        """Show a timed system information popup.

        Args:
            title_text: Popup title.
            message_text: Popup message.
            version_text: Optional version string shown under message.

        Returns:
            None.
        """
        from kivy.uix.modalview import ModalView
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.metrics import dp, sp
        from kivy.graphics import Color, RoundedRectangle, Line

        print("[NOTIF] ========================================")
        print("[NOTIF] System info notification")
        print(f"[NOTIF]    Title: {title_text}")
        print(f"[NOTIF]    Message: {message_text}")
        print("[NOTIF] ========================================")

        popup = ModalView(
            size_hint=(None, None),
            size=(dp(980), dp(520)),
            auto_dismiss=False,
            background='',
            background_color=(0, 0, 0, 0.7)
        )

        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(25)
        )

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
        container.add_widget(Label(
            text=title_text,
            font_size=sp(42),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(60),
            halign="center",
            valign="middle"
        ))
        container.add_widget(Label(
            text=message_text,
            font_size=sp(30),
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            height=dp(90),
            halign="center",
            valign="middle"
        ))
        if version_text:
            container.add_widget(Label(
                text=f"v{version_text}",
                font_size=sp(24),
                color=(0.3, 0.3, 0.3, 1),
                size_hint_y=None,
                height=dp(40),
                halign="center",
                valign="middle"
            ))
        container.add_widget(BoxLayout(size_hint_y=0.2))

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
            if popup.parent:
                popup.dismiss()
                print("[NOTIF] System info notification closed")

        btn_ok.bind(on_release=_close)

        btn_wrapper = BoxLayout(size_hint_y=None, height=dp(75))
        btn_wrapper.add_widget(BoxLayout())
        btn_wrapper.add_widget(btn_ok)
        btn_wrapper.add_widget(BoxLayout())
        container.add_widget(btn_wrapper)

        popup.add_widget(container)
        self._wake_app_for_notification()
        popup.open()
        Clock.schedule_once(lambda dt: _close(), 10)
    
    def show_missed_call_notification(self, caller: str, time_str: str):
        """
        Affiche une notification d'appel manqué avec le nom de l'appelant.
        
        Args:
            caller: Nom de la personne qui a appelé (CASE-SENSITIVE, ex: "Ana")
            time_str: Heure de l'appel (ex: "15:30")
        
        Note: Caller name preserves exact case

        Returns:
            None.
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
        if self.active_call_process and self.active_call_process.poll() is not None:
            self.active_call_process = None

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
        self._wake_app_for_notification()
        popup.open()
        
        print("[NOTIF] ✅ Missed call notification displayed")
