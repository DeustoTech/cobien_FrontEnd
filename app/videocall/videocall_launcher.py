"""Standalone PyQt launcher for browser-based video calls.

This module starts a fullscreen Qt WebEngine window, auto-fills room/device
prompts, notifies backend call acceptance, and records call duration metrics.
"""

import sys
import os
import json
import datetime
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from icso_data.videocall_logger import log_call_end
from config_store import load_section, save_section
from audio.audio_devices import (
    apply_system_audio_devices,
    pa_get_default_sink,
    pa_get_default_source,
    pa_list_sinks,
    pa_list_sources,
    pa_set_default_sink,
    play_test_beep,
)

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QDialog, QComboBox, QLabel, QSizePolicy,
)
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
)

# Allow media permissions without interactive prompts and relax autoplay/WebRTC
# restrictions for kiosk device calls.
_existing_qt_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
_required_qt_flags = [
    "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
]
_merged_qt_flags = " ".join(
    flag for flag in (_existing_qt_flags.split() + _required_qt_flags) if flag
)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _merged_qt_flags

_services_cfg = load_section("services", {})
PORTAL_URL = _services_cfg.get("portal_videocall_url", "https://portal.co-bien.eu/videocall/")
DEVICE_PORTAL_URL = _services_cfg.get("portal_videocall_device_url", "https://portal.co-bien.eu/videocall/device/")
DEVICE_SESSION_URL = _services_cfg.get("device_videocall_session_url", "https://portal.co-bien.eu/api/device-videocall-session/")
BACKEND_URL = _services_cfg.get("portal_call_answered_url", "https://portal.co-bien.eu/api/call-answered/")
DEVICE_API_KEY = (_services_cfg.get("videocall_device_api_key", "") or "").strip()


def _default_config_path() -> str:
    """Return default runtime config path used by video-call launcher.

    Returns:
        Absolute path to unified local config.
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config",
        "config.local.json"
    )


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load launcher runtime config from JSON file.

    Args:
        config_path (Optional[str]): Config path override.

    Returns:
        Dict[str, Any]: Parsed config or fallback defaults.

    Raises:
        No exception is propagated. Invalid paths and parse errors are handled
        by returning default values.
    """
    selected_path = config_path or _default_config_path()

    try:
        with open(selected_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            print(f"[VIDEOCALL] Config loaded from {selected_path}")
            return config
    except Exception as e:
        print(f"[VIDEOCALL] Config error ({selected_path}): {e}")
        settings_cfg = load_section("settings", {}) or {}
        return {
            "device_id": settings_cfg.get("device_id", "CoBien1"),
            "videocall_room": settings_cfg.get("videocall_room", "CoBien1"),
        }


def resolve_runtime_config(argv: Optional[list] = None) -> Tuple[Dict[str, Any], str, str]:
    """Resolve runtime config and derive room/device names from CLI args.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Tuple containing:
        - Parsed config dictionary.
        - Room name used by the video portal.
        - Device name reported to backend.
    """
    argv = argv or sys.argv
    config_path = argv[1] if len(argv) > 1 and argv[1] else None
    config = load_config(config_path)
    settings_cfg = config.get("settings") if isinstance(config.get("settings"), dict) else {}
    room_name = (
        config.get("room")
        or config.get("videocall_room")
        or settings_cfg.get("videocall_room")
        or settings_cfg.get("device_id")
        or "CoBien1"
    )
    device_name = (
        config.get("identity")
        or config.get("device_id")
        or settings_cfg.get("device_id")
        or room_name
    )
    return config, room_name, device_name

def notify_backend_call_answered(room_name: str, device_name: str) -> None:
    """Notify backend that the call has been accepted by local device.

    Args:
        room_name (str): Video-call room identifier.
        device_name (str): Device identity reported to backend.

    Returns:
        None.

    Raises:
        No exception is propagated. Network/parse errors are logged.
    """
    import urllib.request
    import urllib.error
    
    try:
        payload = json.dumps({
            "room": room_name,
            "device": device_name
        }).encode('utf-8')
        
        req = urllib.request.Request(
            BACKEND_URL,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        print(f"[VIDEOCALL] Sending call_answered to backend for room '{room_name}'")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('success'):
                print(f"[VIDEOCALL] Backend notified successfully")
            else:
                print(f"[VIDEOCALL] Unexpected backend response: {result}")
    
    except urllib.error.URLError as e:
        print(f"[VIDEOCALL] Network error: {e}")
    except Exception as e:
        print(f"[VIDEOCALL] Backend notification error: {e}")


def request_device_session(room_name: str, device_name: str) -> Optional[Dict[str, Any]]:
    """Request a trusted device bootstrap session from backend."""
    import urllib.request
    import urllib.error

    if not DEVICE_API_KEY:
        print("[VIDEOCALL] No device API key configured; using standard portal flow")
        return None

    payload = json.dumps(
        {
            "device_id": device_name,
            "room": room_name,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        DEVICE_SESSION_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-DEVICE-ID": device_name,
            "X-DEVICE-KEY": DEVICE_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            call_answered_url = str(data.get("call_answered_url") or "").strip()
            if call_answered_url:
                global BACKEND_URL
                BACKEND_URL = call_answered_url
            print(f"[VIDEOCALL] Device session created for room '{data.get('room_name', room_name)}'")
            return data
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        print(f"[VIDEOCALL] ❌ Device session rejected: HTTP {e.code} {detail}")
    except urllib.error.URLError as e:
        print(f"[VIDEOCALL] ❌ Device session network error: {e}")
    except Exception as e:
        print(f"[VIDEOCALL] ❌ Device session error: {e}")
    return None

# ================================================================
class AudioDialog(QDialog):
    """Modal dialog for audio device selection during a video call.

    Lets the operator pick a PA output sink and input source, test the
    speaker with a beep, and persist the choice back to config so the
    next app start picks it up automatically.
    """

    _STYLE = """
        QDialog  { background:#1e1e1e; color:#eeeeee; font-family:Arial,Helvetica,sans-serif; }
        QLabel   { font-size:16px; }
        QComboBox {
            background:#2d2d2d; color:#eeeeee; border:1px solid #555;
            border-radius:6px; padding:6px 10px; font-size:15px; min-height:36px;
        }
        QComboBox::drop-down { border:none; width:28px; }
        QPushButton {
            border-radius:6px; font-weight:bold; font-size:15px;
            min-height:40px; padding:4px 18px;
        }
        QPushButton#btn_beep  { background:#1565C0; color:white; }
        QPushButton#btn_save  { background:#2E7D32; color:white; }
        QPushButton#btn_close { background:#555;    color:white; }
    """

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de audio")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(self._STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # ── Output (sink) ──────────────────────────────────────────
        layout.addWidget(QLabel("Salida de audio (altavoz):"))
        self._combo_out = QComboBox()
        layout.addWidget(self._combo_out)

        self._btn_beep = QPushButton("▶  Probar altavoz")
        self._btn_beep.setObjectName("btn_beep")
        self._btn_beep.clicked.connect(self._test_beep)
        layout.addWidget(self._btn_beep)

        layout.addSpacing(10)

        # ── Input (source) ─────────────────────────────────────────
        layout.addWidget(QLabel("Entrada de audio (micrófono):"))
        self._combo_in = QComboBox()
        layout.addWidget(self._combo_in)

        layout.addSpacing(16)

        # ── Buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_save = QPushButton("Guardar y aplicar")
        self._btn_save.setObjectName("btn_save")
        self._btn_save.clicked.connect(self._save)

        self._btn_close = QPushButton("Cerrar")
        self._btn_close.setObjectName("btn_close")
        self._btn_close.clicked.connect(self.reject)

        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

        self._sinks: List[Dict[str, str]] = []
        self._sources: List[Dict[str, str]] = []
        self._populate()

    def _populate(self) -> None:
        """Fill combos with current PA sinks/sources; mark active device with ★."""
        try:
            current_sink = pa_get_default_sink()
        except Exception:
            current_sink = ""
        try:
            current_source = pa_get_default_source()
        except Exception:
            current_source = ""

        self._sinks = pa_list_sinks()
        selected_out = 0
        for i, s in enumerate(self._sinks):
            label = f"★ {s['name']}" if s["name"] == current_sink else s["name"]
            self._combo_out.addItem(label, s["name"])
            if s["name"] == current_sink:
                selected_out = i
        self._combo_out.setCurrentIndex(selected_out)

        self._sources = pa_list_sources()
        selected_in = 0
        for i, s in enumerate(self._sources):
            label = f"★ {s['name']}" if s["name"] == current_source else s["name"]
            self._combo_in.addItem(label, s["name"])
            if s["name"] == current_source:
                selected_in = i
        self._combo_in.setCurrentIndex(selected_in)

    def _selected_sink(self) -> str:
        return self._combo_out.currentData() or ""

    def _selected_source(self) -> str:
        return self._combo_in.currentData() or ""

    def _test_beep(self) -> None:
        """Apply the chosen output sink and play a short test beep."""
        sink = self._selected_sink()
        if sink:
            pa_set_default_sink(sink)
        play_test_beep()

    def _save(self) -> None:
        """Apply and persist the selected devices."""
        sink = self._selected_sink()
        source = self._selected_source()
        apply_system_audio_devices(sink, source)

        settings = load_section("settings", {}) or {}
        if sink:
            settings["audio_output_device"] = sink
        if source:
            settings["microphone_device"] = source
        try:
            save_section("settings", settings)
            print(f"[VIDEOCALL] Audio saved: out={sink!r} in={source!r}")
        except Exception as exc:
            print(f"[VIDEOCALL] Warning: could not save audio config: {exc}")

        self.accept()


# ================================================================
class CustomWebEnginePage(QWebEnginePage):
    """QWebEngine page overriding prompts for room/device auto-fill."""

    def __init__(
        self,
        room_name: str,
        device_name: str,
        parent: Optional[Any] = None,
        close_callback: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.prompt_counter = 0
        self.room_name = room_name
        self.device_name = device_name
        self.close_callback = close_callback

    # Autocompleta los dos prompts secuenciales (room y nombre)
    def javaScriptPrompt(self, security_origin: Any, msg: str, default: str) -> Tuple[bool, str]:
        """Auto-answer first two JavaScript prompts (room, then identity).

        Args:
            security_origin: Origin requesting the prompt.
            msg: Prompt message from JavaScript context.
            default: Default value proposed by the page.

        Returns:
            Tuple ``(accepted, value)`` consumed by Qt WebEngine.
        """
        if self.prompt_counter == 0:
            self.prompt_counter += 1
            return True, self.room_name
        elif self.prompt_counter == 1:
            self.prompt_counter += 1
            return True, self.device_name
        return True, (default or "")

    def acceptNavigationRequest(self, url: QUrl, nav_type: Any, is_main_frame: bool) -> bool:
        """Intercept internal close sentinel used by the embedded videocall page."""
        if url.scheme() == "cobien" and url.host() == "call-ended":
            print("[VIDEOCALL] Embedded page requested close")
            if callable(self.close_callback):
                self.close_callback()
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

class MainWindow(QMainWindow):
    """Main full-screen window embedding web-based video-call UI."""

    def __init__(self, room_name: str, device_name: str, session_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.room_name = room_name
        self.device_name = device_name
        self.session_data = session_data or {}
        
        self.setWindowTitle("VIDEOLLAMADA")
        self._call_start_time = datetime.datetime.now()
        
        # Notify backend as soon as call window starts.
        print("[VIDEOCALL] Backend notification: call accepted")
        notify_backend_call_answered(self.room_name, self.device_name)
        
        # Persistent browser profile and cache.
        cache_path = os.path.expanduser("~/.cobien_qtwebengine_cache")
        os.makedirs(cache_path, exist_ok=True)
        profile = QWebEngineProfile.defaultProfile()
        profile.setCachePath(cache_path)
        profile.setPersistentStoragePath(cache_path)

        s = profile.settings()
        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        if hasattr(QWebEngineSettings, "PlaybackRequiresUserGesture"):
            s.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)

        # Web view and customized page.
        self.web_view = QWebEngineView()
        self.page = CustomWebEnginePage(
            self.room_name,
            self.device_name,
            self.web_view,
            close_callback=self._quit_app,
        )
        self.web_view.setPage(self.page)
        self.page.loadStarted.connect(self._show_loading_overlay)
        self.page.loadProgress.connect(self._handle_load_progress)
        self.page.loadFinished.connect(self._handle_load_finished)

        # Grant media permissions automatically.
        self.page.featurePermissionRequested.connect(
            lambda origin, feature: self.page.setFeaturePermission(
                origin, feature, QWebEnginePage.PermissionGrantedByUser
            )
        )

        # Exit button.
        self.button = QPushButton("SALIR")
        self.button.setMinimumHeight(70)
        self.button.setFont(QFont("Arial", 22, QFont.Bold))
        self.button.setStyleSheet(
            "background-color:#E53935; color:white; font-weight:bold; border:none; border-radius:6px;"
        )
        self.button.clicked.connect(self._quit_app)

        # Audio settings button.
        self._btn_audio = QPushButton("🎧  Audio")
        self._btn_audio.setMinimumHeight(70)
        self._btn_audio.setFixedWidth(220)
        self._btn_audio.setFont(QFont("Arial", 18, QFont.Bold))
        self._btn_audio.setStyleSheet(
            "background-color:#1565C0; color:white; font-weight:bold; border:none; border-radius:6px; padding:0 18px;"
        )
        self._btn_audio.clicked.connect(self._open_audio_dialog)

        # Toolbar row: compact audio button and expanding exit button.
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(4)
        toolbar.addWidget(self._btn_audio)
        toolbar.addWidget(self.button)
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setFixedHeight(74)
        toolbar_widget.setStyleSheet("background:#111111;")

        self._web_stack = QWidget()
        self._web_stack.setAttribute(Qt.WA_StyledBackground, True)
        self._web_stack.setStyleSheet("background:#000000;")

        self._loading_overlay = QWidget(self._web_stack)
        self._loading_overlay.setStyleSheet("background:rgba(8, 12, 20, 0.88);")
        overlay_layout = QVBoxLayout(self._loading_overlay)
        overlay_layout.setContentsMargins(48, 48, 48, 48)
        overlay_layout.setSpacing(16)
        overlay_layout.addStretch()

        self._loading_title = QLabel("Conectando videollamada...")
        self._loading_title.setAlignment(Qt.AlignCenter)
        self._loading_title.setFont(QFont("Arial", 28, QFont.Bold))
        self._loading_title.setStyleSheet("color:white;")
        overlay_layout.addWidget(self._loading_title)

        self._loading_subtitle = QLabel("Espera unos segundos. No pulses ningún botón.")
        self._loading_subtitle.setAlignment(Qt.AlignCenter)
        self._loading_subtitle.setFont(QFont("Arial", 18))
        self._loading_subtitle.setStyleSheet("color:#D7E3F4;")
        overlay_layout.addWidget(self._loading_subtitle)

        self._loading_progress = QLabel("Preparando sala...")
        self._loading_progress.setAlignment(Qt.AlignCenter)
        self._loading_progress.setFont(QFont("Arial", 16))
        self._loading_progress.setStyleSheet("color:#8FC3FF;")
        overlay_layout.addWidget(self._loading_progress)
        overlay_layout.addStretch()

        # Main layout.
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar_widget)
        layout.addWidget(self._web_stack)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Kiosk-style window mode.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        
        # Render fullscreen.
        self.showFullScreen()

        # Load portal URL.
        self._load_videocall()
        self._resize_overlay()

    def _open_audio_dialog(self) -> None:
        """Open the audio device selection dialog."""
        dlg = AudioDialog(self)
        dlg.exec_()

    def keyPressEvent(self, event: Any) -> None:
        """Ignore Escape so the embedded call remains in kiosk flow."""
        if event.key() == Qt.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: Any) -> None:
        """Handle native close event by performing graceful quit."""
        self._quit_app()

    def _quit_app(self) -> None:
        """Close app and persist call-duration log entry."""
        if hasattr(self, "_call_start_time") and self._call_start_time:
            duration = int((datetime.datetime.now() - self._call_start_time).total_seconds())
            print(f"[VIDEOCALL] Call duration: {duration}s")
            log_call_end(duration)
        
        QApplication.instance().quit()

    def resizeEvent(self, event: Any) -> None:
        """Keep stacked browser widgets sized to the available space."""
        super().resizeEvent(event)
        self._resize_overlay()

    def _resize_overlay(self) -> None:
        """Resize browser and loading overlay to the central stack area."""
        if not hasattr(self, "_web_stack"):
            return
        rect = self._web_stack.rect()
        self.web_view.setParent(self._web_stack)
        self.web_view.setGeometry(rect)
        self._loading_overlay.setGeometry(rect)
        self._loading_overlay.raise_()

    def _show_loading_overlay(self) -> None:
        """Display in-window loading feedback while the portal opens."""
        self._loading_title.setText("Conectando videollamada...")
        self._loading_subtitle.setText("Espera unos segundos. No pulses ningún botón.")
        self._loading_progress.setText("Cargando interfaz de videollamada...")
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _handle_load_progress(self, progress: int) -> None:
        """Update loading percentage while the portal page is loading."""
        self._loading_progress.setText(f"Cargando interfaz de videollamada... {progress}%")

    def _handle_load_finished(self, ok: bool) -> None:
        """Hide loading feedback or show an error state if the load fails."""
        if ok:
            self._loading_overlay.hide()
            return
        self._loading_title.setText("No se pudo abrir la videollamada")
        self._loading_subtitle.setText("Comprueba la conexión y vuelve a intentarlo.")
        self._loading_progress.setText("La sala no ha terminado de cargar.")
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _load_videocall(self) -> None:
        """Load portal video-call URL into embedded browser."""
        self.page.prompt_counter = 0
        if self.session_data.get("token"):
            fragment = urlencode(
                {
                    "token": self.session_data.get("token", ""),
                    "room": self.session_data.get("room_name", self.room_name),
                    "identity": self.session_data.get("identity", self.device_name),
                }
            )
            target_url = f"{DEVICE_PORTAL_URL}#{fragment}"
        elif DEVICE_API_KEY:
            error_html = f"""
            <html>
              <body style="background:#111;color:#fff;font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="max-width:900px;padding:32px;border:1px solid #444;border-radius:16px;background:#1b1b1b;">
                  <h1 style="margin-top:0;">Video call device access failed</h1>
                  <p>The furniture is configured to enter the videocall without human login, but the backend session could not be created.</p>
                  <p>Please review:</p>
                  <ul>
                    <li><strong>device_id</strong>: {self.device_name}</li>
                    <li><strong>room</strong>: {self.room_name}</li>
                    <li><strong>device session URL</strong>: {DEVICE_SESSION_URL}</li>
                    <li><strong>device portal URL</strong>: {DEVICE_PORTAL_URL}</li>
                    <li><strong>videocall device API key</strong>: configured</li>
                  </ul>
                  <p>The launcher stopped before opening the login-protected web portal to avoid falling back to manual authentication.</p>
                </div>
              </body>
            </html>
            """
            self.web_view.setHtml(error_html, QUrl(DEVICE_PORTAL_URL))
            print("[VIDEOCALL] ❌ Device session missing; refusing fallback to login portal.")
            return
        else:
            target_url = PORTAL_URL
        self.web_view.setUrl(QUrl(target_url))
        print(f"[VIDEOCALL] Loading {target_url}")

def main() -> None:
    """Entrypoint for launching full-screen video-call runtime window."""
    # Apply saved audio device routing before Qt/WebEngine initialises so the
    # browser's WebRTC stack sees the correct PulseAudio default sink/source.
    try:
        _settings = load_section("settings", {}) or {}
        _output_dev = (_settings.get("audio_output_device") or "").strip()
        _input_dev = (_settings.get("microphone_device") or "").strip()
        if _output_dev or _input_dev:
            apply_system_audio_devices(_output_dev, _input_dev)
            print(f"[VIDEOCALL] Audio routing: out={_output_dev!r} in={_input_dev!r}")
    except Exception as _ae:
        print(f"[VIDEOCALL] Warning: could not apply audio devices: {_ae}")

    config, room_name, device_name = resolve_runtime_config()
    session_data = request_device_session(room_name, device_name)
    print(f"[VIDEOCALL] Configuration: room='{room_name}', device='{device_name}'")
    app = QApplication(sys.argv)
    # Escala HiDPI correcta en Mac
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = MainWindow(room_name, device_name, session_data=session_data)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
