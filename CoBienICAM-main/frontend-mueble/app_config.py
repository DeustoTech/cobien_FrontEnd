# app_config.py
import json
import os
from kivy.event import EventDispatcher
from kivy.properties import DictProperty


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "settings", "settings.json")
MQTT_LOCAL_BROKER = os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost")
MQTT_LOCAL_PORT = int(os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883"))
BACKEND_BASE_URL = os.getenv("COBIEN_BACKEND_BASE_URL", "http://portal.co-bien.eu")
DEFAULT_DEVICE_ID = os.getenv("COBIEN_DEVICE_ID", "CoBien1")
DEFAULT_VIDEOCALL_ROOM = os.getenv("COBIEN_VIDEOCALL_ROOM", DEFAULT_DEVICE_ID)
DEFAULT_DEVICE_LOCATION = os.getenv("COBIEN_DEVICE_LOCATION", "Bilbao")
DEFAULT_CONFIG = {
    "language": "es",
    "weather_cities": [],
    "weather_primary_city": "",
    "button_colors": {},
    "rfid_actions": {},
    "microphone_device": "",
    "device_id": DEFAULT_DEVICE_ID,
    "videocall_room": DEFAULT_VIDEOCALL_ROOM,
    "device_location": DEFAULT_DEVICE_LOCATION,
    "joke_category": "general",
    "idle_timeout_sec": 60,
}


def _clone_default_config():
    return {
        "language": DEFAULT_CONFIG["language"],
        "weather_cities": list(DEFAULT_CONFIG["weather_cities"]),
        "weather_primary_city": DEFAULT_CONFIG["weather_primary_city"],
        "button_colors": dict(DEFAULT_CONFIG["button_colors"]),
        "rfid_actions": dict(DEFAULT_CONFIG["rfid_actions"]),
        "microphone_device": DEFAULT_CONFIG["microphone_device"],
        "device_id": DEFAULT_CONFIG["device_id"],
        "videocall_room": DEFAULT_CONFIG["videocall_room"],
        "device_location": DEFAULT_CONFIG["device_location"],
        "joke_category": DEFAULT_CONFIG["joke_category"],
        "idle_timeout_sec": DEFAULT_CONFIG["idle_timeout_sec"],
    }

class AppConfig(EventDispatcher):
    """
    ✅ Configuration with binding support for change notifications
    """
    data = DictProperty({})
    
    def __init__(self):
        super().__init__()  # Important pour EventDispatcher
        
        self.config_path = CONFIG_PATH
        self._last_mtime = None
        
        # Create folder if necessary
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # Load or create config
        if os.path.exists(self.config_path):
            self.load()
            # Add new fields if missing
            self._ensure_device_fields()
        else:
            self.data = self._default_config()
            self.save()
    
    def _default_config(self):
        """Default configuration"""
        return _clone_default_config()
    
    def set_joke_category(self, category):
        """Set the joke category."""
        self.data["joke_category"] = category
        self.save()
    
    def get_joke_category(self):
        """Get the current joke category."""
        return self.data.get("joke_category", "general")
    
    def _ensure_device_fields(self):
        """Backfill missing config keys while preserving stored values."""
        defaults = self._default_config()
        modified = False

        for key, default_value in defaults.items():
            if key not in self.data:
                if isinstance(default_value, list):
                    self.data[key] = list(default_value)
                elif isinstance(default_value, dict):
                    self.data[key] = dict(default_value)
                else:
                    self.data[key] = default_value
                print(f"[CONFIG] ✅ Ajout {key} = {self.data[key]}")
                modified = True
        
        if modified:
            self.save()
    
    def load(self):
        """Load configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            
            # IMPORTANT: Assign via the property to trigger bindings
            self.data = new_data
            self._last_mtime = os.path.getmtime(self.config_path)
            
            print(f"[CONFIG] ✅ Configuration chargée depuis {self.config_path}")
        except Exception as e:
            print(f"[CONFIG] ⚠️ Erreur lecture config: {e}")
            self.data = self._default_config()
    
    def save(self):
        """Save configuration"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            self._last_mtime = os.path.getmtime(self.config_path)
            print(f"[CONFIG] ✅ Configuration sauvegardée")
        except Exception as e:
            print(f"[CONFIG] ⚠️ Erreur sauvegarde config: {e}")
    
    def get_device_id(self):
        """Retourne l'identifiant du meuble"""
        return self.data.get("device_id", DEFAULT_DEVICE_ID)
    
    def get_videocall_room(self):
        """Retourne la room de videocall"""
        return self.data.get("videocall_room", DEFAULT_VIDEOCALL_ROOM)
    
    def get_device_location(self):
        """Retourne la localisation du meuble"""
        return self.data.get("device_location", DEFAULT_DEVICE_LOCATION)
    
    def get_idle_timeout(self):
        """
        Récupère le délai de mise en veille (en secondes).
        ✅ RECHARGE le fichier UNIQUEMENT s'il a été modifié.
        
        Returns:
            int: Nombre de secondes avant mise en veille (défaut: 60)
        """
        # Vérifier si le fichier a été modifié
        try:
            current_mtime = os.path.getmtime(self.config_path)
            
            # Charger uniquement si modifié
            if current_mtime != self._last_mtime:
                self.load()
        
        except FileNotFoundError:
            # Fichier n'existe pas, utiliser données en mémoire
            pass
        
        return self.data.get("idle_timeout_sec", 60)

    def get_microphone_device(self):
        return self.data.get("microphone_device", "")

    def set_microphone_device(self, device_name):
        self.data["microphone_device"] = device_name or ""
        self.save()
