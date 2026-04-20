"""PIN entry screen used to guard access to administration screens."""

import os
from typing import Any

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, NumericProperty
from kivy.animation import Animation
from kivy.clock import Clock

from translation import _, get_current_language
from config_store import load_section, save_section


PIN_ENV_VAR = "COBIEN_SETTINGS_PIN"


class PinDisplay(BoxLayout):
    """Masked PIN visualization widget."""
    
    pin_value = StringProperty("")
    max_length = NumericProperty(4)
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(10)
        self.size_hint_y = None
        self.height = dp(80)
        self.padding = [dp(20), 0, dp(20), 0]
        
        self.dots = []
        for i in range(self.max_length):
            dot_box = BoxLayout(size_hint_x=1)
            with dot_box.canvas.before:
                Color(0.9, 0.9, 0.9, 1)
                dot_rect = RoundedRectangle(pos=dot_box.pos, size=dot_box.size, radius=[dp(12),])
                Color(0.3, 0.3, 0.3, 1)
                dot_line = Line(rounded_rectangle=(dot_box.pos[0], dot_box.pos[1], 
                                               dot_box.size[0], dot_box.size[1], dp(12)), 
                           width=2)
            
            dot_box.bind(pos=lambda x, y, r=dot_rect: setattr(r, 'pos', x.pos))
            dot_box.bind(size=lambda x, y, r=dot_rect: setattr(r, 'size', x.size))
            dot_box.bind(pos=lambda x, y, l=dot_line: self._update_line(l, x))
            dot_box.bind(size=lambda x, y, l=dot_line: self._update_line(l, x))

            with dot_box.canvas.after:
                dot_fill = Color(0, 0, 0, 0)
                dot_circle = Ellipse(pos=(0, 0), size=(0, 0))

            dot_box.bind(pos=lambda x, y, c=dot_circle: self._update_dot(c, x))
            dot_box.bind(size=lambda x, y, c=dot_circle: self._update_dot(c, x))

            self.dots.append((dot_box, dot_fill, dot_circle))
            self.add_widget(dot_box)
        
        self.bind(pin_value=self.update_display)
    
    def _update_line(self, line: Any, widget: Any) -> None:
        """Update rounded border geometry for one PIN slot."""
        line.rounded_rectangle = (widget.pos[0], widget.pos[1], 
                                  widget.size[0], widget.size[1], dp(12))

    def _update_dot(self, dot: Any, widget: Any) -> None:
        """Center and size one black PIN dot inside its slot."""
        diameter = min(widget.width, widget.height) * 0.28
        dot.size = (diameter, diameter)
        dot.pos = (
            widget.x + (widget.width - diameter) / 2,
            widget.y + (widget.height - diameter) / 2,
        )
    
    def update_display(self, *args: Any) -> None:
        """Refresh visible masked dots from current `pin_value`."""
        pin_len = len(self.pin_value)
        for i, (_box, dot_fill, _dot_circle) in enumerate(self.dots):
            if i < pin_len:
                dot_fill.rgba = (0, 0, 0, 1)
            else:
                dot_fill.rgba = (0, 0, 0, 0)
    
    def shake_animation(self) -> None:
        """Play horizontal shake animation for invalid PIN feedback."""
        anim = Animation(x=self.x + dp(10), duration=0.05) + \
               Animation(x=self.x - dp(10), duration=0.05) + \
               Animation(x=self.x + dp(10), duration=0.05) + \
               Animation(x=self.x, duration=0.05)
        anim.start(self)


class PinButton(Button):
    """Numeric keypad button with custom style."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.font_size = sp(32)
        self.bold = True
        self.color = (0.2, 0.2, 0.2, 1)
        
        with self.canvas.before:
            self.bg_color = Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12),])
            self.border_color = Color(0.7, 0.7, 0.7, 1)
            self.border_line = Line(rounded_rectangle=(self.pos[0], self.pos[1], 
                                                  self.size[0], self.size[1], dp(12)), 
                              width=2)
        
        self.bind(pos=self.update_canvas)
        self.bind(size=self.update_canvas)
        self.bind(state=self.on_state_change)
    
    def update_canvas(self, *args: Any) -> None:
        """Update button background/border geometry."""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = (self.pos[0], self.pos[1], 
                                        self.size[0], self.size[1], dp(12))
    
    def on_state_change(self, *args: Any) -> None:
        """Update button fill color according to press state."""
        if self.state == 'down':
            self.bg_color.rgba = (0.85, 0.85, 0.85, 1)
        else:
            self.bg_color.rgba = (0.95, 0.95, 0.95, 1)


class PinBackButton(Button):
    """Back button with icon for PIN header."""
    icon_source = StringProperty("")


class PinCodeScreen(Screen):
    """PIN authentication screen for protected navigation."""
    
    def __init__(self, sm: Any, cfg: Any, target_screen: str = "settings", **kwargs: Any) -> None:
        """Initialize PIN screen and build keypad UI."""
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        self.target_screen = target_screen
        
        self.correct_pin = self.load_pin()
        
        # ✅ Initialiser les widgets comme attributs de classe
        self.title_label = None
        self.message_label = None
        self.pin_display = None
        
        self.build_ui()
        
        # ✅ Planifier update_labels après initialisation
        Clock.schedule_once(lambda dt: self.update_labels(), 0.1)

    def on_pre_enter(self, *args: Any) -> None:
        """Reload the active PIN every time the screen is opened."""
        self.correct_pin = self.load_pin()
        if self.pin_display is not None:
            self.pin_display.max_length = len(self.correct_pin)
            self.pin_display.pin_value = ""
        if self.message_label is not None:
            self.message_label.text = ""
        Clock.schedule_once(lambda dt: self.update_labels(), 0)
    
    def load_pin(self) -> str:
        """Load the settings PIN from env first, then file fallback."""
        try:
            env_pin = os.getenv(PIN_ENV_VAR, "").strip()
            if env_pin:
                print(f"[PIN] Settings PIN loaded from environment variable {PIN_ENV_VAR}")
                return env_pin

            security = load_section("security", {"settings_pin": "1234"}) or {"settings_pin": "1234"}
            pin = str(security.get("settings_pin", "")).strip()
            if pin:
                print("[PIN] Settings PIN loaded from unified config")
                return pin
            
            default_pin = "1234"
            security["settings_pin"] = default_pin
            save_section("security", security)
            print(f"[PIN] Default settings PIN created: {default_pin}")
            return default_pin
            
        except Exception as e:
            print(f"[PIN] Failed to load settings PIN: {e}")
            return "1234"
    
    def update_labels(self) -> None:
        """Refresh translated labels and helper text."""
        print("[PIN] 🔄 Mise à jour labels...")
        
        if not self.title_label or not self.message_label:
            print("[PIN] ⚠️ Labels non initialisés")
            return
        
        lang = get_current_language()
        print(f"[PIN] 🌐 Langue actuelle: {lang}")
        
        # ✅ Traduire avec les clés EXACTES des .po
        # self.title_label.text = _("Código de Seguridad")
        
        # Réinitialiser message si pas d'erreur
        if "✓" not in self.message_label.text and "✗" not in self.message_label.text:
            # self.message_label.text = _("Ingrese el código PIN")
            self.message_label.color = (0.4, 0.4, 0.4, 1)
        
        print(f"[PIN] ✅ Labels mis à jour: '{self.title_label.text}'")
    
    def build_ui(self) -> None:
        """Build full PIN-entry layout and keypad controls."""
        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(20))
        
        # Header
        header = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(10))
        
        self.title_label = Label(
            text="",  # ✅ Sera rempli par update_labels()
            font_size=sp(32),
            bold=True,
            color=(0.2, 0.2, 0.2, 1),
            size_hint_x=0.8,
            halign="left",
            valign="middle"
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        
        back_btn = PinBackButton(
            icon_source="data/images/back.png",
            size_hint_x=0.2,
            size_hint_y=1
        )
        back_btn.bind(on_release=self.go_back)
        
        header.add_widget(self.title_label)
        header.add_widget(back_btn)
        
        # Message
        self.message_label = Label(
            text="",  # ✅ Sera rempli par update_labels()
            font_size=sp(20),
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None,
            height=dp(50)
        )
        
        # PIN Display
        self.pin_display = PinDisplay(max_length=len(self.correct_pin))
        
        # Spacer
        spacer = BoxLayout(size_hint_y=0.2)
        
        # Keyboard
        keyboard = GridLayout(cols=3, spacing=dp(15), size_hint_y=None, height=dp(400))
        
        for i in range(1, 10):
            btn = PinButton(text=str(i))
            btn.bind(on_release=lambda x, num=str(i): self.on_number_press(num))
            keyboard.add_widget(btn)
        
        keyboard.add_widget(BoxLayout())
        
        btn_0 = PinButton(text="0")
        btn_0.bind(on_release=lambda x: self.on_number_press("0"))
        keyboard.add_widget(btn_0)
        
        btn_del = PinButton(text="⌫")
        btn_del.bind(on_release=self.on_delete_press)
        keyboard.add_widget(btn_del)
        
        root.add_widget(header)
        root.add_widget(self.message_label)
        root.add_widget(self.pin_display)
        root.add_widget(spacer)
        root.add_widget(keyboard)
        
        self.add_widget(root)
    
    def on_number_press(self, number: str) -> None:
        """Handle numeric key press and trigger validation when complete."""
        current_pin = self.pin_display.pin_value
        
        if len(current_pin) < len(self.correct_pin):
            self.pin_display.pin_value = current_pin + number
            
            if len(self.pin_display.pin_value) == len(self.correct_pin):
                Clock.schedule_once(lambda dt: self.check_pin(), 0.3)
    
    def on_delete_press(self, *args: Any) -> None:
        """Handle delete key press."""
        current_pin = self.pin_display.pin_value
        if len(current_pin) > 0:
            self.pin_display.pin_value = current_pin[:-1]
    
    def check_pin(self) -> None:
        """Validate entered PIN against configured secret."""
        entered_pin = self.pin_display.pin_value
        
        if entered_pin == self.correct_pin:
            # ✅ Code correct
            # self.message_label.text = _("✓ Código correcto")
            self.message_label.color = (0, 0.7, 0, 1)
            Clock.schedule_once(lambda dt: self.grant_access(), 0.5)
        else:
            # ✅ Code incorrect
            # self.message_label.text = _("✗ Código incorrecto")
            self.message_label.color = (0.9, 0, 0, 1)
            self.pin_display.shake_animation()
            Clock.schedule_once(lambda dt: self.reset_pin(), 1.0)
    
    def reset_pin(self) -> None:
        """Clear entered PIN and reset info message style."""
        self.pin_display.pin_value = ""
        # self.message_label.text = _("Ingrese el código PIN")
        self.message_label.color = (0.4, 0.4, 0.4, 1)
    
    def grant_access(self) -> None:
        """Grant access and navigate to target screen."""
        print(f"[PIN] Accès autorisé - Transition vers {self.target_screen}")
        self.sm.current = self.target_screen
        self.reset_pin()
    
    def go_back(self, *args: Any) -> None:
        """Navigate back to main screen without authentication."""
        self.sm.current = "main"
    
    def on_pre_enter(self) -> None:
        """Reset state and refresh labels before screen entry."""
        print("[PIN] 📺 on_pre_enter() - Mise à jour traductions")
        self.reset_pin()
        self.update_labels()
    
    def on_enter(self) -> None:
        """Refresh labels when screen becomes visible."""
        print("[PIN] 🔄 on_enter: réinitialisation du PIN")
        self.update_labels()


# KV String pour PinBackButton
PINBACK_BUTTON_KV = """
<PinBackButton>:
    background_color: 0,0,0,0
    canvas.before:
        Color:
            rgba: 0.95, 0.95, 0.95, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12),]
        Color:
            rgba: 0,0,0,0.85
        Line:
            rounded_rectangle: (self.pos[0], self.pos[1], self.size[0], self.size[1], dp(12))
            width: 2
    Image:
        source: root.icon_source if root.icon_source else ""
        pos: root.pos
        size: root.size
        allow_stretch: True
        keep_ratio: True
"""
