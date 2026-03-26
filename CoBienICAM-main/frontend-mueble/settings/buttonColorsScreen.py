from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import DictProperty, StringProperty, ListProperty, ObjectProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.popup import Popup
from kivy.uix.colorpicker import ColorPicker
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp
from kivy.app import App
from translation import _
import json
import paho.mqtt.client as mqtt
import os
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

# ✅ MQTT Client CORRIGÉ
mqtt_client = mqtt.Client()

try:
    mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
    mqtt_client.loop_start()
    print("[MQTT_BUTTONS] ✓ Client MQTT démarré pour button/config")
except Exception as e:
    print(f"[MQTT_BUTTONS] ✗ Erreur connexion: {e}")

# ✅ CONSTANTES CORRIGÉES SELON LE CODE C
SHAPES = {
    "all": 0,           # ALL
    "square": 1,        # SQUARE
    "diamond": 2,       # DIAMOND
    "plus": 3,          # PLUS (croix)
    "X": 4,             # IXE
    "only_center": 5    # ONLY_CENTER
}

MODES = {
    "on": 0,            # ON
    "off": 1,           # OFF
    "blink": 2,         # BLINK
    "fading_blink": 3   # FADING_BLINK
}

# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

class ColorPreview(ButtonBehavior, Widget):
    hex_color = StringProperty("#ffffff")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_rect, size=self.update_rect, hex_color=self.update_color)
        self._build()

    def _build(self):
        try:
            color = get_color_from_hex(self.hex_color)
            if len(color) == 4:
                r, g, b, a = color
            else:
                r, g, b, a = 1, 1, 1, 1
        except:
            r, g, b, a = 1, 1, 1, 1
        
        with self.canvas:
            self._col = Color(r, g, b, a)
            self._rect = Rectangle(pos=self.pos, size=self.size)

    def update_rect(self, *args):
        if hasattr(self, "_rect"):
            self._rect.pos = self.pos
            self._rect.size = self.size

    def update_color(self, *args):
        if not hasattr(self, "_col"):
            return
        
        try:
            color = get_color_from_hex(self.hex_color)
            if len(color) == 4:
                r, g, b, a = color
                self._col.rgba = (r, g, b, a)
            else:
                self._col.rgba = (1, 1, 1, 1)
        except:
            self._col.rgba = (1, 1, 1, 1)

Factory.register("ColorPreview", cls=ColorPreview)
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

<ButtonColorsRoot@FloatLayout>:
    pic1_color: "#ffffff"
    pic2_color: "#ffffff"
    pic1_shape: "all"
    pic1_mode: "on"
    pic2_shape: "all"
    pic2_mode: "on"
    pic1_intensity: 255
    pic2_intensity: 255
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

        # ---------- CABECERA ----------
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

        # ---------- CONTENIDO PRINCIPAL ----------
        ScrollView:
            do_scroll_x: False
            bar_width: dp(8)
            
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(30)
                padding: dp(40)
                canvas.before:
                    Color:
                        rgba: 1,1,1,0.85
                    RoundedRectangle:
                        size: self.size
                        pos: self.pos
                        radius: [R_CARD,]

                # ---------- BOTÓN PIC1 ----------
                BoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(610)
                    spacing: dp(20)
                    padding: dp(24)
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

                    Label:
                        id: lbl_pic1
                        text: "PIC1"
                        font_size: sp(32)
                        bold: True
                        color: 0,0,0,1
                        size_hint_y: None
                        height: dp(40)
                        halign: "left"
                        valign: "middle"
                        text_size: self.size

                    # Couleur
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_color_pic1
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        ColorPreview:
                            id: color_preview_pic1
                            hex_color: root.pic1_color
                            size_hint_x: None
                            width: dp(200)
                            canvas.before:
                                Color:
                                    rgba: 0,0,0,0.85
                                Line:
                                    width: 2
                                    rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
                            on_release: root.parent_screen.open_color_picker("PIC1") if root.parent_screen else None

                        TextInput:
                            id: hex_input_pic1
                            text: root.pic1_color
                            font_size: sp(20)
                            multiline: False
                            size_hint_x: None
                            width: dp(160)
                            on_text: root.parent_screen.on_color_change("PIC1", self.text) if root.parent_screen else None
                            padding: [dp(12), dp(10)]

                    # Forme
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_shape_pic1
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Spinner:
                            id: spinner_shape_pic1
                            text: root.pic1_shape
                            values: ["all", "square", "diamond", "plus", "X", "only_center"]
                            font_size: sp(20)
                            size_hint_x: 1
                            on_text: root.parent_screen.on_shape_change("PIC1", self.text) if root.parent_screen else None

                    # Mode
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_mode_pic1
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Spinner:
                            id: spinner_mode_pic1
                            text: root.pic1_mode
                            values: ["on", "off", "blink", "fading_blink"]
                            font_size: sp(20)
                            size_hint_x: 1
                            on_text: root.parent_screen.on_mode_change("PIC1", self.text) if root.parent_screen else None

                    # Intensité
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_intensity_pic1
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Slider:
                            id: slider_intensity_pic1
                            min: 0
                            max: 255
                            value: root.pic1_intensity
                            step: 1
                            size_hint_x: 0.6
                            on_value: root.pic1_intensity = int(self.value)

                        Label:
                            id: lbl_intensity_value_pic1
                            text: str(int(root.pic1_intensity))
                            font_size: sp(22)
                            color: 0,0,0,1
                            size_hint_x: 0.15
                            halign: "center"
                            valign: "middle"

                    # Botón Actualizar PIC1
                    Button:
                        id: btn_update_pic1
                        text: ""
                        font_size: sp(20)
                        size_hint_y: None
                        height: dp(60)
                        background_color: 0,0,0,0
                        canvas.before:
                            Color:
                                rgba: 0.15, 0.55, 0.95, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(10),]
                        on_release: root.parent_screen.on_update_single("PIC1") if root.parent_screen else None

                # ---------- BOTÓN PIC2 ----------
                BoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(610)
                    spacing: dp(20)
                    padding: dp(24)
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

                    Label:
                        id: lbl_pic2
                        text: "PIC2"
                        font_size: sp(32)
                        bold: True
                        color: 0,0,0,1
                        size_hint_y: None
                        height: dp(40)
                        halign: "left"
                        valign: "middle"
                        text_size: self.size

                    # Couleur
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_color_pic2
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        ColorPreview:
                            id: color_preview_pic2
                            hex_color: root.pic2_color
                            size_hint_x: None
                            width: dp(200)
                            canvas.before:
                                Color:
                                    rgba: 0,0,0,0.85
                                Line:
                                    width: 2
                                    rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
                            on_release: root.parent_screen.open_color_picker("PIC2") if root.parent_screen else None

                        TextInput:
                            id: hex_input_pic2
                            text: root.pic2_color
                            font_size: sp(20)
                            multiline: False
                            size_hint_x: None
                            width: dp(160)
                            on_text: root.parent_screen.on_color_change("PIC2", self.text) if root.parent_screen else None
                            padding: [dp(12), dp(10)]

                    # Forme
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_shape_pic2
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Spinner:
                            id: spinner_shape_pic2
                            text: root.pic2_shape
                            values: ["all", "square", "diamond", "plus", "X", "only_center"]
                            font_size: sp(20)
                            size_hint_x: 1
                            on_text: root.parent_screen.on_shape_change("PIC2", self.text) if root.parent_screen else None

                    # Mode
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_mode_pic2
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Spinner:
                            id: spinner_mode_pic2
                            text: root.pic2_mode
                            values: ["on", "off", "blink", "fading_blink"]
                            font_size: sp(20)
                            size_hint_x: 1
                            on_text: root.parent_screen.on_mode_change("PIC2", self.text) if root.parent_screen else None

                    # Intensité
                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(20)
                        size_hint_y: None
                        height: dp(80)

                        Label:
                            id: lbl_intensity_pic2
                            text: ""
                            bold: True
                            font_size: sp(24)
                            color: 0,0,0,1
                            size_hint_x: 0.25
                            halign: "left"
                            valign: "middle"
                            text_size: self.size

                        Slider:
                            id: slider_intensity_pic2
                            min: 0
                            max: 255
                            value: root.pic2_intensity
                            step: 1
                            size_hint_x: 0.6
                            on_value: root.pic2_intensity = int(self.value)

                        Label:
                            id: lbl_intensity_value_pic2
                            text: str(int(root.pic2_intensity))
                            font_size: sp(22)
                            color: 0,0,0,1
                            size_hint_x: 0.15
                            halign: "center"
                            valign: "middle"

                    # Botón Actualizar PIC2
                    Button:
                        id: btn_update_pic2
                        text: ""
                        font_size: sp(20)
                        size_hint_y: None
                        height: dp(60)
                        background_color: 0,0,0,0
                        canvas.before:
                            Color:
                                rgba: 0.15, 0.55, 0.95, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(10),]
                        on_release: root.parent_screen.on_update_single("PIC2") if root.parent_screen else None

                Widget:
                    size_hint_y: None
                    height: dp(20)

                # ---------- BOTÓN ACTUALIZAR ----------
                Button:
                    id: btn_update
                    text: ""
                    font_size: sp(24)
                    size_hint_y: None
                    height: dp(70)
                    background_color: 0,0,0,0
                    canvas.before:
                        Color:
                            rgba: 0.15, 0.55, 0.95, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(12),]
                    on_release: root.parent_screen.on_update() if root.parent_screen else None

                Widget:
                    size_hint_y: None
                    height: dp(20)
"""

Builder.load_string(KV)

# ----------------- SCREEN PRINCIPALE -----------------

class ButtonColorsScreen(Screen):
    color_popup = ObjectProperty(None, allownone=True)
    current_editing = StringProperty("")

    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg

        self.root_view = Factory.ButtonColorsRoot()
        self.root_view.parent_screen = self
        self.add_widget(self.root_view)

        # Charger les couleurs sauvegardées
        self.load_saved_colors()

        # Mettre à jour les labels
        self.update_labels()

    def load_saved_colors(self):
        """Charge les paramètres sauvegardés depuis la configuration"""
        button_colors = self.cfg.data.get("button_colors", {})
        
        # PIC1
        pic1_data = button_colors.get("PIC1", {})
        if isinstance(pic1_data, str):
            self.root_view.pic1_color = pic1_data
            self.root_view.pic1_shape = "all"
            self.root_view.pic1_mode = "on"
            self.root_view.pic1_intensity = 255
        elif isinstance(pic1_data, dict):
            self.root_view.pic1_color = pic1_data.get("color", "#ffffff")
            self.root_view.pic1_shape = pic1_data.get("shape", "all")
            self.root_view.pic1_mode = pic1_data.get("mode", "on")
            self.root_view.pic1_intensity = pic1_data.get("intensity", 255)
        else:
            self.root_view.pic1_color = "#ffffff"
            self.root_view.pic1_shape = "all"
            self.root_view.pic1_mode = "on"
            self.root_view.pic1_intensity = 255
        
        # PIC2
        pic2_data = button_colors.get("PIC2", {})
        if isinstance(pic2_data, str):
            self.root_view.pic2_color = pic2_data
            self.root_view.pic2_shape = "all"
            self.root_view.pic2_mode = "on"
            self.root_view.pic2_intensity = 255
        elif isinstance(pic2_data, dict):
            self.root_view.pic2_color = pic2_data.get("color", "#ffffff")
            self.root_view.pic2_shape = pic2_data.get("shape", "all")
            self.root_view.pic2_mode = pic2_data.get("mode", "on")
            self.root_view.pic2_intensity = pic2_data.get("intensity", 255)
        else:
            self.root_view.pic2_color = "#ffffff"
            self.root_view.pic2_shape = "all"
            self.root_view.pic2_mode = "on"
            self.root_view.pic2_intensity = 255

    def update_labels(self):
        """Met à jour les labels avec les traductions"""
        
        if not hasattr(self.root_view, 'ids'):
            return
        
        self.root_view.ids.lbl_title.text = _("Configuración Colores Botones")
        self.root_view.ids.lbl_color_pic1.text = _("Color:")
        self.root_view.ids.lbl_color_pic2.text = _("Color:")
        self.root_view.ids.lbl_shape_pic1.text = _("Forma:")
        self.root_view.ids.lbl_shape_pic2.text = _("Forma:")
        self.root_view.ids.lbl_mode_pic1.text = _("Modo:")
        self.root_view.ids.lbl_mode_pic2.text = _("Modo:")
        self.root_view.ids.lbl_intensity_pic1.text = _("Intensidad:")
        self.root_view.ids.lbl_intensity_pic2.text = _("Intensidad:")
        self.root_view.ids.btn_update_pic1.text = _("Actualizar PIC1")
        self.root_view.ids.btn_update_pic2.text = _("Actualizar PIC2")
        self.root_view.ids.btn_update.text = _("Actualizar Todo")

    def on_color_change(self, button_id, hex_color):
        """Met à jour la couleur quand l'utilisateur tape dans le champ texte"""
        hex_str = hex_color.strip()
        if not hex_str.startswith('#'):
            hex_str = '#' + hex_str
        
        if len(hex_str) == 7:
            try:
                int(hex_str[1:], 16)
                if button_id == "PIC1":
                    self.root_view.pic1_color = hex_str
                elif button_id == "PIC2":
                    self.root_view.pic2_color = hex_str
            except ValueError:
                pass

    def open_color_picker(self, button_id):
        """Ouvre un sélecteur de couleur dans une popup"""
        self.current_editing = button_id
        
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        picker = ColorPicker()
        
        try:
            current_color = self.root_view.pic1_color if button_id == "PIC1" else self.root_view.pic2_color
            r, g, b, a = get_color_from_hex(current_color)
            picker.color = (r, g, b, a)
        except:
            picker.color = (1, 1, 1, 1)
        
        def on_color_change(instance, value):
            r, g, b, a = value
            hex_color = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
            
            if button_id == "PIC1":
                self.root_view.pic1_color = hex_color
            elif button_id == "PIC2":
                self.root_view.pic2_color = hex_color
        
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
            title=_('Seleccionar Color') + f" - {button_id}",
            content=content,
            size_hint=(0.7, 0.8),
            auto_dismiss=True
        )
        
        close_btn.bind(on_release=self.color_popup.dismiss)
        self.color_popup.open()

    def on_shape_change(self, button_id, shape):
        """Met à jour la forme quand l'utilisateur change dans le Spinner"""
        if button_id == "PIC1":
            self.root_view.pic1_shape = shape
        elif button_id == "PIC2":
            self.root_view.pic2_shape = shape

    def on_mode_change(self, button_id, mode):
        """Met à jour le mode quand l'utilisateur change dans le Spinner"""
        if button_id == "PIC1":
            self.root_view.pic1_mode = mode
        elif button_id == "PIC2":
            self.root_view.pic2_mode = mode

    def encode_shape_mode(self, shape, mode):
        """
        ✅ ENCODAGE CORRECT (8 bits):
        data[1] = (shape << 4) | mode
        """
        shape_code = SHAPES.get(shape, 0)
        mode_code = MODES.get(mode, 0)
        
        # ✅ Encoder sur 8 bits
        encoded = (shape_code << 4) | mode_code
        
        return encoded

    def hex_to_rgb(self, hex_color):
        """Convertit #RRGGBB en (R, G, B)"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def on_update_single(self, button_id):
        """✅ Actualise la configuration d'un seul bouton (PIC1 ou PIC2)"""
        if button_id == "PIC1":
            pic_bitmask = 0x01  # PIC1
            color = self.root_view.pic1_color
            shape = self.root_view.pic1_shape
            mode = self.root_view.pic1_mode
            intensity = int(self.root_view.pic1_intensity)
        else:  # PIC2
            pic_bitmask = 0x02  # PIC2
            color = self.root_view.pic2_color
            shape = self.root_view.pic2_shape
            mode = self.root_view.pic2_mode
            intensity = int(self.root_view.pic2_intensity)
        
        # Sauvegarder dans la configuration
        if "button_colors" not in self.cfg.data:
            self.cfg.data["button_colors"] = {}
        
        self.cfg.data["button_colors"][button_id] = {
            "color": color,
            "shape": shape,
            "mode": mode,
            "intensity": intensity
        }
        
        self.cfg.save()
        
        # ✅ Encoder shape_mode
        shape_mode = self.encode_shape_mode(shape, mode)
        
        # ✅ PAYLOAD MQTT CORRIGÉ (format attendu par le convertisseur)
        payload = {
            "PIC": pic_bitmask,      # ✅ Champ PIC
            "shape_mode": shape_mode, # ✅ Champ shape_mode
            "color": color,           # ✅ Champ color (#RRGGBB)
            "intensity": intensity    # ✅ Champ intensity
        }
        
        # Publier sur MQTT
        mqtt_client.publish("button/config", json.dumps(payload))
    
        # Log
        print(f"[MQTT] ========================================")
        print(f"[MQTT] Topic: button/config")
        print(f"[MQTT] {button_id} Payload:")
        print(f"[MQTT]   PIC = 0x{pic_bitmask:02X}")
        print(f"[MQTT]   shape_mode = {shape_mode} (0x{shape_mode:02X})")
        print(f"[MQTT]   color = {color}")
        print(f"[MQTT]   intensity = {intensity}")
        print(f"[MQTT] ========================================")

    def on_update(self):
        """✅ Sauvegarde les paramètres et les publie via MQTT"""
        # Sauvegarder dans la configuration
        if "button_colors" not in self.cfg.data:
            self.cfg.data["button_colors"] = {}
        
        self.cfg.data["button_colors"]["PIC1"] = {
            "color": self.root_view.pic1_color,
            "shape": self.root_view.pic1_shape,
            "mode": self.root_view.pic1_mode,
            "intensity": int(self.root_view.pic1_intensity)
        }
        
        self.cfg.data["button_colors"]["PIC2"] = {
            "color": self.root_view.pic2_color,
            "shape": self.root_view.pic2_shape,
            "mode": self.root_view.pic2_mode,
            "intensity": int(self.root_view.pic2_intensity)
        }
        
        self.cfg.save()
        
        # ✅ Encoder shape_mode pour les deux boutons
        pic1_shape_mode = self.encode_shape_mode(
            self.root_view.pic1_shape,
            self.root_view.pic1_mode
        )
        
        pic2_shape_mode = self.encode_shape_mode(
            self.root_view.pic2_shape,
            self.root_view.pic2_mode
        )
        
        # ✅ PAYLOAD MQTT CORRIGÉ pour PIC1
        payload_pic1 = {
            "PIC": 0x01,
            "shape_mode": pic1_shape_mode,
            "color": self.root_view.pic1_color,
            "intensity": int(self.root_view.pic1_intensity)
        }
        
        # ✅ PAYLOAD MQTT CORRIGÉ pour PIC2
        payload_pic2 = {
            "PIC": 0x02,
            "shape_mode": pic2_shape_mode,
            "color": self.root_view.pic2_color,
            "intensity": int(self.root_view.pic2_intensity)
        }
        
        # ✅ Publier sur button/config
        mqtt_client.publish("button/config", json.dumps(payload_pic1))
        mqtt_client.publish("button/config", json.dumps(payload_pic2))
        
        # Log détaillé
        print(f"[MQTT] ========================================")
        print(f"[MQTT] Topic: button/config")
        print(f"[MQTT] PIC1: {payload_pic1}")
        print(f"[MQTT] PIC2: {payload_pic2}")
        print(f"[MQTT] ========================================")

    def on_pre_enter(self, *args):
        """✅ Appelé avant d'afficher l'écran"""
        self.load_saved_colors()
        self.update_labels()

Factory.register("ButtonColorsScreen", cls=ButtonColorsScreen)
