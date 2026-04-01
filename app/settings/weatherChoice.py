from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.modalview import ModalView
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
import requests
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
from config_store import load_section

# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

class CityCard(BoxLayout):
    def __init__(self, city_name, is_active, is_primary, callback, delete_callback, priority_callback, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.spacing = dp(20)
        self.padding = [dp(24), dp(20), dp(24), dp(20)]
        self.size_hint_y = None
        self.height = dp(120)
        self.is_active = is_active
        self.is_primary = is_primary
        self.city_name = city_name
        self.callback = callback
        self.delete_callback = delete_callback
        self.priority_callback = priority_callback
        
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
        btn_box = BoxLayout(size_hint_x=None, width=dp(510), spacing=dp(10))
        
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
        
        self.btn_delete = Button(
            text=_("Eliminar"),
            font_size=sp(20),
            size_hint_x=1,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
        )
        self.btn_delete_bg_rect = None
        with self.btn_delete.canvas.before:
            Color(0.86, 0.2, 0.2, 1)
            self.btn_delete_bg_rect = RoundedRectangle(
                pos=self.btn_delete.pos,
                size=self.btn_delete.size,
                radius=[dp(12)],
            )

        self.btn_delete.bind(pos=self.update_btn_delete_bg, size=self.update_btn_delete_bg)
        self.btn_delete.bind(on_release=lambda x: delete_callback(city_name))

        self.btn_priority = Button(
            text=_("Prioritaria") if is_primary else _("Priorizar"),
            font_size=sp(20),
            size_hint_x=1,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
        )
        self.btn_priority_bg_rect = None
        with self.btn_priority.canvas.before:
            if is_primary:
                Color(0.95, 0.65, 0.15, 1)
            else:
                Color(0.35, 0.35, 0.35, 1)
            self.btn_priority_bg_rect = RoundedRectangle(
                pos=self.btn_priority.pos,
                size=self.btn_priority.size,
                radius=[dp(12)],
            )
        self.btn_priority.bind(pos=self.update_btn_priority_bg, size=self.update_btn_priority_bg)
        self.btn_priority.bind(on_release=lambda x: priority_callback(city_name))
        
        btn_box.add_widget(self.btn)
        btn_box.add_widget(self.btn_delete)
        btn_box.add_widget(self.btn_priority)
        self.add_widget(btn_box)
    
    def update_text(self):
        """✅ Met à jour le texte du bouton selon la langue"""
        self.btn.text = _("Activa") if self.is_active else _("Activar")
        self.btn_priority.text = _("Prioritaria") if self.is_primary else _("Priorizar")
    
    def update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))
    
    def update_btn_bg(self, btn, *args):
        if self.btn_bg_rect:
            self.btn_bg_rect.pos = btn.pos
            self.btn_bg_rect.size = btn.size

    def update_btn_delete_bg(self, btn, *args):
        if self.btn_delete_bg_rect:
            self.btn_delete_bg_rect.pos = btn.pos
            self.btn_delete_bg_rect.size = btn.size

    def update_btn_priority_bg(self, btn, *args):
        if self.btn_priority_bg_rect:
            self.btn_priority_bg_rect.pos = btn.pos
            self.btn_priority_bg_rect.size = btn.size


class WeatherChoice(FloatLayout):
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.sm = sm
        self.city_list_geo = {}
        self.available_cities = []
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config_weather.txt")
        self.last_mtime = 0
        self._watch_event = None
        self.selected_letter = None
        self.letter_buttons = {}
        self.primary_city = (self.cfg.data.get("weather_primary_city", "") or "").strip()
        
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
            background_normal="",
            background_down="",
            background_disabled_normal="",
            background_disabled_down="",
            background_color=(1, 1, 1, 1),
            color=(0, 0, 0, 1),
        )
        self.btn_all_letters.bind(on_release=lambda *_: self._set_letter_filter(None))
        self.letters_row.add_widget(self.btn_all_letters)

        source_cities = self.active_cities if self.active_cities else self.available_cities
        letters = sorted({
            (city or "").strip()[0].upper()
            for city in source_cities
            if (city or "").strip()
        })

        if self.selected_letter and self.selected_letter not in letters:
            self.selected_letter = None

        for letter in letters:
            btn = Button(
                text=letter,
                size_hint=(None, None),
                size=(dp(52), dp(52)),
                font_size=sp(18),
                background_normal="",
                background_down="",
                background_disabled_normal="",
                background_disabled_down="",
                background_color=(1, 1, 1, 1),
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
            self.btn_all_letters.background_color = (1, 1, 1, 1)
            self.btn_all_letters.color = (0, 0, 0, 1)

        for letter, btn in self.letter_buttons.items():
            btn.background_color = (1, 1, 1, 1)
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
        """Load city catalog and active cities from unified settings config."""
        active = [str(c).strip() for c in self.cfg.data.get("weather_cities", []) if str(c).strip()]
        catalog = [str(c).strip() for c in self.cfg.data.get("weather_city_catalog", []) if str(c).strip()]
        if not catalog:
            catalog = list(active)
            self.cfg.data["weather_city_catalog"] = list(catalog)
            self.cfg.save()

        self.available_cities = catalog
        self.active_cities = active
        self.primary_city = (self.cfg.data.get("weather_primary_city", "") or "").strip()
        self._build_letter_filter_buttons()

    def create_default_config(self, config_path):
        """Legacy no-op retained for compatibility."""
        self.load_available_cities()

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
                text=_("No hay ciudades disponibles."),
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
            is_primary = bool(self.primary_city) and city == self.primary_city
            print(f"[DEBUG] Création carte: {city} (active: {is_active})")
            
            try:
                card = CityCard(
                    city_name=city,
                    is_active=is_active,
                    is_primary=is_primary,
                    callback=self.toggle_city,
                    delete_callback=self.confirm_delete_city,
                    priority_callback=self.set_primary_city,
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
        """Toggle city activation in unified settings config."""
        try:
            active = [str(c).strip() for c in self.cfg.data.get("weather_cities", []) if str(c).strip()]
            if city in active:
                active = [c for c in active if c != city]
            else:
                active.append(city)
            self.cfg.data["weather_cities"] = active
            self.cfg.save()
            self.load_available_cities()
            self.refresh_cities()
            self.publish_reload_event()
        except Exception as e:
            print(f"[TOGGLE] ERREUR lors de la modification: {e}")

    def _normalize_city_name(self, raw_name):
        city = (raw_name or "").strip()
        return " ".join(city.split())

    def _city_exists(self, city_name):
        target = city_name.casefold()
        return any(c.casefold() == target for c in self.available_cities)

    def _append_city_to_config(self, city_name):
        catalog = [str(c).strip() for c in self.cfg.data.get("weather_city_catalog", []) if str(c).strip()]
        active = [str(c).strip() for c in self.cfg.data.get("weather_cities", []) if str(c).strip()]
        if city_name not in catalog:
            catalog.append(city_name)
        if city_name not in active:
            active.append(city_name)
        self.cfg.data["weather_city_catalog"] = catalog
        self.cfg.data["weather_cities"] = active
        self.cfg.save()

    def set_primary_city(self, city_name):
        if not city_name:
            return
        self.primary_city = city_name
        self.cfg.data["weather_primary_city"] = city_name
        self.cfg.save()
        print(f"[WEATHER CHOICE] ⭐ Primary city set: {city_name}")
        self.refresh_cities()
        self.publish_reload_event()

    def _remove_city_from_config(self, city_name):
        catalog = [str(c).strip() for c in self.cfg.data.get("weather_city_catalog", []) if str(c).strip()]
        active = [str(c).strip() for c in self.cfg.data.get("weather_cities", []) if str(c).strip()]
        if city_name not in catalog and city_name not in active:
            return False
        self.cfg.data["weather_city_catalog"] = [c for c in catalog if c != city_name]
        self.cfg.data["weather_cities"] = [c for c in active if c != city_name]
        self.cfg.save()
        return True

    def confirm_delete_city(self, city_name):
        from kivy.graphics import Color, RoundedRectangle, Line
        popup = ModalView(
            size_hint=(None, None),
            size=(dp(980), dp(520)),
            auto_dismiss=False,
            background="",
            background_color=(0, 0, 0, 0.7),
        )
        content = BoxLayout(orientation="vertical", spacing=dp(24), padding=dp(40))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(24)])
            Color(0, 0, 0, 0.2)
            border = Line(rounded_rectangle=(content.x, content.y, content.width, content.height, dp(24)), width=3)

        def _sync_bg(*_args):
            bg.pos = content.pos
            bg.size = content.size
            border.rounded_rectangle = (content.x, content.y, content.width, content.height, dp(24))

        content.bind(pos=_sync_bg, size=_sync_bg)

        title = Label(
            text=_("Confirmar borrado"),
            size_hint_y=None,
            height=dp(60),
            font_size=sp(42),
            bold=True,
            color=(0, 0, 0, 1),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        message = Label(
            text=_("¿Seguro que quieres eliminar esta ciudad?"),
            size_hint_y=None,
            height=dp(90),
            font_size=sp(30),
            color=(0.2, 0.2, 0.2, 1),
            halign="center",
            valign="middle",
        )
        message.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        actions = BoxLayout(orientation="horizontal", spacing=dp(20), size_hint_y=None, height=dp(75))
        btn_cancel = Button(
            text=_("Cancelar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(30),
            bold=True,
        )
        btn_delete = Button(
            text=_("Eliminar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(30),
            bold=True,
        )
        actions.add_widget(BoxLayout())
        actions.add_widget(btn_cancel)
        actions.add_widget(btn_delete)
        actions.add_widget(BoxLayout())
        content.add_widget(BoxLayout(size_hint_y=0.15))
        content.add_widget(title)
        content.add_widget(message)
        content.add_widget(BoxLayout(size_hint_y=0.2))
        content.add_widget(actions)
        popup.add_widget(content)

        def _close(*_args):
            popup.dismiss()

        def _confirm(*_args):
            try:
                if self._remove_city_from_config(city_name):
                    if self.cfg.data.get("weather_primary_city", "") == city_name:
                        self.cfg.data["weather_primary_city"] = ""
                        self.cfg.save()
                        self.primary_city = ""
                    self.load_available_cities()
                    self.refresh_cities()
                    self.publish_reload_event()
                    print(f"[WEATHER CHOICE] ✅ Removed city from UI: {city_name}")
                else:
                    print(f"[WEATHER CHOICE] ⚠️ City not found for deletion: {city_name}")
            except Exception as exc:
                print(f"[WEATHER CHOICE] ❌ Error deleting city '{city_name}': {exc}")
            popup.dismiss()

        btn_cancel.bind(on_release=_close)
        btn_delete.bind(on_release=_confirm)
        popup.open()

    def open_add_city_popup(self):
        from kivy.graphics import Color, RoundedRectangle, Line
        popup = ModalView(
            size_hint=(None, None),
            size=(dp(980), dp(520)),
            auto_dismiss=False,
            background="",
            background_color=(0, 0, 0, 0.7),
        )
        content = BoxLayout(orientation="vertical", spacing=dp(24), padding=dp(40))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(24)])
            Color(0, 0, 0, 0.2)
            border = Line(rounded_rectangle=(content.x, content.y, content.width, content.height, dp(24)), width=3)

        def _sync_bg(*_args):
            bg.pos = content.pos
            bg.size = content.size
            border.rounded_rectangle = (content.x, content.y, content.width, content.height, dp(24))

        content.bind(pos=_sync_bg, size=_sync_bg)

        title = Label(
            text=_("Añadir ciudad a la rotación"),
            size_hint_y=None,
            height=dp(60),
            font_size=sp(42),
            bold=True,
            color=(0, 0, 0, 1),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        city_input = TextInput(
            multiline=False,
            hint_text=_("Nombre de la ciudad"),
            size_hint_y=None,
            height=dp(72),
            font_size=sp(28),
        )
        validation_label = Label(
            text="",
            size_hint_y=None,
            height=dp(36),
            font_size=sp(20),
            color=(0.85, 0.1, 0.1, 1),
            halign="center",
            valign="middle",
        )
        validation_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        actions = BoxLayout(orientation="horizontal", spacing=dp(20), size_hint_y=None, height=dp(75))
        btn_cancel = Button(
            text=_("Cancelar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(30),
            bold=True,
        )
        btn_save = Button(
            text=_("Guardar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
            font_size=sp(30),
            bold=True,
        )
        actions.add_widget(BoxLayout())
        actions.add_widget(btn_cancel)
        actions.add_widget(btn_save)
        actions.add_widget(BoxLayout())
        content.add_widget(BoxLayout(size_hint_y=0.15))
        content.add_widget(title)
        content.add_widget(city_input)
        content.add_widget(validation_label)
        content.add_widget(BoxLayout(size_hint_y=0.2))
        content.add_widget(actions)
        popup.add_widget(content)

        def _close(*_args):
            popup.dismiss()

        def _save(*_args):
            city = self._normalize_city_name(city_input.text)
            if not city:
                validation_label.text = _("Debe escribir una ciudad.")
                return
            if self._city_exists(city):
                print(f"[WEATHER CHOICE] City already exists: {city}")
                validation_label.text = _("La ciudad ya existe en la lista.")
                popup.dismiss()
                return
            if not self._is_valid_city(city):
                validation_label.text = _("Ciudad no válida. Revise el nombre.")
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

    def _is_valid_city(self, city_name):
        """Validate that the city name can be geocoded."""
        try:
            services_cfg = load_section("services", {})
            url = services_cfg.get("nominatim_search_url", "https://nominatim.openstreetmap.org/search")
            params = {"format": "json", "q": city_name, "limit": 1}
            headers = {"User-Agent": "CoBien-App"}
            response = requests.get(url, params=params, headers=headers, timeout=6)
            if response.status_code != 200:
                print(f"[WEATHER CHOICE] City validation HTTP error: {response.status_code}")
                return False
            payload = response.json()
            is_valid = isinstance(payload, list) and len(payload) > 0
            if not is_valid:
                print(f"[WEATHER CHOICE] Invalid city name: {city_name}")
            return is_valid
        except Exception as exc:
            print(f"[WEATHER CHOICE] City validation error for '{city_name}': {exc}")
            return False
    
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
        """Watch unified settings for city list changes."""
        try:
            self.load_available_cities()
            self.refresh_cities()
        except Exception as e:
            print(f"[WEATHER CHOICE] erreur: {e}")
