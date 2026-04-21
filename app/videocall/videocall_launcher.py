"""Standalone PyQt launcher for browser-based video calls.

This module starts a fullscreen Qt WebEngine window, auto-fills room/device
prompts, notifies backend call acceptance, and records call duration metrics.
"""

import sys
import os
import json
import datetime
from urllib.parse import urlencode
from typing import Any, Dict, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from icso_data.videocall_logger import log_call_end
from config_store import load_section

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
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
            print(f"[VIDEOCALL] ✅ Config cargada desde {selected_path}")
            return config
    except Exception as e:
        print(f"[VIDEOCALL] ⚠️ Erreur config ({selected_path}): {e}")
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
        
        print(f"[VIDEOCALL] 📞 Envoi call_answered au backend...")
        print(f"[VIDEOCALL]    URL: {BACKEND_URL}")
        print(f"[VIDEOCALL]    Room: {room_name}")
        print(f"[VIDEOCALL]    Device: {device_name}")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('success'):
                print(f"[VIDEOCALL] ✅ Backend notifié avec succès")
            else:
                print(f"[VIDEOCALL] ⚠️ Réponse backend: {result}")
    
    except urllib.error.URLError as e:
        print(f"[VIDEOCALL] ❌ Erreur réseau: {e}")
    except Exception as e:
        print(f"[VIDEOCALL] ❌ Erreur notification backend: {e}")


def request_device_session(room_name: str, device_name: str) -> Optional[Dict[str, Any]]:
    """Request a trusted device bootstrap session from backend."""
    import urllib.request
    import urllib.error

    if not DEVICE_API_KEY:
        print("[VIDEOCALL] ℹ️ No device API key configured; using standard portal flow.")
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
            print(f"[VIDEOCALL] ✅ Device session created for room '{data.get('room_name', room_name)}'")
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
class CustomWebEnginePage(QWebEnginePage):
    """QWebEngine page overriding prompts for room/device auto-fill."""

    def __init__(self, room_name: str, device_name: str, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.prompt_counter = 0
        self.room_name = room_name
        self.device_name = device_name

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
        print("[VIDEOCALL] 📞 Notification backend: appel accepté")
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
        self.page = CustomWebEnginePage(self.room_name, self.device_name, self.web_view)
        self.web_view.setPage(self.page)

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

        # Main layout.
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.button)
        layout.addWidget(self.web_view)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Kiosk-style window mode.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        
        # Render fullscreen.
        self.showFullScreen()

        # Load portal URL.
        self._load_videocall()

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
            print(f"[VIDEOCALL] 📊 Durée appel: {duration}s")
            log_call_end(duration)
        
        QApplication.instance().quit()

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
        print(f"[VIDEOCALL] 🌐 Chargement: {target_url}")

def main() -> None:
    """Entrypoint for launching full-screen video-call runtime window."""
    config, room_name, device_name = resolve_runtime_config()
    session_data = request_device_session(room_name, device_name)
    print(f"[VIDEOCALL] ========================================")
    print(f"[VIDEOCALL] Configuration:")
    print(f"[VIDEOCALL]    Room: {room_name}")
    print(f"[VIDEOCALL]    Device: {device_name}")
    print(f"[VIDEOCALL] ========================================")
    app = QApplication(sys.argv)
    # Escala HiDPI correcta en Mac
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = MainWindow(room_name, device_name, session_data=session_data)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
