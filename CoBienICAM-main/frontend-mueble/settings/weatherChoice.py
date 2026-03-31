from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty
from kivy.app import App
from kivy.clock import Clock
import os
from translation import _
import json
from datetime import datetime
import paho.mqtt.publish as publish
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
from popup_style import wrap_popup_content, popup_theme_kwargs

# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

class CityCard(BoxLayout):
    def __init__(self, city_name, is_active, callback, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.spacing = dp(20)
        self.padding = [dp(24), dp(20), dp(24), dp(20)]
        self.size_hint_y = None
        self.height = dp(120)
        self.is_active = is_active
        self.city_name = city_name
        self.callback = callback
        
        # Background - TOUJOURS BLANC
        from kivy.graphics import Color, RoundedRectangle, Line
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
            Color(0, 0, 0, 0.85)
            self.border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(16)), width=2)
        
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        
        # City label
        lbl = Label(
            text=city_name,
            font_size=sp(28),
            bold=is_active,
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle"
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)
        
        # Bouton toggle
        btn_box = BoxLayout(size_hint_x=None, width=dp(200), spacing=dp(10))
        
        # ✅ Utiliser traduction
        self.btn = Button(
            text=_("Activa") if is_active else _("Activar"),
            font_size=sp(20),
            size_hint_x=1,
            background_color=(0, 0, 0, 0)
        )
        
        self.btn_bg_rect = None
        with self.btn.canvas.before:
            if is_active:
                Color(0.2, 0.7, 0.3, 1)
            else:
                Color(0.15, 0.55, 0.95, 1)
            self.btn_bg_rect = RoundedRectangle(pos=self.btn.pos, size=self.btn.size, radius=[dp(12)])
        
        self.btn.bind(pos=self.update_btn_bg, size=self.update_btn_bg)
        self.btn.bind(on_release=lambda x: callback(city_name))
        
        btn_box.add_widget(self.btn)
        self.add_widget(btn_box)
    
    def update_text(self):
        """✅ Met à jour le texte du bouton selon la langue"""
        self.btn.text = _("Activa") if self.is_active else _("Activar")
    
    def update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))
    
    def update_btn_bg(self, btn, *args):
        if self.btn_bg_rect:
            self.btn_bg_rect.pos = btn.pos
            self.btn_bg_rect.size = btn.size


class WeatherChoice(FloatLayout):
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.sm = sm
        self.city_list_geo = {}
        self.available_cities = []
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_weather.txt")
        self.last_mtime = os.path.getmtime(self.config_path) if os.path.exists(self.config_path) else 0
        self._watch_event = None
        self.selected_letter = None
        self.letter_buttons = {}
        
        print("[WEATHER CHOICE] __init__ called")

        # Load available cities from the file
        self.load_available_cities()
        
        print(f"[WEATHER CHOICE] Cities loaded: {self.available_cities}")
        
        # ✅ IMPORTANT: Build the UI manually
        self.build_ui()

    
    def update_labels(self):
        """✅ Update all translated labels"""
        print("[WEATHER CHOICE] 🔄 Updating labels...")
        
        if hasattr(self, 'lbl_title'):
            self.lbl_title.text = _("Ciudades Meteorología")
        if hasattr(self, 'lbl_instruction'):
            self.lbl_instruction.text = _(
                "Seleccione las ciudades a mostrar en la rotación de meteorología"
            )
        if hasattr(self, "btn_add_city"):
            self.btn_add_city.text = _("Añadir ciudad")
        if hasattr(self, "btn_all_letters"):
            self.btn_all_letters.text = _("Todas")
        
        # ✅ Update the "Activa"/"Activar" buttons of each card
        if hasattr(self, 'list_cities'):
            for child in self.list_cities.children:
                if isinstance(child, CityCard):
                    child.update_text()
        
        print("[WEATHER CHOICE] ✅ Labels mis à jour")
    
    def publish_reload_event(self):
        """Publish an MQTT event to request reload"""
        try:
            payload = {
                "action": "reload",
                "timestamp": datetime.now().isoformat()
            }
            
            publish.single(
                "weather/reload",
                payload=json.dumps(payload),
                hostname=MQTT_LOCAL_BROKER,
                port=MQTT_LOCAL_PORT
            )
            
            print("[TOGGLE] 📤 MQTT event 'weather/reload' published")
        
        except Exception as e:
            print(f"[TOGGLE] ⚠️ MQTT publish error: {e}")

    def go_back(self):
        """Return to settings screen"""
        self.sm.current = "settings"
    
    def build_ui(self):
        """Build the user interface manually"""
        from kivy.graphics import Color as ColorGraphics, Rectangle, RoundedRectangle, Line
        from kivy.uix.widget import Widget
        
        app = App.get_running_app()

        # Background
        with self.canvas.before:
            ColorGraphics(1, 1, 1, 1)
            self.bg = Rectangle(pos=self.pos, size=self.size)
            if hasattr(app, 'has_bg_image') and app.has_bg_image:
                self.bg.source = app.bg_image
        
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Container principal
        main_box = BoxLayout(
            orientation="vertical",
            size_hint=(0.94, 0.94),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            padding=[0, dp(18), 0, dp(18)],
            spacing=dp(18)
        )
        
        # ===== HEADER =====
        header = BoxLayout(
            size_hint_y=None,
            height=dp(110),
            padding=[dp(22), dp(14), dp(22), dp(14)],
            spacing=dp(18)
        )
        
        with header.canvas.before:
            ColorGraphics(1, 1, 1, 0.85)
            header.bg_rect = RoundedRectangle(pos=header.pos, size=header.size, radius=[dp(20)])
        
        header.bind(
            pos=lambda inst, val: setattr(inst.bg_rect, 'pos', val),
            size=lambda inst, val: setattr(inst.bg_rect, 'size', val)
        )
        
        # Titre
        self.lbl_title = Label(
            text=_("Ciudades Meteorología"),
            font_size=sp(40),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_x=None,
            width=dp(700),
            halign="left",
            valign="middle"
        )
        self.lbl_title.bind(size=self.lbl_title.setter('text_size'))
        header.add_widget(self.lbl_title)
        
        header.add_widget(Widget())
        
        # Boutons action
        btn_back_box = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(320),
            spacing=dp(12),
            padding=[0, 0, dp(10), 0]
        )

        self.btn_add_city = Button(
            text=_("Añadir ciudad"),
            font_size=sp(18),
            size_hint=(None, None),
            size=(dp(190), dp(56)),
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
        )
        from kivy.graphics import Color as BtnColor, RoundedRectangle as BtnRoundedRectangle
        with self.btn_add_city.canvas.before:
            BtnColor(0.15, 0.55, 0.95, 1)
            self.btn_add_bg = BtnRoundedRectangle(
                pos=self.btn_add_city.pos,
                size=self.btn_add_city.size,
                radius=[dp(12)]
            )
        self.btn_add_city.bind(
            pos=lambda inst, val: setattr(self.btn_add_bg, "pos", val),
            size=lambda inst, val: setattr(self.btn_add_bg, "size", val),
            on_release=lambda *_: self.open_add_city_popup(),
        )
        btn_back_box.add_widget(self.btn_add_city)
        
        btn_back = IconBadge()
        btn_back.icon_source = app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "images/back.png"
        btn_back.bind(on_release=lambda x: self.go_back())
        btn_back_box.add_widget(btn_back)
        
        header.add_widget(btn_back_box)
        main_box.add_widget(header)
        
        # ===== CONTENU PRINCIPAL =====
        content_anchor = AnchorLayout(size_hint=(1, 1))
        
        with content_anchor.canvas.before:
            ColorGraphics(1, 1, 1, 0.85)
            content_anchor.bg_rect = RoundedRectangle(
                pos=content_anchor.pos,
                size=content_anchor.size,
                radius=[dp(20)]
            )
        
        content_anchor.bind(
            pos=lambda inst, val: setattr(inst.bg_rect, 'pos', val),
            size=lambda inst, val: setattr(inst.bg_rect, 'size', val)
        )
        
        content_box = BoxLayout(
            orientation="vertical",
            size_hint=(0.96, 0.90),
            spacing=dp(30),
            padding=dp(40)
        )
        
        # Espace supérieur
        content_box.add_widget(Widget(size_hint_y=0.05))
        
        # Instruction
        self.lbl_instruction = Label(
            text=_("Seleccione las ciudades a mostrar en la rotación de meteorología"),
            font_size=sp(20),
            color=(0, 0, 0, 0.7),
            size_hint_y=None,
            height=dp(40),
            halign="center",
            valign="middle"
        )
        self.lbl_instruction.bind(size=self.lbl_instruction.setter('text_size'))
        content_box.add_widget(self.lbl_instruction)

        # Filtro alfabético táctil (sin teclado)
        letters_scroll = ScrollView(
            size_hint_y=None,
            height=dp(64),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=dp(6),
        )
        self.letters_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            padding=[dp(4), dp(4), dp(4), dp(4)],
            size_hint_x=None,
            width=dp(1400),
        )
        letters_scroll.add_widget(self.letters_row)
        content_box.add_widget(letters_scroll)
        self._build_letter_filter_buttons()
        
        # ScrollView avec liste des villes
        scroll = ScrollView(
            size_hint_y=None,
            height=dp(500),
            do_scroll_x=False,
            bar_width=dp(12)
        )
        
        self.list_cities = GridLayout(
            cols=1,
            spacing=dp(20),
            padding=dp(10),
            size_hint_y=None
        )
        self.list_cities.bind(minimum_height=self.list_cities.setter('height'))
        
        scroll.add_widget(self.list_cities)
        content_box.add_widget(scroll)
        
        # Espace inférieur
        content_box.add_widget(Widget(size_hint_y=0.15))
        
        content_anchor.add_widget(content_box)
        main_box.add_widget(content_anchor)
        
        self.add_widget(main_box)
        
        print("[WEATHER CHOICE] UI built")
        
        # Load cities after a short delay
        Clock.schedule_once(lambda dt: self.refresh_cities(), 0.1)

    def _build_letter_filter_buttons(self):
        self.letters_row.clear_widgets()
        self.letter_buttons = {}

        self.btn_all_letters = Button(
            text=_("Todas"),
            size_hint=(None, None),
            size=(dp(110), dp(52)),
            font_size=sp(18),
            background_color=(0.1, 0.1, 0.1, 1),
            color=(1, 1, 1, 1),
        )
        self.btn_all_letters.bind(on_release=lambda *_: self._set_letter_filter(None))
        self.letters_row.add_widget(self.btn_all_letters)

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            btn = Button(
                text=letter,
                size_hint=(None, None),
                size=(dp(52), dp(52)),
                font_size=sp(18),
                background_color=(0.85, 0.85, 0.85, 1),
                color=(0, 0, 0, 1),
            )
            btn.bind(on_release=lambda _b, l=letter: self._set_letter_filter(l))
            self.letter_buttons[letter] = btn
            self.letters_row.add_widget(btn)

        self._refresh_letter_filter_ui()

    def _set_letter_filter(self, letter):
        self.selected_letter = letter
        self._refresh_letter_filter_ui()
        self.refresh_cities()

    def _refresh_letter_filter_ui(self):
        if hasattr(self, "btn_all_letters"):
            if self.selected_letter is None:
                self.btn_all_letters.background_color = (0.1, 0.1, 0.1, 1)
                self.btn_all_letters.color = (1, 1, 1, 1)
            else:
                self.btn_all_letters.background_color = (0.85, 0.85, 0.85, 1)
                self.btn_all_letters.color = (0, 0, 0, 1)

        for letter, btn in self.letter_buttons.items():
            if self.selected_letter == letter:
                btn.background_color = (0.1, 0.1, 0.1, 1)
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = (0.85, 0.85, 0.85, 1)
                btn.color = (0, 0, 0, 1)

    def _city_matches_selected_letter(self, city):
        if not self.selected_letter:
            return True
        city = (city or "").strip()
        if not city:
            return False
        return city[0].upper() == self.selected_letter
    
    def _update_bg(self, *args):
        """Met à jour le background"""
        if hasattr(self, 'bg'):
            self.bg.pos = self.pos
            self.bg.size = self.size

    def load_available_cities(self):
        """Charge la liste des villes disponibles depuis config/config_weather.txt"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_weather.txt")
        
        print(f"[WEATHER CHOICE] Chemin config: {config_path}")
        print(f"[WEATHER CHOICE] Fichier existe? {os.path.exists(config_path)}")
        
        self.available_cities = []
        self.active_cities = []
        
        if not os.path.exists(config_path):
            print(f"[WEATHER CHOICE] Fichier non trouvé, création...")
            self.create_default_config(config_path)
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                print(f"[WEATHER CHOICE] {len(lines)} lignes lues")
                
                for line in lines:
                    stripped = line.strip()
                    
                    if not stripped:
                        continue
                    
                    if stripped.startswith("#"):
                        city = stripped[1:].strip()
                        
                        if city and not any(word in city.lower() for word in ['liste', 'list', 'una', 'ville', 'ciudad', 'disponible', 'ligne', 'line']):
                            self.available_cities.append(city)
                            print(f"[WEATHER CHOICE] Ville désactivée: {city}")
                    
                    else:
                        self.available_cities.append(stripped)
                        self.active_cities.append(stripped)
                        print(f"[WEATHER CHOICE] Ville active: {stripped}")
            
            print(f"[WEATHER CHOICE] Total: {len(self.available_cities)} villes ({len(self.active_cities)} actives)")
        
        except Exception as e:
            print(f"[WEATHER CHOICE] Erreur lors du chargement: {e}")
            import traceback
            traceback.print_exc()

    def create_default_config(self, config_path):
        """Crée un fichier de configuration par défaut avec quelques villes"""
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            default_cities = [
                "# Liste des villes disponibles pour la météo",
                "# Une ville par ligne",
                "",
                "Bilbao",
                "Madrid",
                "Barcelona",
                "Valencia",
                "Sevilla"
            ]
            
            with open(config_path, "w", encoding="utf-8") as f:
                f.write("\n".join(default_cities))
            
            print(f"[WEATHER CHOICE] Fichier de configuration créé: {config_path}")
            self.load_available_cities()
        
        except Exception as e:
            print(f"[WEATHER CHOICE] Erreur lors de la création du fichier: {e}")
            import traceback
            traceback.print_exc()

    def set_city_list(self, city_geo_dict):
        """Méthode appelée par mainApp.py"""
        self.city_list_geo = city_geo_dict
        print(f"[WEATHER CHOICE] Liste geo reçue: {len(city_geo_dict)} villes")

    def refresh_cities(self, *args):
        """Affiche toutes les villes disponibles"""
        print(f"\n[DEBUG] ========== REFRESH_CITIES ==========")
        print(f"[DEBUG] Nombre de villes: {len(self.available_cities)}")
        
        if not hasattr(self, 'list_cities'):
            print("[DEBUG] ERREUR: list_cities n'existe pas encore!")
            Clock.schedule_once(lambda dt: self.refresh_cities(), 0.1)
            return
        
        box = self.list_cities
        print(f"[DEBUG] ✓ Box trouvée: {box}")
        box.clear_widgets()
        
        # Mettre à jour les labels avant de créer les cartes
        if hasattr(self, 'lbl_title'):
            self.lbl_title.text = _("Ciudades Meteorología")
        if hasattr(self, 'lbl_instruction'):
            self.lbl_instruction.text = _(
                "Seleccione las ciudades a mostrar en la rotación de meteorología"
            )

        active_cities = getattr(self, 'active_cities', [])
        print(f"[DEBUG] Villes actives: {active_cities}")
        
        if not self.available_cities:
            box.add_widget(Label(
                text="Aucune ville dans config_weather.txt",
                font_size=sp(24),
                color=(1, 0.5, 0, 1),
                size_hint_y=None,
                height=dp(60)
            ))
            print("[DEBUG] Message d'erreur ajouté")
            return
        
        shown_count = 0
        for city in self.available_cities:
            if not self._city_matches_selected_letter(city):
                continue
            is_active = city in active_cities
            print(f"[DEBUG] Création carte: {city} (active: {is_active})")
            
            try:
                card = CityCard(
                    city_name=city,
                    is_active=is_active,
                    callback=self.toggle_city
                )
                box.add_widget(card)
                shown_count += 1
            except Exception as e:
                print(f"[DEBUG] Erreur carte {city}: {e}")
                import traceback
                traceback.print_exc()

        if shown_count == 0:
            empty_msg = _("No hay ciudades para esta letra.") if self.selected_letter else _("No hay ciudades disponibles.")
            box.add_widget(Label(
                text=empty_msg,
                font_size=sp(24),
                color=(0.2, 0.2, 0.2, 1),
                size_hint_y=None,
                height=dp(60)
            ))
        
        print(f"[DEBUG] Total widgets: {len(box.children)}")
        print(f"[DEBUG] ========== FIN REFRESH ==========\n")

    def toggle_city(self, city):
        """Active ou désactive une ville en modifiant config_weather.txt"""
        print(f"\n[TOGGLE] ========== DÉBUT TOGGLE ==========")
        print(f"[TOGGLE] Ville cliquée: '{city}'")
        
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_weather.txt")
        
        if not os.path.exists(config_path):
            print(f"[TOGGLE] Fichier config_weather.txt introuvable: {config_path}")
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            print(f"[TOGGLE] {len(lines)} lignes lues")
            
            city_found = False
            city_is_active = False
            city_line_index = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                if stripped.startswith("#"):
                    city_in_comment = stripped[1:].strip()
                    if city_in_comment == city:
                        city_found = True
                        city_is_active = False
                        city_line_index = i
                        print(f"[TOGGLE] Ville trouvée DÉSACTIVÉE à la ligne {i}: '{stripped}'")
                        break
                
                elif stripped == city:
                    city_found = True
                    city_is_active = True
                    city_line_index = i
                    print(f"[TOGGLE] Ville trouvée ACTIVE à la ligne {i}: '{stripped}'")
                    break
            
            if city_found:
                old_line = lines[city_line_index].strip()
                
                if city_is_active:
                    lines[city_line_index] = f"# {city}\n"
                    print(f"[TOGGLE] DÉSACTIVATION: '{old_line}' → '# {city}'")
                else:
                    lines[city_line_index] = f"{city}\n"
                    print(f"[TOGGLE] ACTIVATION: '{old_line}' → '{city}'")
                
                with open(config_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                    self.publish_reload_event()
                self.last_mtime = os.path.getmtime(config_path)
                
                print(f"[TOGGLE] Fichier config_weather.txt sauvegardé")
                
                print(f"[TOGGLE] Contenu après modification:")
                for i, line in enumerate(lines[:10]):
                    print(f"  Ligne {i}: {line.rstrip()}")
                
                print(f"[TOGGLE] Rechargement des villes...")
                self.load_available_cities()
                self.refresh_cities()
                print(f"[TOGGLE] ========== FIN TOGGLE (succès) ==========\n")
            
            else:
                print(f"[TOGGLE] Ville '{city}' NON TROUVÉE dans config_weather.txt")
                print(f"[TOGGLE] Contenu du fichier:")
                for i, line in enumerate(lines):
                    print(f"  Ligne {i}: '{line.rstrip()}'")
                print(f"[TOGGLE] ========== FIN TOGGLE (échec) ==========\n")
        
        except Exception as e:
            print(f"[TOGGLE] ERREUR lors de la modification: {e}")
            import traceback
            traceback.print_exc()
            print(f"[TOGGLE] ========== FIN TOGGLE (erreur) ==========\n")

    def _normalize_city_name(self, raw_name):
        city = (raw_name or "").strip()
        return " ".join(city.split())

    def _city_exists(self, city_name):
        target = city_name.casefold()
        return any(c.casefold() == target for c in self.available_cities)

    def _append_city_to_config(self, city_name):
        if not os.path.exists(self.config_path):
            self.create_default_config(self.config_path)
        with open(self.config_path, "a", encoding="utf-8") as f:
            if os.path.getsize(self.config_path) > 0:
                f.write("\n")
            f.write(f"{city_name}\n")
        self.last_mtime = os.path.getmtime(self.config_path)

    def open_add_city_popup(self):
        content = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(16))
        title = Label(
            text=_("Añadir ciudad a la rotación"),
            size_hint_y=None,
            height=dp(36),
            font_size=sp(20),
            color=(0, 0, 0, 1),
        )
        city_input = TextInput(
            multiline=False,
            hint_text=_("Nombre de la ciudad"),
            size_hint_y=None,
            height=dp(48),
            font_size=sp(18),
        )
        actions = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
        btn_cancel = Button(text=_("Cancelar"))
        btn_save = Button(text=_("Guardar"))
        actions.add_widget(btn_cancel)
        actions.add_widget(btn_save)
        content.add_widget(title)
        content.add_widget(city_input)
        content.add_widget(actions)

        popup = Popup(
            title=_("Nueva ciudad"),
            content=wrap_popup_content(content),
            size_hint=(None, None),
            size=(dp(560), dp(290)),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )

        def _close(*_args):
            popup.dismiss()

        def _save(*_args):
            city = self._normalize_city_name(city_input.text)
            if not city:
                print("[WEATHER CHOICE] Empty city ignored")
                return
            if self._city_exists(city):
                print(f"[WEATHER CHOICE] City already exists: {city}")
                popup.dismiss()
                return
            try:
                self._append_city_to_config(city)
                self.load_available_cities()
                self.refresh_cities()
                self.publish_reload_event()
                print(f"[WEATHER CHOICE] ✅ Added city from UI: {city}")
            except Exception as exc:
                print(f"[WEATHER CHOICE] ❌ Error adding city '{city}': {exc}")
            popup.dismiss()

        btn_cancel.bind(on_release=_close)
        btn_save.bind(on_release=_save)
        popup.open()
    
    def on_pre_enter(self, *args):
        """Appelé avant d'afficher l'écran"""
        print("[WEATHER CHOICE] on_pre_enter")
        self._start_config_watcher()
        self.update_labels()
        self.load_available_cities()
        self.refresh_cities()

    def on_leave(self, *args):
        self._stop_config_watcher()

    def _start_config_watcher(self):
        if self._watch_event is not None:
            return
        self._watch_event = Clock.schedule_interval(self._watch_config_file, 3)
        print("[WEATHER CHOICE] ✅ Config watcher activé")

    def _stop_config_watcher(self):
        if self._watch_event is None:
            return
        self._watch_event.cancel()
        self._watch_event = None
        print("[WEATHER CHOICE] 🛑 Config watcher désactivé")

    def _watch_config_file(self, dt):
        """Surveille config_weather.txt et recharge si modifié."""
        try:
            if not os.path.exists(self.config_path):
                return
            
            current_mtime = os.path.getmtime(self.config_path)
            
            # Le fichier a été modifié → on recharge
            if current_mtime != self.last_mtime:
                print("[WEATHER CHOICE] Fichier txt modifié : rechargement automatique")
                self.last_mtime = current_mtime
                self.load_available_cities()
                self.refresh_cities()
                self.publish_reload_event()
        
        except Exception as e:
            print(f"[WEATHER CHOICE] erreur: {e}")
