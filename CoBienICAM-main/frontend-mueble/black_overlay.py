from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
import os
import subprocess


def suspend_system() -> bool:
    if os.getenv("COBIEN_DISABLE_SYSTEM_SLEEP", "0") in ("1", "true", "True"):
        return False

    commands = [
        ["systemctl", "suspend"],
        ["loginctl", "suspend"],
        ["dbus-send", "--system", "--print-reply", "--dest=org.freedesktop.login1",
         "/org/freedesktop/login1", "org.freedesktop.login1.Manager.Suspend", "boolean:true"],
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, check=True, timeout=8)
            print(f"[SLEEP] ✅ Suspend command executed: {' '.join(cmd[:2])}")
            return True
        except Exception as exc:
            print(f"[SLEEP] Command failed ({' '.join(cmd[:2])}): {exc}")
    return False


class BlackOverlay(ModalView):
    def __init__(self, on_wakeup=None, **kwargs):
        super().__init__(
            auto_dismiss=False,
            background="",
            **kwargs
        )
        self.size_hint = (1, 1)
        self.on_wakeup = on_wakeup

        with self.canvas:
            Color(0, 0, 0, 1)
            self._rect = Rectangle(pos=self.pos, size=self.size)

        # 🔧 CORRECTION ICI
        self.bind(pos=self.sync_rect, size=self.sync_rect)

    def sync_rect(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def on_touch_down(self, touch):
        # premier input = wakeup, clic consommé
        if self.collide_point(*touch.pos):
            self.dismiss()
            if callable(self.on_wakeup):
                Clock.schedule_once(lambda dt: self.on_wakeup(), 0)
            return True
        return super().on_touch_down(touch)
