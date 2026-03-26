# app_config.py
import json
import os
from kivy.event import EventDispatcher
from kivy.properties import DictProperty


CONFIG_PATH = "settings/settings.json"
MQTT_LOCAL_BROKER = os.getenv("COBIEN_MQTT_LOCAL_BROKER", "localhost")
MQTT_LOCAL_PORT = int(os.getenv("COBIEN_MQTT_LOCAL_PORT", "1883"))
DEFAULT_CONFIG = {
    "language": "es",
    "weather_cities": [],
    "button_colors": {},
    "rfid_actions": {},
    "microphone_device": "",
    "device_id": "CoBien1",
    "videocall_room": "CoBien1",
    "device_location": "Bilbao",
    "joke_category": "general",
    "idle_timeout_sec": 60,
}


def _clone_default_config():
    return {
        "language": DEFAULT_CONFIG["language"],
        "weather_cities": list(DEFAULT_CONFIG["weather_cities"]),
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
    ✅ Configuration avec support du binding pour notifications de changements
    """
    data = DictProperty({})
    
    def __init__(self):
        super().__init__()  # Important pour EventDispatcher
        
        self.config_path = CONFIG_PATH
        self._last_mtime = None
        
        # Créer dossier si nécessaire
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # Charger ou créer config
        if os.path.exists(self.config_path):
            self.load()
            # Ajouter les nouveaux champs si manquants
            self._ensure_device_fields()
        else:
            self.data = self._default_config()
            self.save()
    
    def _default_config(self):
        """Configuration par défaut"""
        return _clone_default_config()
    
    def set_joke_category(self, category):
        """Définit la catégorie de blagues."""
        self.data["joke_category"] = category
        self.save()
    
    def get_joke_category(self):
        """Récupère la catégorie actuelle."""
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
        """Charge la configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            
            # IMPORTANT : Assigner via la property pour déclencher les bindings
            self.data = new_data
            self._last_mtime = os.path.getmtime(self.config_path)
            
            print(f"[CONFIG] ✅ Configuration chargée depuis {self.config_path}")
        except Exception as e:
            print(f"[CONFIG] ⚠️ Erreur lecture config: {e}")
            self.data = self._default_config()
    
    def save(self):
        """Sauvegarde la configuration"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            self._last_mtime = os.path.getmtime(self.config_path)
            print(f"[CONFIG] ✅ Configuration sauvegardée")
        except Exception as e:
            print(f"[CONFIG] ⚠️ Erreur sauvegarde config: {e}")
    
    def get_device_id(self):
        """Retourne l'identifiant du meuble"""
        return self.data.get("device_id", "CoBien1")
    
    def get_videocall_room(self):
        """Retourne la room de videocall"""
        return self.data.get("videocall_room", "CoBien1")
    
    def get_device_location(self):
        """Retourne la localisation du meuble"""
        return self.data.get("device_location", "Bilbao")
    
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
