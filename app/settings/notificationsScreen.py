from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import DictProperty, StringProperty, NumericProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.popup import Popup
from kivy.uix.colorpicker import ColorPicker
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp
from kivy.app import App
from kivy.clock import Clock
from translation import _
import os
import threading

# ========== IMPORT DU MODULE LED CENTRALISÉ ==========
from notifications.mqtt_led_sender import send_led_config_from_dict
from notifications.notification_runtime import (
    AUDIO_AVAILABLE,
    NONE_RINGTONE,
    load_notification_config as runtime_load_notification_config,
    load_ringtones as runtime_load_ringtones,
    normalize_ringtone_name,
    play_ringtone_file,
    save_notification_config as runtime_save_notification_config,
    stop_ringtone as runtime_stop_ringtone,
)
from popup_style import wrap_popup_content, popup_theme_kwargs

# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

class PlayButton(ButtonBehavior, AnchorLayout):
    """Bouton play avec icône"""
    pass

class PlayStopButton(ButtonBehavior, AnchorLayout):
    """Play/Stop button with icon change"""
    icon_source = StringProperty("")
    is_playing = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(is_playing=self._update_color)
    
    def _update_color(self, *args):
        """Update button color based on state"""
        self.canvas.before.clear()
        with self.canvas.before:
            # Red when playing, green when stopped
            if self.is_playing:
                Color(0.9, 0.2, 0.2, 1)  # Red
            else:
                Color(0.2, 0.7, 0.3, 1)  # Green
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(8)]
            )
            Color(0, 0, 0, 0.85)
            from kivy.graphics import Line
            Line(
                width=2,
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(8))
            )

class ColorPreview(ButtonBehavior, Widget):
    hex_color = StringProperty("#ffffff")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_rect, size=self.update_rect, hex_color=self.update_color)
        self._build()
    
    def _build(self):
        r, g, b, a = get_color_from_hex(self.hex_color)
        with self.canvas:
            self._col = Color(r, g, b, a)
            self._rect = Rectangle(pos=self.pos, size=self.size)
    
    def update_rect(self, *args):
        if hasattr(self, "_rect"):
            self._rect.pos = self.pos
            self._rect.size = self.size
    
    def update_color(self, *args):
        r, g, b, a = get_color_from_hex(self.hex_color)
        self._col.rgba = (r, g, b, a)

Factory.register("ColorPreview", cls=ColorPreview)
Factory.register("IconBadge", cls=IconBadge)
Factory.register("PlayButton", cls=PlayButton)
Factory.register("PlayStopButton", cls=PlayStopButton)

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

<PlayStopButton>:
    is_playing: False
    size_hint: None, None
    size: dp(72), dp(72)
    padding: dp(6)
    canvas.before:
        Color:
            rgba: (0.9, 0.2, 0.2, 1) if self.is_playing else (0.2, 0.7, 0.3, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8),]
        Color:
            rgba: 0,0,0,0.85
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
    Image:
        source: root.icon_source
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(42), dp(42)

<ColorPreview@ButtonBehavior+Widget>:
    hex_color: "#ffffff"

<LEDColorsRoot@FloatLayout>:
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
                    icon_source: app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "images/back.png"
                    on_release: app.root.current = "settings"
        
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
                size_hint: 0.96, 0.90
                bar_width: dp(12)
                do_scroll_x: False
                
                GridLayout:
                    id: strips_grid
                    cols: 1
                    spacing: dp(20)
                    padding: dp(30)
                    size_hint_y: None
                    height: self.minimum_height

<StripCard@BoxLayout>:
    orientation: "vertical"
    padding: dp(24)
    spacing: dp(16)
    size_hint_y: None
    height: dp(550)
    canvas.before:
        Color:
            rgba: 1,1,1,1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(16),]
        Color:
            rgba: 0,0,0,0.85
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
    
    # Title
    Label:
        text: root.title
        font_size: sp(28)
        bold: True
        color: 0,0,0,1
        size_hint_y: None
        height: dp(36)
        halign: "left"
        valign: "middle"
        text_size: self.size
        padding: [dp(8), 0]
    
    # Separator line
    Widget:
        size_hint_y: None
        height: dp(2)
        canvas:
            Color:
                rgba: 0,0,0,0.2
            Rectangle:
                pos: self.pos
                size: self.size
    
    # Intensity
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(20)
        size_hint_y: None
        height: dp(50)
        
        Label:
            id: lbl_intensity
            text: ""
            bold: True
            font_size: sp(22)
            color: 0,0,0,1
            size_hint_x: 0.25
            halign: "left"
            valign: "middle"
            text_size: self.size
        
        Slider:
            id: slider
            min: 0
            max: 255
            value: root.intensity
            size_hint_x: 1.5
            on_value: root.on_intensity(self, self.value)
        
        Label:
            text: str(int(slider.value))
            font_size: sp(22)
            bold: True
            color: 0,0,0,1
            size_hint_x: 0.2
            halign: "center"
            valign: "middle"
            text_size: self.size
    
    # Color
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(20)
        size_hint_y: None
        height: dp(80)
        
        Label:
            id: lbl_color
            text: ""
            bold: True
            font_size: sp(22)
            color: 0,0,0,1
            size_hint_x: 0.25
            halign: "left"
            valign: "middle"
            text_size: self.size
        
        ColorPreview:
            id: color_preview
            hex_color: root.color
            size_hint_x: None
            width: dp(200)
            canvas.before:
                Color:
                    rgba: 0,0,0,0.85
                Line:
                    width: 2
                    rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
            on_release: root.open_color_picker()
        
        TextInput:
            id: hex_input
            text: root.color
            font_size: sp(18)
            multiline: False
            size_hint_x: None
            width: dp(140)
            on_text: root.on_color(self, self.text)
            padding: [dp(12), dp(8)]
    
    # Mode
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(20)
        size_hint_y: None
        height: dp(50)
        
        Label:
            id: lbl_mode
            text: ""
            bold: True
            font_size: sp(22)
            color: 0,0,0,1
            size_hint_x: 0.25
            halign: "left"
            valign: "middle"
            text_size: self.size
        
        Spinner:
            id: mode_spinner
            text: root.mode
            font_size: sp(20)
            values: root.mode_values
            size_hint_x: 0.55
            on_text: root.on_mode(self, self.text)
    
    # Ringtone
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(30)
        size_hint_y: None
        height: dp(75)
        
        Label:
            id: lbl_ringtone
            text: ""
            bold: True
            font_size: sp(22)
            color: 0,0,0,1
            size_hint_x: 0.25
            halign: "left"
            valign: "middle"
            text_size: self.size
        
        Spinner:
            id: ringtone_spinner
            text: root.ringtone
            font_size: sp(20)
            values: root.available_ringtones
            size_hint_x: 0.50
            on_text: root.on_ringtone(self, self.text)
        
        PlayStopButton:
            id: play_stop_btn
            icon_source: root.play_icon
            on_release: root.toggle_ringtone()
    
    Widget:
        size_hint_y: 0.1
    
    # Actions
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(12)
        size_hint_y: None
        height: dp(56)

        Button:
            id: btn_update
            text: ""
            font_size: sp(22)
            background_color: 0,0,0,0
            canvas.before:
                Color:
                    rgba: 0.15, 0.55, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12),]
            on_release: root.on_update()

        Button:
            id: btn_simulate
            text: ""
            font_size: sp(22)
            background_color: 0,0,0,0
            canvas.before:
                Color:
                    rgba: 0.2, 0.65, 0.3, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12),]
            on_release: root.on_simulate()
"""

Builder.load_string(KV)

# ----------------- STRIP CARD WIDGET -----------------

class StripCard(BoxLayout):
    title = StringProperty("")
    strip_key = StringProperty("")
    intensity = NumericProperty(255)
    color = StringProperty("#ffffff")
    mode = StringProperty("")
    ringtone = StringProperty("")
    available_ringtones = ListProperty([])
    mode_values = ListProperty([])
    play_icon = StringProperty("images/play.png")
    stop_icon = StringProperty("images/stop.png")
    
    parent_screen = None
    initialized = False
    color_popup = ObjectProperty(None, allownone=True)
    
    # Audio playback state
    _ringtone_thread = None
    _stop_event = None
    _is_playing = False
    
    def on_kv_post(self, *args):
        self.initialized = True
        self.update_labels()
    
    def update_labels(self):
        """Update labels with translations"""
        if not hasattr(self, 'ids'):
            return
        
        self.ids.lbl_intensity.text = _("Intensidad:")
        self.ids.lbl_color.text = _("Color:")
        self.ids.lbl_mode.text = _("Modo:")
        self.ids.lbl_ringtone.text = _("Tono de llamada:")
        self.ids.btn_update.text = _("Actualizar Configuración")
        self.ids.btn_simulate.text = _("Simular Notificación")
        
        # Update mode spinner values
        self.mode_values = [_("Encendido"), _("Apagado"), _("Parpadeo"), _("Parpadeo Gradual")]
        self._refresh_ringtone_spinner()
    
    def on_intensity(self, instance, value):
        if not self.initialized or not self.parent_screen:
            return
        self.parent_screen.update_strip_value(self.strip_key, "intensity", int(value))
    
    def on_color(self, instance, hex_color):
        if not self.initialized or not self.parent_screen:
            return
        
        hex_str = hex_color.strip()
        if not hex_str.startswith('#'):
            hex_str = '#' + hex_str
        if len(hex_str) == 7:
            self.color = hex_str
            self.parent_screen.update_strip_value(self.strip_key, "color", hex_str)
    
    def on_mode(self, instance, mode_text):
        if not self.initialized or not self.parent_screen:
            return
        
        mode_map = {
            _("Encendido"): "ON",
            _("Apagado"): "OFF",
            _("Parpadeo"): "BLINK",
            _("Parpadeo Gradual"): "FADING_BLINK"
        }
        
        technical_mode = mode_map.get(mode_text, "ON")
        self.mode = mode_text
        self.parent_screen.update_strip_value(self.strip_key, "mode", technical_mode)
    
    def on_ringtone(self, instance, ringtone):
        if not self.initialized or not self.parent_screen:
            return
        stored_ringtone = self.parent_screen.to_stored_ringtone(ringtone)
        self.ringtone = self.parent_screen.to_display_ringtone(stored_ringtone)
        self.parent_screen.update_strip_value(self.strip_key, "ringtone", stored_ringtone)
    
    def toggle_ringtone(self):
        """Toggle between play and stop"""
        if self._is_playing:
            self.stop_ringtone()
        else:
            self.play_ringtone()
    
    def play_ringtone(self):
        """Play the selected ringtone"""
        ringtone_name = self.parent_screen.to_stored_ringtone(self.ringtone) if self.parent_screen else self.ringtone

        if ringtone_name == NONE_RINGTONE or not ringtone_name or ringtone_name.strip() == "":
            print("[RINGTONE] No ringtone selected")
            return
        
        if not AUDIO_AVAILABLE:
            print("[RINGTONE] ⚠ No audio backend available")
            return
        
        # Stop previous playback if exists
        if self._ringtone_thread and self._ringtone_thread.is_alive():
            print("[RINGTONE] Already playing, stopping first...")
            self.stop_ringtone()
            return
        
        # Update button state
        self._is_playing = True
        self.ids.play_stop_btn.is_playing = True
        self.ids.play_stop_btn.icon_source = self.stop_icon

        def _finish():
            Clock.schedule_once(lambda dt: self._reset_button_state(), 0)

        if not play_ringtone_file(ringtone_name, on_finish=_finish):
            self._reset_button_state()
            return

        self._ringtone_thread = threading.Thread(target=lambda: None, daemon=True)
        self._ringtone_thread.start()

    def _refresh_ringtone_spinner(self):
        if not hasattr(self, "ids") or "ringtone_spinner" not in self.ids:
            return
        if not self.parent_screen:
            return

        self.available_ringtones = self.parent_screen.get_display_ringtones()
        self.ringtone = self.parent_screen.to_display_ringtone(self.parent_screen.to_stored_ringtone(self.ringtone))
        self.ids.ringtone_spinner.values = self.available_ringtones
        self.ids.ringtone_spinner.text = self.ringtone
    
    def stop_ringtone(self):
        """Stop the currently playing ringtone"""
        if not self._is_playing:
            return
        
        print("[RINGTONE] Stopping playback...")
        runtime_stop_ringtone()
        self._reset_button_state()
    
    def _reset_button_state(self):
        """Reset button to play state"""
        self._is_playing = False
        if hasattr(self, 'ids') and 'play_stop_btn' in self.ids:
            self.ids.play_stop_btn.is_playing = False
            self.ids.play_stop_btn.icon_source = self.play_icon
        print("[RINGTONE] Button reset to play state")
    
    def open_color_picker(self):
        """Open color picker in popup"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        picker = ColorPicker()
        
        try:
            r, g, b, a = get_color_from_hex(self.color)
            picker.color = (r, g, b, a)
        except:
            picker.color = (1, 1, 1, 1)
        
        def on_color_change(instance, value):
            r, g, b, a = value
            hex_color = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
            self.color = hex_color
            if self.initialized and self.parent_screen:
                self.parent_screen.update_strip_value(self.strip_key, "color", hex_color)
        
        picker.bind(color=on_color_change)
        
        close_btn = Button(
            text=_('Cerrar'),
            size_hint_y=None,
            height=dp(50),
            font_size=sp(20)
        )
        
        content.add_widget(picker)
        content.add_widget(close_btn)
        
        self.color_popup = Popup(
            title=_('Seleccionar Color'),
            content=wrap_popup_content(content),
            size_hint=(0.7, 0.8),
            auto_dismiss=True,
            **popup_theme_kwargs()
        )
        
        close_btn.bind(on_release=self.color_popup.dismiss)
        self.color_popup.open()
    
    def on_update(self):
        if not self.parent_screen:
            return
        
        # Publish LED config
        self.parent_screen.publish_config(self.strip_key)
        
        # ========== TURN OFF LEDS AFTER 5 SECONDS ==========
        from notifications.mqtt_led_sender import turn_off_leds
        Clock.schedule_once(lambda dt: turn_off_leds(), 5)

    def on_simulate(self):
        if not self.parent_screen:
            return
        self.parent_screen.simulate_notification(self.strip_key)

Factory.register("StripCard", cls=StripCard)

# ----------------- SCREEN PRINCIPALE -----------------

class NotificationsScreen(Screen):
    ledStrips = DictProperty({
        "videollamada": {"group": 1, "intensity": 255, "color": "#00FF00", "mode": "ON", "ringtone": NONE_RINGTONE},
        "nuevo_evento": {"group": 2, "intensity": 255, "color": "#FF0000", "mode": "ON", "ringtone": NONE_RINGTONE},
        "nueva_foto": {"group": 3, "intensity": 255, "color": "#0000FF", "mode": "BLINK", "ringtone": NONE_RINGTONE},
    })
    
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        
        self.root_view = Factory.LEDColorsRoot()
        self.add_widget(self.root_view)
        
        # ========== CHARGER LA CONFIGURATION SAUVEGARDÉE ==========
        self.load_config()
        
        # Charger les sonneries disponibles
        self.available_ringtones = self.load_ringtones()
        
        # Injecter les StripCard
        Clock.schedule_once(lambda dt: self.load_strip_cards(), 0.1)
        
        # Mettre à jour le titre de l'écran
        Clock.schedule_once(lambda dt: self.update_labels(), 0.15)
    
    def update_labels(self):
        """✅ Met à jour les labels traduits"""
        print("[NOTIF_SCREEN] 🔄 Mise à jour labels...")
        
        if hasattr(self.root_view, 'ids') and 'lbl_title' in self.root_view.ids:
            self.root_view.ids.lbl_title.text = _("Configuración notificaciones")
        
        # ✅ IMPORTANT : Rafraîchir tous les StripCard
        self._refresh_all_strip_cards()
        
        print("[NOTIF_SCREEN] ✅ Labels mis à jour")
    
    def _refresh_all_strip_cards(self):
        """Recrée tous les StripCard avec les nouvelles traductions"""
        print("[NOTIF_SCREEN] 🔄 Rafraîchissement des StripCard...")
        
        if not hasattr(self.root_view, 'ids') or 'strips_grid' not in self.root_view.ids:
            print("[NOTIF_SCREEN] ⚠️ strips_grid non disponible")
            return
        
        # Supprimer tous les widgets existants
        grid = self.root_view.ids.strips_grid
        grid.clear_widgets()
        
        # Recréer les StripCard avec load_strip_cards()
        self.load_strip_cards()
        
        print("[NOTIF_SCREEN] ✅ StripCard rafraîchis")
    
    # ========== SAUVEGARDE/CHARGEMENT ==========
    
    def load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        config = runtime_load_notification_config()
        for key in self.ledStrips.keys():
            if key in config:
                self.ledStrips[key].update(config[key])
        print("[CONFIG] ✓ Configuration chargée")
    
    def save_config(self):
        """Sauvegarde la configuration dans le fichier JSON"""
        ok = runtime_save_notification_config(dict(self.ledStrips))
        if ok:
            print("[CONFIG] ✓ Configuration sauvegardée")
        return ok
    
    def update_strip_value(self, strip, field, value):
        """Mise à jour + sauvegarde automatique"""
        if field == "ringtone":
            value = self.normalize_ringtone(value)
        self.ledStrips[strip][field] = value
        self.save_config()
    
    def publish_config(self, strip):
        """Publie la configuration d'un strip sur MQTT en utilisant le module centralisé"""
        payload = self.ledStrips[strip]
        
        # Utiliser le module centralisé
        send_led_config_from_dict(payload)
        
        print(f"[NOTIF_SCREEN] Configuration publiée pour {strip}")
    
    # ========== AUTRES MÉTHODES ==========
    
    def load_ringtones(self):
        ringtones = runtime_load_ringtones()
        print(f"[RINGTONE] Found {len(ringtones)-1} ringtones")
        return ringtones

    def normalize_ringtone(self, ringtone):
        ringtone_name = normalize_ringtone_name(ringtone)
        if ringtone_name in {_("Ninguna"), _("Aucune")}:
            return NONE_RINGTONE
        return ringtone_name

    def to_display_ringtone(self, ringtone):
        ringtone_name = self.normalize_ringtone(ringtone)
        if ringtone_name == NONE_RINGTONE:
            return _("Ninguna")
        return ringtone_name

    def to_stored_ringtone(self, ringtone):
        return self.normalize_ringtone(ringtone)

    def get_display_ringtones(self):
        return [self.to_display_ringtone(ringtone) for ringtone in self.available_ringtones]
    
    def load_strip_cards(self):
        """Charge les StripCard avec les traductions actuelles"""
        if not hasattr(self.root_view, 'ids') or 'strips_grid' not in self.root_view.ids:
            print("[NOTIF_SCREEN] ⚠️ strips_grid non disponible pour load_strip_cards")
            return
        
        grid = self.root_view.ids.strips_grid
        
        titles = {
            "videollamada": _("Videollamada"),
            "nuevo_evento": _("Nuevo Evento"),
            "nueva_foto": _("Nueva Foto"),
        }
        
        mode_map = {
            "ON": _("Encendido"),
            "OFF": _("Apagado"),
            "BLINK": _("Parpadeo"),
            "FADING_BLINK": _("Parpadeo Gradual")
        }
        
        for key, data in self.ledStrips.items():
            technical_mode = data["mode"]
            translated_mode = mode_map.get(technical_mode, _("Encendido"))
            
            card = StripCard(
                title=titles.get(key, key.capitalize()),
                strip_key=key,
                intensity=data["intensity"],
                color=data["color"],
                mode=translated_mode,
                ringtone=self.to_display_ringtone(data.get("ringtone", NONE_RINGTONE)),
                available_ringtones=self.get_display_ringtones(),
                mode_values=[_("Encendido"), _("Apagado"), _("Parpadeo"), _("Parpadeo Gradual")]
            )
            card.parent_screen = self
            grid.add_widget(card)
        
        print(f"[NOTIF_SCREEN] ✅ {len(self.ledStrips)} StripCard créés")
    
    def on_pre_enter(self, *args):
        """✅ Mise à jour des traductions avant d'entrer dans l'écran"""
        print("[NOTIF_SCREEN] 🔄 on_pre_enter")
        self.update_labels()
        self.available_ringtones = self.load_ringtones()

    def simulate_notification(self, strip_key):
        app = App.get_running_app()
        manager = getattr(app, "notification_manager", None) if app else None
        if not manager:
            print("[NOTIF_SCREEN] ⚠️ NotificationManager non disponible pour simulation")
            return

        if strip_key == "videollamada":
            manager.show_videocall_notification("Test Usuario", room=None)
        elif strip_key == "nuevo_evento":
            manager.show_event_notification(_("Evento de prueba"), "2026-04-01 10:00")
        elif strip_key == "nueva_foto":
            manager.show_message_notification(_("Usuario de prueba"), has_image=True, has_text=True)
        else:
            print(f"[NOTIF_SCREEN] ⚠️ Tipo de simulación no soportado: {strip_key}")

Factory.register("NotificationsScreen", cls=NotificationsScreen)
