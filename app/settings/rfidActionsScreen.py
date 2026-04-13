"""RFID settings screen used to map card IDs to frontend actions.

The module provides an administration flow for scanning a card, selecting an
action, storing mappings, and notifying the runtime to reload RFID actions.
"""

from typing import Any, Dict, List, Optional

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import DictProperty, StringProperty, ListProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.metrics import dp, sp
from kivy.app import App
from kivy.clock import Clock
from translation import _, get_current_language, change_language
from popup_style import wrap_popup_content, popup_theme_kwargs
import json
import paho.mqtt.client as mqtt
import os
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
from config_store import load_section, save_section

# ----------------- REUSABLE WIDGETS -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    """Reusable icon badge button."""

    icon_source = StringProperty("")

Factory.register("IconBadge", cls=IconBadge)

# ----------------- KV LAYOUT -----------------

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set C_BORDER 0,0,0,0.85
#:set R_CARD dp(20)
#:set R_BTN dp(16)
#:set H_HEADER dp(110)
#:set GAP_Y dp(18)

<IconBadge>:
    size_hint: None, None
    size: dp(80), dp(80)
    padding: dp(6)
    canvas.before:
        Color:
            rgba: 1,1,1,1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [R_BTN,]
        Color:
            rgba: C_BORDER
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, R_BTN)
    Image:
        source: root.icon_source
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(56), dp(56)

<RFIDActionsRoot@FloatLayout>:
    parent_screen: None
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if app.has_bg_image else ""

    BoxLayout:
        orientation: "vertical"
        size_hint: 0.94, 0.94
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        padding: [0, GAP_Y, 0, GAP_Y]
        spacing: GAP_Y

        # ---------- HEADER ----------
        BoxLayout:
            size_hint_y: None
            height: H_HEADER
            padding: dp(22), dp(14)
            spacing: dp(18)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            Label:
                id: lbl_title
                text: ""
                font_size: sp(40)
                bold: True
                color: C_BLACK
                size_hint_x: None
                width: dp(700)
                halign: "left"
                valign: "middle"
                text_size: self.size

            Widget:

            BoxLayout:
                orientation: "horizontal"
                size_hint_x: None
                width: self.minimum_width
                spacing: dp(6)
                padding: [0, 0, dp(10), 0]
                IconBadge:
                    icon_source: app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "data/images/back.png"
                    on_release: root.parent_screen.go_back() if root.parent_screen else None

        # ---------- MAIN CONTENT ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            ScrollView:
                do_scroll_x: False
                bar_width: dp(8)
                
                BoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(20)
                    padding: dp(40)

                    # ---------- INSTRUCTION ----------
                    Label:
                        id: lbl_instruction
                        text: ""
                        font_size: sp(24)
                        color: 0,0,0,0.7
                        size_hint_y: None
                        height: self.texture_size[1] + dp(20)
                        halign: "left"
                        valign: "top"
                        text_size: self.width - dp(40), None

                    # ---------- CARD LIST ----------
                    GridLayout:
                        id: cards_container
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(20)

                    Widget:
                        size_hint_y: None
                        height: dp(20)

                    # ---------- CONFIGURATION MODE BUTTON ----------
                    Button:
                        id: btn_start_config
                        text: ""
                        font_size: sp(24)
                        size_hint_y: None
                        height: dp(70)
                        background_color: 0,0,0,0
                        canvas.before:
                            Color:
                                rgba: 0.2, 0.7, 0.2, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(12),]
                        on_release: root.parent_screen.start_configuration_mode() if root.parent_screen else None

                    Widget:
                        size_hint_y: None
                        height: dp(40)
"""

Builder.load_string(KV)

# ----------------- PER-CARD WIDGET -----------------

class RFIDCardWidget(BoxLayout):
    card_id = NumericProperty(0)
    action = StringProperty("")
    extra_data = StringProperty("")
    
    def __init__(self, card_id: int, action: str, extra_data: str, parent_screen: Any, **kwargs: Any) -> None:
        """Initialize one RFID card row widget."""
        super().__init__(**kwargs)
        self.card_id = card_id
        self.action = action
        self.extra_data = extra_data
        self.parent_screen = parent_screen
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "config.local.json"))
        
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(180)
        self.spacing = dp(12)
        self.padding = dp(20)
        
        # Container styling
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16),])
            Color(0, 0, 0, 0.85)
            self.border = Line(width=2)
        
        self.bind(pos=self._update_graphics, size=self._update_graphics)
        
        # Header with card ID and delete action
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40))
        
        lbl_id = Label(
            text=f"{_('ID Tarjeta')}: {card_id}",
            font_size=sp(26),
            bold=True,
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle"
        )
        lbl_id.bind(size=lbl_id.setter('text_size'))
        
        btn_delete = Button(
            text=_("Eliminar"),
            size_hint_x=None,
            width=dp(150),
            font_size=sp(20),
            background_color=(0.9, 0.2, 0.2, 1)
        )
        btn_delete.bind(on_release=lambda x: self.parent_screen.confirm_remove_card(self.card_id))
        
        header.add_widget(lbl_id)
        header.add_widget(btn_delete)
        self.add_widget(header)
        
        # Action info
        action_info = Label(
            text=f"{_('Acción')}: {self._get_action_display_name(action)}",
            font_size=sp(22),
            color=(0, 0, 0, 0.8),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(40)
        )
        action_info.bind(size=action_info.setter('text_size'))
        self.add_widget(action_info)
        
        # Extra info (city or contact)
        if action == "weather" and extra_data:
            extra_info = Label(
                text=f"{_('Ciudad')}: {extra_data}",
                font_size=sp(20),
                color=(0, 0, 0, 0.7),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(35)
            )
            extra_info.bind(size=extra_info.setter('text_size'))
            self.add_widget(extra_info)
        elif action == "videocall" and extra_data:
            extra_info = Label(
                text=f"{_('Contacto')}: {extra_data}",
                font_size=sp(20),
                color=(0, 0, 0, 0.7),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(35)
            )
            extra_info.bind(size=extra_info.setter('text_size'))
            self.add_widget(extra_info)
    
    def _update_graphics(self, *args: Any) -> None:
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))
    
    def _get_action_display_name(self, action: str) -> str:
        action_map = {
            "day_events": _("Eventos del Día"),
            "weather": _("Tiempo"),
            "videocall": _("Videollamada")
        }
        return action_map.get(action, action)

# ----------------- MAIN SCREEN -----------------

class RFIDActionsScreen(Screen):
    configuring = BooleanProperty(False)
    detected_card_id = NumericProperty(0)
    
    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        """Initialize RFID settings screen and its MQTT integration."""
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        self.card_widgets = {}
        self.config_popup = None
        self.available_cities = []
        self.available_contacts = []

        # Écouter les changements de configuration (langue)
        if hasattr(self.cfg, 'bind'):
            self.cfg.bind(data=self._on_config_change)
            print("[RFID] ✅ Language-change listener enabled")
        else:
            print("[RFID] ⚠️ AppConfig does not expose bind()")
        
        # MQTT
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self.on_mqtt_message
        try:
            self.mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
            self.mqtt_client.loop_start()
            self.mqtt_client.subscribe("rfid/read")
        except Exception as e:
            print(f"[RFID] Erreur connexion MQTT: {e}")

        
        self.root_view = Factory.RFIDActionsRoot()
        self.root_view.parent_screen = self
        self.add_widget(self.root_view)
        
        # Load available weather cities from configuration.
        Clock.schedule_once(lambda dt: self.load_available_cities(), 0.05)
        
        # Load available contacts from contact mapping file.
        Clock.schedule_once(lambda dt: self.load_available_contacts(), 0.05)

        # Load persisted RFID action mapping.
        Clock.schedule_once(lambda dt: self.load_config(), 0.1)
        
        # Apply initial translated labels.
        Clock.schedule_once(lambda dt: self.update_labels(), 0.15)
    
    def update_labels(self):
        """Refresh translated labels for this screen."""
        print("[RFID] 🔄 Mise à jour labels...")
        
        if not hasattr(self.root_view, 'ids'):
            return
        
        self.root_view.ids.lbl_title.text = _("Configuración Tarjetas RFID")
        self.root_view.ids.lbl_instruction.text = _(
            "Presione 'Iniciar Configuración' y luego presente una tarjeta RFID para asignarle una acción."
        )
        self.root_view.ids.btn_start_config.text = _("🔧 Iniciar Configuración")
        
        # Ensure existing card widgets are rebuilt with translated strings.
        self._refresh_all_cards()
        
        print("[RFID] ✅ Labels updated")
    
    def _refresh_all_cards(self):
        """Rebuild all card widgets after language or label changes."""
        print("[RFID] 🔄 Refreshing card widgets...")
        
        # Snapshot card data before rebuilding widgets.
        cards_data = []
        for card_id, widget in self.card_widgets.items():
            cards_data.append({
                'card_id': card_id,
                'action': widget.action,
                'extra_data': widget.extra_data
            })
        
        # Remove current widgets and recreate from snapshot.
        container = self.root_view.ids.cards_container
        container.clear_widgets()
        self.card_widgets.clear()
        
        # Recreate widgets with translated labels.
        for card_data in cards_data:
            self.add_card_widget(
                card_data['card_id'],
                card_data['action'],
                card_data['extra_data']
            )
        
        print(f"[RFID] ✅ {len(cards_data)} cards refreshed")
    
    def _on_config_change(self, instance: Any, value: Dict[str, Any]) -> None:
        """Handle live configuration changes (for example language updates)."""
        print("[RFID] 🔄 Configuration change detected")
        
        # React only when language actually changes.
        new_lang = value.get('language', 'es')
        current_lang = get_current_language()
        
        if new_lang != current_lang:
            print(f"[RFID] 🌍 Language change detected: {current_lang} -> {new_lang}")
            
            # Force translation module reload.
            change_language(new_lang)
            
            # Refresh UI labels after language switch.
            Clock.schedule_once(lambda dt: self.update_labels(), 0.1)
    
    def go_back(self) -> None:
        """Navigate back to settings."""
        self.sm.current = "settings"
    
    def on_mqtt_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Handle incoming MQTT card-read events."""
        if msg.topic == "rfid/read":
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                if isinstance(payload, dict):
                    card_id = int(payload.get("data", {}).get("id", 0)) if "data" in payload else int(payload.get("id", 0))
                else:
                    card_id = int(msg.payload.decode("utf-8"))
                
                Clock.schedule_once(lambda dt: self.handle_card_detected(card_id))
            except Exception as e:
                print(f"[RFID] Erreur lecture carte: {e}")
    
    def handle_card_detected(self, card_id: int) -> None:
        """Handle card detection according to active mode."""
        if self.configuring:
            self.detected_card_id = card_id
            self.show_action_selection_popup(card_id)
        else:
            print(f"[RFID] Carte détectée: {card_id} (mode normal)")
    
    def load_available_cities(self):
        """Load active weather cities from unified settings."""
        try:
            settings = load_section("settings", {})
            cities = settings.get("weather_cities", [])
            self.available_cities = [str(c).strip() for c in cities if str(c).strip()]
            print(f"[RFID] ✅ {len(self.available_cities)} villes disponibles chargées")
        except Exception as e:
            print(f"[RFID] Erreur chargement villes: {e}")
            self.available_cities = []
    
    def load_available_contacts(self):
        """Load contact display names from list_contacts.txt."""
        self.available_contacts = []

        contact_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "contacts", "list_contacts.txt")
        )

        if not os.path.exists(contact_path):
            print("[RFID] ⚠️ list_contacts.txt introuvable")
            return

        try:
            with open(contact_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    name = line.split("=", 1)[0].strip()
                    if name:
                        self.available_contacts.append(name)

            print(f"[RFID] Contacts chargés : {self.available_contacts}")

        except Exception as e:
            print(f"[RFID] Erreur chargement contacts : {e}")
            self.available_contacts = []
    
    def load_config(self):
        """Load RFID action mapping from unified settings."""
        self.root_view.ids.cards_container.clear_widgets()
        self.card_widgets = {}
        try:
            settings = load_section("settings", {})
            mappings = settings.get("rfid_actions", {})
            if not isinstance(mappings, dict):
                mappings = {}
            for card_id_str, item in mappings.items():
                try:
                    card_id = int(card_id_str)
                except Exception:
                    continue
                action = (item or {}).get("action", "day_events")
                extra = (item or {}).get("extra", "")
                self.add_card_widget(card_id, action, extra)
        except Exception as e:
            print(f"[RFID] Erreur chargement config: {e}")
    
    def add_card_widget(self, card_id: int, action: str = "day_events", extra_data: str = "") -> None:
        """Create and mount a card widget in the UI."""
        if card_id in self.card_widgets:
            old_widget = self.card_widgets[card_id]
            self.root_view.ids.cards_container.remove_widget(old_widget)
        
        card_widget = RFIDCardWidget(card_id, action, extra_data, self)
        self.card_widgets[card_id] = card_widget
        self.root_view.ids.cards_container.add_widget(card_widget)
    
    def start_configuration_mode(self) -> None:
        """Active le mode configuration et envoie la commande MQTT"""
        self.configuring = True
        
        payload = {"mode": 1}
        self.mqtt_client.publish("rfid/init", json.dumps(payload))
        print("[RFID] Mode configuration activé")
        
        content = BoxLayout(orientation='vertical', spacing=dp(20), padding=dp(20))
        content.add_widget(Label(
            text=_("Modo Configuración Activado\n\nPresente una tarjeta RFID..."),
            font_size=sp(24),
            halign="center"
        ))
        
        btn_cancel = Button(
            text=_("Cancelar"),
            size_hint_y=None,
            height=dp(60),
            font_size=sp(22)
        )
        content.add_widget(btn_cancel)
        
        self.config_popup = Popup(
            title=_("Esperando tarjeta RFID"),
            content=wrap_popup_content(content),
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )
        
        def cancel_config(instance):
            self.configuring = False
            self.config_popup.dismiss()
        
        btn_cancel.bind(on_release=cancel_config)
        self.config_popup.open()
    
    def show_action_selection_popup(self, card_id: int) -> None:
        """Open the action-selection popup."""
        if self.config_popup:
            self.config_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        
        content.add_widget(Label(
            text=f"{_('ID Tarjeta')}: {card_id}",
            font_size=sp(28),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))
        
        content.add_widget(Label(
            text=_("¿A qué acción quiere asignar esta tarjeta?"),
            font_size=sp(22),
            size_hint_y=None,
            height=dp(60)
        ))
        
        actions_grid = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(200))
        
        actions = [
            ("day_events", _("Eventos del Día")),
            ("weather", _("Tiempo")),
            ("videocall", _("Videollamada"))
        ]
        
        for action_code, action_label in actions:
            btn = Button(
                text=action_label,
                font_size=sp(20),
                size_hint_y=None,
                height=dp(60)
            )
            btn.bind(on_release=lambda x, ac=action_code: self.on_action_selected(card_id, ac))
            actions_grid.add_widget(btn)
        
        content.add_widget(actions_grid)
        
        btn_cancel = Button(
            text=_("Cancelar"),
            size_hint_y=None,
            height=dp(60),
            font_size=sp(22)
        )
        content.add_widget(btn_cancel)
        
        self.config_popup = Popup(
            title=_("Seleccionar Acción"),
            content=wrap_popup_content(content),
            size_hint=(0.7, 0.7),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )
        
        def cancel_config(instance):
            self.configuring = False
            self.config_popup.dismiss()
        
        btn_cancel.bind(on_release=cancel_config)
        self.config_popup.open()
    
    def on_action_selected(self, card_id: int, action: str) -> None:
        """Handle selected action from the configuration flow."""
        if action == "weather":
            self.show_city_dropdown_popup(card_id, action)
        elif action == "videocall":
            self.show_contact_input_popup(card_id, action)
        else:
            self.confirm_configuration(card_id, action, "")
    
    def show_city_dropdown_popup(self, card_id: int, action: str) -> None:
        """Open city selection popup."""
        self.config_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        
        content.add_widget(Label(
            text=f"{_('ID Tarjeta')}: {card_id}",
            font_size=sp(26),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))
        
        content.add_widget(Label(
            text=_("Seleccione la ciudad:"),
            font_size=sp(22),
            size_hint_y=None,
            height=dp(50)
        ))
        
        if self.available_cities:
            city_spinner = Spinner(
                text=self.available_cities[0],
                values=self.available_cities,
                size_hint_y=None,
                height=dp(60),
                font_size=sp(22),
                background_color=(1, 1, 1, 1),
                color=(0, 0, 0, 1)
            )
        else:
            content.add_widget(Label(
                text=_("⚠️ No hay ciudades disponibles en la configuración."),
                font_size=sp(20),
                color=(0.9, 0.2, 0.2, 1),
                size_hint_y=None,
                height=dp(60)
            ))
            city_spinner = None
        
        if city_spinner:
            content.add_widget(city_spinner)
        
        btn_box = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(70))
        
        btn_cancel = Button(text=_("Cancelar"), font_size=sp(22))
        btn_confirm = Button(text=_("Confirmar"), font_size=sp(22))
        
        btn_box.add_widget(btn_cancel)
        btn_box.add_widget(btn_confirm)
        content.add_widget(btn_box)
        
        self.config_popup = Popup(
            title=_("Configuración Tiempo"),
            content=wrap_popup_content(content),
            size_hint=(0.6, 0.5),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )
        
        def on_confirm(instance):
            if city_spinner:
                city = city_spinner.text
                self.confirm_configuration(card_id, action, city)
            else:
                print("[RFID] ⚠️ Aucune ville sélectionnée")
        
        def on_cancel(instance):
            self.configuring = False
            self.config_popup.dismiss()
        
        btn_confirm.bind(on_release=on_confirm)
        btn_cancel.bind(on_release=on_cancel)
        
        self.config_popup.open()
    
    def show_contact_input_popup(self, card_id: int, action: str) -> None:
        """Open contact selection popup."""
        self.config_popup.dismiss()

        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))

        content.add_widget(Label(
            text=f"{_('ID Tarjeta')}: {card_id}",
            font_size=sp(26),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))

        content.add_widget(Label(
            text=_("Seleccione el contacto:"),
            font_size=sp(22),
            size_hint_y=None,
            height=dp(50)
        ))

        if self.available_contacts:
            contact_spinner = Spinner(
                text=self.available_contacts[0],
                values=self.available_contacts,
                size_hint_y=None,
                height=dp(60),
                font_size=sp(22),
            )
            content.add_widget(contact_spinner)
        else:
            content.add_widget(Label(
                text="Aucun contact disponible",
                font_size=sp(20),
                color=(0.9, 0.2, 0.2, 1)
            ))
            contact_spinner = None

        # boutons
        btn_box = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(70))
        btn_cancel = Button(text=_("Cancelar"), font_size=sp(22))
        btn_confirm = Button(text=_("Confirmar"), font_size=sp(22))
        btn_box.add_widget(btn_cancel)
        btn_box.add_widget(btn_confirm)
        content.add_widget(btn_box)

        self.config_popup = Popup(
            title=_("Seleccionar Contacto"),
            content=wrap_popup_content(content),
            size_hint=(0.6, 0.5),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )

        def on_confirm(instance):
            if contact_spinner:
                contact = contact_spinner.text
                self.confirm_configuration(card_id, action, contact)

        btn_confirm.bind(on_release=on_confirm)
        btn_cancel.bind(on_release=lambda x: self.config_popup.dismiss())

        self.config_popup.open()
    
    def confirm_configuration(self, card_id: int, action: str, extra_data: str = "") -> None:
        """Persist and apply a confirmed RFID mapping."""
        action_code = self._get_action_code(action)
        payload = {
            "id": int(card_id),
            "action": action_code
        }
        self.mqtt_client.publish("rfid/config", json.dumps(payload))
        print(f"[MQTT] RFID config sent: {payload}")
        
        self.add_card_widget(card_id, action, extra_data)
        
        self.save_to_config(card_id, action, extra_data)
        
        self.publish_rfid_reload_event()
        
        if self.config_popup:
            self.config_popup.dismiss()
        self.configuring = False
        
        msg_content = Label(
            text=f"✅ {_('Tarjeta')} {card_id} {_('configurada con éxito')}!",
            font_size=sp(24)
        )
        msg_popup = Popup(
            title=_("Configuración Exitosa"),
            content=wrap_popup_content(msg_content, padding=22),
            size_hint=(0.5, 0.3),
            auto_dismiss=True,
            **popup_theme_kwargs()
        )
        msg_popup.open()
        Clock.schedule_once(lambda dt: msg_popup.dismiss(), 2)
    
    def publish_rfid_reload_event(self) -> None:
        """Publish an MQTT event requesting RFID action reload."""
        try:
            from datetime import datetime
            
            payload = {
                "action": "reload",
                "timestamp": datetime.now().isoformat()
            }
            
            self.mqtt_client.publish("rfid/actions_reload", json.dumps(payload))
            print("[RFID] 📤 Événement MQTT 'rfid/actions_reload' publié")
        
        except Exception as e:
            print(f"[RFID] ⚠️ Erreur publication MQTT: {e}")
    
    def save_to_config(self, card_id: int, action: str, extra_data: str = "") -> None:
        """Persist card mapping into unified settings config."""
        try:
            settings = load_section("settings", {})
            mappings = settings.get("rfid_actions", {})
            if not isinstance(mappings, dict):
                mappings = {}
            mappings[str(card_id)] = {"action": action, "extra": extra_data or ""}
            settings["rfid_actions"] = mappings
            save_section("settings", settings)
            print(f"[RFID] Configuration sauvegardée: carte {card_id} → {action}")
        except Exception as e:
            print(f"[RFID] Erreur sauvegarde: {e}")
    
    def remove_card(self, card_id: int) -> None:
        """Remove a card from UI and persisted config."""
        if card_id in self.card_widgets:
            widget = self.card_widgets[card_id]
            self.root_view.ids.cards_container.remove_widget(widget)
            del self.card_widgets[card_id]
            
            self.remove_from_config(card_id)
            self.publish_rfid_reload_event()

    def confirm_remove_card(self, card_id: int) -> None:
        content = BoxLayout(orientation='vertical', spacing=dp(14), padding=dp(20))
        content.add_widget(Label(
            text=_("¿Seguro que quieres eliminar esta tarjeta RFID?"),
            font_size=sp(24),
            color=(0, 0, 0, 1),
            halign="center",
            valign="middle"
        ))

        buttons = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(12))
        btn_cancel = Button(text=_("Cancelar"), font_size=sp(22))
        btn_confirm = Button(text=_("Confirmar"), font_size=sp(22))
        buttons.add_widget(btn_cancel)
        buttons.add_widget(btn_confirm)
        content.add_widget(buttons)

        popup = Popup(
            title=_("Confirmar borrado"),
            content=wrap_popup_content(content),
            size_hint=(0.62, 0.4),
            auto_dismiss=False,
            **popup_theme_kwargs()
        )

        btn_cancel.bind(on_release=popup.dismiss)
        btn_confirm.bind(on_release=lambda *_: (popup.dismiss(), self.remove_card(card_id)))
        popup.open()
    
    def remove_from_config(self, card_id: int) -> None:
        """Remove a card entry from unified settings."""
        try:
            settings = load_section("settings", {})
            mappings = settings.get("rfid_actions", {})
            if isinstance(mappings, dict) and str(card_id) in mappings:
                mappings.pop(str(card_id), None)
                settings["rfid_actions"] = mappings
                save_section("settings", settings)
            print(f"[RFID] Carte {card_id} supprimée du config unifié")
        except Exception as e:
            print(f"[RFID] Erreur suppression: {e}")
    
    def _get_action_code(self, action_name: str) -> int:
        """Map action name to numeric action code expected by firmware."""
        action_codes = {
            "day_events": 2,
            "weather": 3,
            "videocall": 5
        }
        return action_codes.get(action_name, 2)
    
    def on_pre_enter(self, *args: Any) -> None:
        """Refresh language-dependent content before entering the screen."""
        print("[RFID] 🔄 on_pre_enter appelé")
        
        # Force reload of language from settings.json.
        app = App.get_running_app()
        if app and hasattr(app, 'cfg'):
            current_lang = app.cfg.data.get("language", "es")
            change_language(current_lang)
            print(f"[RFID] 🌍 Language forced: {current_lang}")
        
        # Reload dynamic sources.
        self.load_available_cities()
        self.load_available_contacts()
        
        # Refresh labels and card widgets.
        self.update_labels()
        
        print("[RFID] ✅ Screen refreshed")
    
    def on_leave(self, *args: Any) -> None:
        """Release temporary state when leaving the screen."""
        self.configuring = False
        if self.config_popup:
            self.config_popup.dismiss()

Factory.register("RFIDActionsScreen", cls=RFIDActionsScreen)
