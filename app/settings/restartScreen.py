"""Dedicated system restart screen protected by an alternate PIN."""

from typing import Any

from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen


KV = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<RestartOnlyScreen>:
    canvas.before:
        Color:
            rgba: 0.97, 0.98, 0.99, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "vertical"
        padding: [dp(36), dp(36), dp(36), dp(36)]

        Widget:

        BoxLayout:
            orientation: "vertical"
            size_hint: 1, None
            height: dp(280)
            spacing: dp(24)

            Label:
                text: root.title_text
                font_size: sp(42)
                bold: True
                color: 0.1, 0.1, 0.1, 1
                halign: "center"
                valign: "middle"
                text_size: self.size

            Button:
                id: reboot_btn
                text: root.button_text
                size_hint: None, None
                size: dp(320), dp(110)
                pos_hint: {"center_x": 0.5}
                background_normal: ""
                background_down: ""
                background_color: 0.89, 0.57, 0.12, 1
                color: 1, 1, 1, 1
                bold: True
                font_size: sp(34)
                on_release: root.reboot_system()
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        size: self.size
                        pos: self.pos
                        radius: [dp(20),]

            Label:
                text: root.status_text
                font_size: sp(22)
                color: 0.25, 0.25, 0.25, 1
                halign: "center"
                valign: "middle"
                text_size: self.size

        Widget:
"""


class RestartOnlyScreen(Screen):
    """Minimal reboot screen reachable with an alternate PIN."""

    title_text = StringProperty("Reinicio del equipo")
    button_text = StringProperty("Reiniciar")
    status_text = StringProperty("")

    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        if not hasattr(RestartOnlyScreen, "_kv_loaded"):
            Builder.load_string(KV)
            RestartOnlyScreen._kv_loaded = True

    def on_pre_enter(self, *args: Any) -> None:
        self.status_text = ""

    def reboot_system(self) -> None:
        app = App.get_running_app()
        if hasattr(app, "perform_system_reboot"):
            if app.perform_system_reboot():
                self.status_text = "Reiniciando equipo..."
            else:
                self.status_text = "No se ha podido reiniciar el equipo."
        else:
            self.status_text = "Función de reinicio no disponible."

    def on_touch_down(self, touch: Any) -> bool:
        reboot_btn = self.ids.get("reboot_btn")
        if reboot_btn is not None and reboot_btn.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if self.collide_point(*touch.pos):
            self.sm.current = "main"
            return True
        return super().on_touch_down(touch)
