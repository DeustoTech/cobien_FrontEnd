import json
import os

class SettingsScreen(Screen):
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        Builder.load_string(KV)
        from kivy.factory import Factory
        self.add_widget(Factory.SettingsRoot())

class SettingsManager:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "settings.json")

        if not os.path.exists(self.config_path):
            self._create_default_config()

        self.data = self.load()

    def _create_default_config(self):
        default = {
            "language": "fr",
            "weather_cities": [],          # stockées aussi en .txt si besoin
            "button_color": [1, 1, 1, 1],
            "led_color": [1, 1, 1],
            "ringtone": "default.mp3",
            "rfid_actions": {}             # {"card_uid": "action_name"}
        }

        with open(self.config_path, "w") as f:
            json.dump(default, f, indent=4)

    def load(self):
        with open(self.config_path, "r") as f:
            return json.load(f)

    def save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.data, f, indent=4)

    # ---------------- LANGUAGE ----------------
    def set_language(self, lang):
        self.data["language"] = lang
        self.save()

    # ---------------- WEATHER ----------------
    def set_weather_cities(self, cities):
        self.data["weather_cities"] = cities
        self.save()

        # Sauvegarde parallèle dans un fichier .txt
        txt_path = os.path.join(os.path.dirname(__file__), "config_weather.txt")
        with open(txt_path, "w") as f:
            for city in cities:
                f.write(city + "\n")

    # ---------------- UI COLORS ----------------
    def set_button_color(self, rgba):
        self.data["button_color"] = rgba
        self.save()

    def set_led_color(self, rgb):
        self.data["led_color"] = rgb
        self.save()

    # ---------------- RINGTONES ----------------
    def set_ringtone(self, filename):
        self.data["ringtone"] = filename
        self.save()

    # ---------------- RFID ----------------
    def set_rfid_action(self, uid, action):
        """
        Enregistre une action RFID dans le JSON et dans config_rfid.txt
        
        Args:
            uid: ID de la carte RFID (int ou str)
            action: Texte de l'action (ex: "météo: Paris", "evenements", "principal")
        """
        self.data["rfid_actions"][uid] = action
        self.save()

        # Sauvegarde parallèle dans un fichier .txt
        txt_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_rfid.txt")
        
        # Créer le dossier si nécessaire
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        
        # Lire le fichier existant pour mettre à jour ou ajouter
        existing_lines = []
        card_line_index = -1
        rfid_section_start = -1
        rfid_section_end = -1
        
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    upper = line.strip().upper()
                    
                    # Détection section RFID
                    if "SECTION" in upper and ("CARTES" in upper or "RFID" in upper):
                        rfid_section_start = i
                    elif rfid_section_start != -1 and "SECTION" in upper:
                        rfid_section_end = i
                        break
                    
                    # Chercher si la carte existe déjà
                    if rfid_section_start != -1 and "=" in line:
                        try:
                            existing_uid = int(line.split("=")[0].strip())
                            if existing_uid == int(uid):
                                card_line_index = i
                        except:
                            pass
                existing_lines = lines
        
        # Construire la nouvelle ligne
        new_line = f"{uid} = {action}\n"
        
        # Mettre à jour ou ajouter
        if card_line_index != -1:
            # Remplacer ligne existante
            existing_lines[card_line_index] = new_line
            new_content = existing_lines
        elif rfid_section_start != -1:
            # Ajouter dans la section existante
            if rfid_section_end == -1:
                rfid_section_end = len(existing_lines)
            new_content = (
                existing_lines[:rfid_section_end] +
                [new_line] +
                existing_lines[rfid_section_end:]
            )
        else:
            # Créer la section
            new_content = existing_lines + [
                "\n# SECTION: Cartes RFID\n",
                new_line
            ]
        
        # Écrire le fichier
        with open(txt_path, "w", encoding="utf-8") as f:
            f.writelines(new_content)
        
        print(f"[SETTINGS] Action RFID sauvegardée : {uid} → {action}")


    def get_rfid_action(self, uid):
        """Récupère une action RFID depuis le JSON"""
        return self.data["rfid_actions"].get(str(uid), None)


    def remove_rfid_action(self, uid):
        """
        Supprime une action RFID du JSON et du fichier .txt
        
        Args:
            uid: ID de la carte RFID
        """
        # Supprimer du JSON
        if str(uid) in self.data["rfid_actions"]:
            del self.data["rfid_actions"][str(uid)]
            self.save()
        
        # Supprimer du fichier .txt
        txt_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_rfid.txt")
        
        if not os.path.exists(txt_path):
            return
        
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            for line in lines:
                if "=" in line:
                    try:
                        existing_uid = int(line.split("=")[0].strip())
                        if existing_uid == int(uid):
                            continue  # Skip cette ligne
                    except:
                        pass
                new_lines.append(line)
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            
            print(f"[SETTINGS] Action RFID supprimée : {uid}")
        
        except Exception as e:
            print(f"[SETTINGS] Erreur suppression RFID : {e}")
