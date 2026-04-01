# videocall/videocall_launcher.py
import sys
import os
import json
import datetime

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

# Permitir cámara/micrófono sin pedir permiso
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-fake-ui-for-media-stream"

_services_cfg = load_section("services", {})
PORTAL_URL = _services_cfg.get("portal_videocall_url", "https://portal.co-bien.eu/videocall/")
BACKEND_URL = _services_cfg.get("portal_call_answered_url", "https://portal.co-bien.eu/videocall/call-answered/")


def _default_config_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "settings",
        "settings.json"
    )


def load_config(config_path=None):
    selected_path = config_path or _default_config_path()

    try:
        with open(selected_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            print(f"[VIDEOCALL] ✅ Config cargada desde {selected_path}")
            return config
    except Exception as e:
        print(f"[VIDEOCALL] ⚠️ Erreur config ({selected_path}): {e}")
        return {"device_id": "CoBien1", "videocall_room": "CoBien1"}


def resolve_runtime_config(argv=None):
    argv = argv or sys.argv
    config_path = argv[1] if len(argv) > 1 and argv[1] else None
    config = load_config(config_path)
    room_name = config.get("room") or config.get("videocall_room") or "CoBien1"
    device_name = config.get("identity") or config.get("device_id") or room_name
    return config, room_name, device_name

# ========== Fonction pour notifier le backend ==========
def notify_backend_call_answered(room_name: str, device_name: str):
    """
    Envoie une requête HTTP au backend pour signaler que l'appel a été décroché.
    
    Args:
        room_name: Nom de la room Twilio
        device_name: Identifiant du meuble
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

# ================================================================
class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, room_name, device_name, parent=None):
        super().__init__(parent)
        self.prompt_counter = 0
        self.room_name = room_name
        self.device_name = device_name

    # Autocompleta los dos prompts secuenciales (room y nombre)
    def javaScriptPrompt(self, security_origin, msg, default):
        if self.prompt_counter == 0:
            self.prompt_counter += 1
            return True, self.room_name
        elif self.prompt_counter == 1:
            self.prompt_counter += 1
            return True, self.device_name
        return True, (default or "")

class MainWindow(QMainWindow):
    def __init__(self, room_name, device_name):
        super().__init__()
        self.room_name = room_name
        self.device_name = device_name
        
        self.setWindowTitle("VIDEOLLAMADA")
        self._call_start_time = datetime.datetime.now()
        
        # ✅ NOTIFIER LE BACKEND DÈS LE DÉMARRAGE
        print("[VIDEOCALL] 📞 Notification backend: appel accepté")
        notify_backend_call_answered(self.room_name, self.device_name)
        
        # Perfil/caché persistente
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

        # Vista + página
        self.web_view = QWebEngineView()
        self.page = CustomWebEnginePage(self.room_name, self.device_name, self.web_view)
        self.web_view.setPage(self.page)

        # Conceder permisos de cámara/mic de forma automática
        self.page.featurePermissionRequested.connect(
            lambda origin, feature: self.page.setFeaturePermission(
                origin, feature, QWebEnginePage.PermissionGrantedByUser
            )
        )

        # Botón salir
        self.button = QPushButton("SALIR")
        self.button.setMinimumHeight(70)
        self.button.setFont(QFont("Arial", 22, QFont.Bold))
        self.button.setStyleSheet(
            "background-color:#E53935; color:white; font-weight:bold; border:none; border-radius:6px;"
        )
        self.button.clicked.connect(self._quit_app)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.button)
        layout.addWidget(self.web_view)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Modo pantalla completa tipo kiosk
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        
        # Mostrar en pantalla completa
        self.showFullScreen()

        # Cargar videollamada
        self._load_videocall()

    # Tecla Esc para salir rápidamente si fuese necesario
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._quit_app()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._quit_app()

    def _quit_app(self):
        """Quitter l'application et logger la durée"""
        if hasattr(self, "_call_start_time") and self._call_start_time:
            duration = int((datetime.datetime.now() - self._call_start_time).total_seconds())
            print(f"[VIDEOCALL] 📊 Durée appel: {duration}s")
            log_call_end(duration)
        
        QApplication.instance().quit()

    def _load_videocall(self):
        self.page.prompt_counter = 0
        self.web_view.setUrl(QUrl(PORTAL_URL))
        print(f"[VIDEOCALL] 🌐 Chargement: {PORTAL_URL}")

def main():
    config, room_name, device_name = resolve_runtime_config()
    print(f"[VIDEOCALL] ========================================")
    print(f"[VIDEOCALL] Configuration:")
    print(f"[VIDEOCALL]    Room: {room_name}")
    print(f"[VIDEOCALL]    Device: {device_name}")
    print(f"[VIDEOCALL] ========================================")
    app = QApplication(sys.argv)
    # Escala HiDPI correcta en Mac
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = MainWindow(room_name, device_name)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
