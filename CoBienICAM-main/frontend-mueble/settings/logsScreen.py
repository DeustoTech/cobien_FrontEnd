import glob
import os

from kivy.app import App
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.screenmanager import Screen

from translation import _

KV_LOADED = False


class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")


Factory.register("IconBadge", cls=IconBadge)

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set CARD_R dp(20)
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
            radius: [dp(16),]
        Color:
            rgba: 0,0,0,0.85
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
    Image:
        source: root.icon_source
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(56), dp(56)

<LogsMenuRoot@FloatLayout>:
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

        BoxLayout:
            size_hint_y: None
            height: dp(110)
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
                font_size: sp(44)
                bold: True
                color: C_BLACK
                halign: "left"
                valign: "middle"
                text_size: self.size

            Widget:

            IconBadge:
                icon_source: "images/back.png"
                on_release: app.root.current = "settings"

        BoxLayout:
            orientation: "vertical"
            size_hint: 1, 1
            spacing: dp(20)
            padding: dp(30)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.88
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [CARD_R,]

            Button:
                id: btn_can
                text: ""
                font_size: sp(34)
                background_normal: ""
                background_color: (0.15, 0.55, 0.95, 1)
                color: (1,1,1,1)
                on_release: app.root.current = "settings_logs_can"

            Button:
                id: btn_bridge
                text: ""
                font_size: sp(34)
                background_normal: ""
                background_color: (0.2, 0.65, 0.3, 1)
                color: (1,1,1,1)
                on_release: app.root.current = "settings_logs_bridge"

            Button:
                id: btn_app
                text: ""
                font_size: sp(34)
                background_normal: ""
                background_color: (0.85, 0.45, 0.15, 1)
                color: (1,1,1,1)
                on_release: app.root.current = "settings_logs_app"

<LogsViewerRoot@FloatLayout>:
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if app.has_bg_image else ""

    BoxLayout:
        orientation: "vertical"
        size_hint: 0.96, 0.96
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        spacing: dp(16)

        BoxLayout:
            size_hint_y: None
            height: dp(100)
            padding: dp(18), dp(10)
            spacing: dp(12)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.88
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [dp(20),]

            Label:
                id: lbl_title
                text: ""
                font_size: sp(40)
                bold: True
                color: 0,0,0,1
                halign: "left"
                valign: "middle"
                text_size: self.size

            Label:
                id: lbl_file
                text: ""
                font_size: sp(18)
                color: 0.2,0.2,0.2,1
                halign: "right"
                valign: "middle"
                text_size: self.size

            IconBadge:
                icon_source: "images/back.png"
                on_release: app.root.current = "settings_logs_menu"

        ScrollView:
            id: log_scroll
            do_scroll_x: True
            do_scroll_y: True
            bar_width: dp(8)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.9
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [dp(20),]

            Label:
                id: lbl_log
                text: ""
                font_size: sp(19)
                color: 0,0,0,1
                size_hint_y: None
                height: self.texture_size[1] + dp(20)
                text_size: self.width - dp(24), None
                padding: dp(12), dp(12)
                halign: "left"
                valign: "top"
"""


class LogsMenuScreen(Screen):
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        global KV_LOADED
        if not KV_LOADED:
            Builder.load_string(KV)
            KV_LOADED = True
        self.root_view = Factory.LogsMenuRoot()
        self.add_widget(self.root_view)
        self.update_labels()

    def update_labels(self):
        self.root_view.ids.lbl_title.text = _("Logs del sistema")
        self.root_view.ids.btn_can.text = _("CAN Bus")
        self.root_view.ids.btn_bridge.text = _("MQTT-CAN Bridge")
        self.root_view.ids.btn_app.text = _("Aplicación")

    def on_pre_enter(self, *args):
        self.update_labels()


class LogsViewerScreen(Screen):
    def __init__(self, sm, cfg, log_prefix, title_text, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        self.log_prefix = log_prefix
        self.title_text = title_text
        self._watch_event = None
        self._current_file = ""
        self._read_pos = 0
        global KV_LOADED
        if not KV_LOADED:
            Builder.load_string(KV)
            KV_LOADED = True
        self.root_view = Factory.LogsViewerRoot()
        self.add_widget(self.root_view)

    def _resolve_log_dir(self):
        env_dir = os.getenv("COBIEN_LOG_DIR", "").strip()
        candidates = []
        if env_dir:
            candidates.append(env_dir)
        launcher_env = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "deploy", "ubuntu", "cobien-update.env")
        )
        if os.path.isfile(launcher_env):
            try:
                with open(launcher_env, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("COBIEN_LOG_DIR="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                candidates.append(val)
                            break
            except Exception:
                pass
        candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")))
        candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs")))
        for path in candidates:
            if path and os.path.isdir(path):
                return path
        return candidates[0] if candidates else ""

    def _latest_log_file(self):
        log_dir = self._resolve_log_dir()
        pattern = os.path.join(log_dir, f"{self.log_prefix}-*.log")
        files = glob.glob(pattern)
        if not files:
            return ""
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[0]

    def _load_tail(self, file_path, max_lines=250):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = "".join(lines[-max_lines:])
            self.root_view.ids.lbl_log.text = tail if tail.strip() else _("(sin datos todavía)")
            with open(file_path, "rb") as fb:
                fb.seek(0, os.SEEK_END)
                self._read_pos = fb.tell()
        except Exception as exc:
            self.root_view.ids.lbl_log.text = f"{_('Error al leer log')}: {exc}"
            self._read_pos = 0

    def _poll_log(self, *_args):
        log_dir = self._resolve_log_dir()
        file_path = self._latest_log_file()
        if not file_path:
            self.root_view.ids.lbl_file.text = _("No hay fichero de log")
            self.root_view.ids.lbl_log.text = (
                f"{_('Esperando datos de log...')}\n"
                f"dir={log_dir}\n"
                f"pattern={self.log_prefix}-*.log"
            )
            self._current_file = ""
            self._read_pos = 0
            return

        if file_path != self._current_file:
            self._current_file = file_path
            self.root_view.ids.lbl_file.text = os.path.basename(file_path)
            self._load_tail(file_path)
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._read_pos)
                new_data = f.read()
                self._read_pos = f.tell()
            if new_data:
                merged = (self.root_view.ids.lbl_log.text + new_data).splitlines()
                self.root_view.ids.lbl_log.text = "\n".join(merged[-350:])
                self.root_view.ids.log_scroll.scroll_y = 0
        except Exception as exc:
            self.root_view.ids.lbl_log.text = f"{_('Error al leer log')}: {exc}"

    def on_pre_enter(self, *args):
        self.root_view.ids.lbl_title.text = _(self.title_text)
        self.root_view.ids.lbl_file.text = ""
        self.root_view.ids.lbl_log.text = _("Cargando log...")
        self._poll_log()
        if self._watch_event is None:
            self._watch_event = Clock.schedule_interval(self._poll_log, 1.0)

    def on_leave(self, *args):
        if self._watch_event is not None:
            self._watch_event.cancel()
            self._watch_event = None
