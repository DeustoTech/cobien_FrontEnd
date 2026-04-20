"""Settings dashboard screen and navigation widgets.

This module defines the top-level settings page used to route users toward
specialized configuration screens.
"""

from typing import Any

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty
from kivy.metrics import dp, sp
from kivy.app import App
from translation import _, get_current_language
import os


# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    """Compact icon-only badge used for header actions."""

    icon_source = StringProperty("")

class SettingsNavButton(ButtonBehavior, BoxLayout):
    """Large card button used to navigate to one settings subsection."""

    icon_source = StringProperty("")
    text = StringProperty("")

Factory.register("IconBadge", cls=IconBadge)
Factory.register("SettingsNavButton", cls=SettingsNavButton)

# ----------------- KV LAYOUT -----------------

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set C_BORDER 0,0,0,0.85
#:set CARD_R dp(20)
#:set R_BTN dp(16)
#:set H_HEADER dp(110)
#:set GAP_Y dp(18)

# ========== BOUTON SETTINGS ==========
<SettingsNavButton>:
    padding: dp(24)
    spacing: dp(16)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(20), dp(20), dp(20), dp(20)]
        Color:
            rgba: 0, 0, 0, 0.28
        Line:
            width: 2.5
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(20))
    
    # Icône
    BoxLayout:
        size_hint_x: None
        width: dp(200)
        padding: dp(4)
        canvas.before:
            StencilPush
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(16), dp(16), dp(16), dp(16)]
            StencilUse
        canvas.after:
            StencilUnUse
            StencilPop
        Image:
            source: root.icon_source if root.icon_source else ""
            allow_stretch: True
            keep_ratio: True
            mipmap: True
    
    # Texte
    Label:
        text: root.text
        font_size: sp(36)
        color: 0, 0, 0, 1
        halign: "center"
        valign: "middle"
        text_size: self.size
        shorten: True
        shorten_from: "right"

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

<SettingsRoot@FloatLayout>:
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
                    radius: [CARD_R,]

            Label:
                id: lbl_title
                text: ""
                font_size: sp(50)
                bold: True
                color: C_BLACK
                size_hint_x: None
                width: dp(520)
                halign: "left"
                valign: "middle"
                text_size: self.size

            Widget:

            BoxLayout:
                orientation: "horizontal"
                size_hint_x: None
                width: self.minimum_width
                spacing: dp(18)
                padding: [0, 0, dp(10), 0]
                Button:
                    id: btn_reboot
                    text: "Reiniciar"
                    size_hint: None, None
                    size: dp(170), dp(80)
                    background_normal: ""
                    background_down: ""
                    background_color: 0.89, 0.57, 0.12, 1
                    color: 1, 1, 1, 1
                    bold: True
                    font_size: sp(24)
                    on_release: app.request_admin_reboot()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            size: self.size
                            pos: self.pos
                            radius: [R_BTN,]

                Widget:
                    size_hint_x: None
                    width: dp(14)

                Button:
                    id: btn_exit
                    text: "Salir"
                    size_hint: None, None
                    size: dp(140), dp(80)
                    background_normal: ""
                    background_down: ""
                    background_color: 0.85, 0.18, 0.18, 1
                    color: 1, 1, 1, 1
                    bold: True
                    font_size: sp(26)
                    on_release: app.request_admin_exit()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            size: self.size
                            pos: self.pos
                            radius: [R_BTN,]
                Widget:
                IconBadge:
                    icon_source: "data/images/back.png"
                    on_release: app.root.current = "main"

        # ---------- MAIN CONTENT ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [CARD_R,]

            BoxLayout:
                orientation: "vertical"
                size_hint: 0.96, 0.90
                spacing: dp(20)
                padding: dp(30)

                # Première ligne (3 boutons)
                BoxLayout:
                    orientation: "horizontal"
                    spacing: dp(20)
                    size_hint_y: 0.5

                    SettingsNavButton:
                        id: btn_language
                        icon_source: "data/images/language.png"
                        text: ""
                        on_release: app.root.current = "settings_language"

                    SettingsNavButton:
                        id: btn_cities
                        icon_source: "data/images/weather.png"
                        text: ""
                        on_release: app.root.current = "weather_choice"

                    SettingsNavButton:
                        id: btn_colors
                        icon_source: "data/images/color.png"
                        text: ""
                        on_release: app.root.current = "button_colors"

                # Deuxième ligne (3 boutons COMPLETS - sans Widget vide)
                BoxLayout:
                    orientation: "horizontal"
                    spacing: dp(20)
                    size_hint_y: 0.5

                    SettingsNavButton:
                        id: btn_notifications
                        icon_source: "data/images/notif.png"
                        text: ""
                        on_release: app.root.current = "settings_notifications"

                    SettingsNavButton:
                        id: btn_rfid
                        icon_source: "data/images/card.png"
                        text: ""
                        on_release: app.root.current = "settings_rfid"

                    SettingsNavButton:
                        id: btn_jokes
                        icon_source: "data/images/joke.png"
                        text: ""
                        on_release: app.root.current = "joke_category"

                BoxLayout:
                    orientation: "horizontal"
                    spacing: dp(20)
                    size_hint_y: None
                    height: dp(140)

                    SettingsNavButton:
                        id: btn_logs
                        icon_source: "data/images/logs.png"
                        text: ""
                        on_release: app.root.current = "settings_logs_menu"

                    SettingsNavButton:
                        id: btn_launcher
                        icon_source: "data/images/settings.png"
                        text: ""
                        on_release: app.root.current = "settings_launcher"
"""

class SettingsScreen(Screen):
    """Top-level settings dashboard."""

    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        """Initialize settings dashboard and load localized labels.

        Args:
            sm (Any): Root Kivy screen manager.
            cfg (Any): Shared application configuration object.
            **kwargs (Any): Extra Kivy Screen keyword arguments.

        Returns:
            None.
        """
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg

        # Charger KV une seule fois
        if not hasattr(SettingsScreen, '_kv_loaded'):
            Builder.load_string(KV)
            SettingsScreen._kv_loaded = True

        self.root_view = Factory.SettingsRoot()
        self.root_view.parent_screen = self
        self.add_widget(self.root_view)
        self.software_version = self._load_software_version()

        # Mettre à jour les labels
        self.update_labels()

    def _load_software_version(self) -> str:
        """Read software version from the local VERSION file.

        Returns:
            str: Parsed version string, or ``"unknown"`` if unavailable.
        """
        version_file = os.path.join(os.path.dirname(__file__), "..", "VERSION")
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                version = f.read().strip()
                return version or "unknown"
        except Exception:
            return "unknown"

    def update_labels(self) -> None:
        """Update all translated labels displayed by the settings dashboard.

        Returns:
            None.

        Raises:
            No exception is propagated. Missing widget ids are tolerated.
        """
        if not hasattr(self.root_view, 'ids'):
            return

        lang = get_current_language()
        
        # ✅ Traduire tous les labels
        self.root_view.ids.lbl_title.text = f"{_('Configuración')}  v{self.software_version}"
        self.root_view.ids.btn_language.text = _("Idioma")
        self.root_view.ids.btn_cities.text = _("Ciudades")
        self.root_view.ids.btn_colors.text = _("Colores Botones")
        self.root_view.ids.btn_notifications.text = _("Notificaciones")
        self.root_view.ids.btn_rfid.text = _("Tarjetas RFID")
        self.root_view.ids.btn_logs.text = _("Logs del sistema")
        self.root_view.ids.btn_launcher.text = _("Parámetros Launcher")
        self.root_view.ids.btn_reboot.text = _("Reiniciar")
        self.root_view.ids.btn_exit.text = _("Salir")
        
        # ✅ Bouton blagues selon langue
        if lang == "fr":
            self.root_view.ids.btn_jokes.text = "Catégorie de Phrases"
        else:
            self.root_view.ids.btn_jokes.text = "Categoría de Frases"
        
        print(f"[SETTINGS] ✅ Labels mis à jour ({lang})")

    def on_pre_enter(self, *args: Any) -> None:
        """Refresh labels right before the screen is displayed.

        Args:
            *args (Any): Kivy lifecycle positional arguments.

        Returns:
            None.
        """
        print("[SETTINGS] 📺 on_pre_enter() - Mise à jour traductions")
        self.update_labels()

Factory.register("SettingsScreen", cls=SettingsScreen)
