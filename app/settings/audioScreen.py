"""Audio device configuration screen for the CoBien furniture.

Provides:
- Output device selector (PulseAudio sinks) + test-beep button
- Input device selector (PulseAudio sources / sounddevice) + real-time VU meter
- Save button that persists preferences to config and applies them immediately
"""

from __future__ import annotations

import threading
from typing import Any, List, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from audio.audio_devices import (
    VUMeter,
    apply_system_audio_devices,
    find_input_device_index,
    list_input_devices,
    list_output_devices,
    pa_get_default_sink,
    pa_get_default_source,
    pa_list_sinks,
    pa_list_sources,
    play_test_beep,
)
from translation import _

# ─────────────────────────────────────────────────────────────────────────────
# KV layout
# ─────────────────────────────────────────────────────────────────────────────

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<AudioNavBack>:
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

<AudioPanelCard>:
    orientation: "vertical"
    padding: dp(28)
    spacing: dp(16)
    canvas.before:
        Color:
            rgba: 1,1,1,0.92
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(20),]
        Color:
            rgba: 0,0,0,0.18
        Line:
            width: 1.8
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(20))

<VUBar>:
    size_hint_y: None
    height: dp(44)
    canvas:
        # Background track
        Color:
            rgba: 0.88, 0.88, 0.88, 1
        RoundedRectangle:
            pos: self.x, self.y
            size: self.width, self.height
            radius: [dp(8),]
        # Level fill — green → orange → red
        Color:
            rgba: root._bar_color
        RoundedRectangle:
            pos: self.x, self.y
            size: max(dp(8), self.width * root.level), self.height
            radius: [dp(8),]

<AudioRoot@FloatLayout>:
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
        padding: [0, dp(16), 0, dp(16)]
        spacing: dp(14)

        # ── HEADER ──
        BoxLayout:
            size_hint_y: None
            height: dp(100)
            padding: dp(20), dp(10)
            spacing: dp(18)
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
                font_size: sp(46)
                bold: True
                color: 0,0,0,1
                halign: "left"
                valign: "middle"
                text_size: self.size
                size_hint_x: 1

            AudioNavBack:
                id: btn_back
                icon_source: "data/images/back.png"
                on_release: app.root.current = "settings"

        # ── TWO COLUMNS ──
        BoxLayout:
            orientation: "horizontal"
            spacing: dp(16)
            size_hint_y: 1

            # ── OUTPUT PANEL ──
            AudioPanelCard:
                id: panel_output
                size_hint_x: 0.5

                Label:
                    id: lbl_output_title
                    text: ""
                    font_size: sp(36)
                    bold: True
                    color: 0,0,0,1
                    size_hint_y: None
                    height: dp(50)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                Label:
                    id: lbl_output_hint
                    text: ""
                    font_size: sp(26)
                    color: 0.35,0.35,0.35,1
                    size_hint_y: None
                    height: dp(40)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                Spinner:
                    id: spinner_output
                    text: ""
                    values: []
                    font_size: sp(28)
                    size_hint_y: None
                    height: dp(68)
                    background_normal: ""
                    background_color: 0.95,0.95,0.95,1
                    color: 0,0,0,1

                Widget:
                    size_hint_y: 1

                BoxLayout:
                    orientation: "horizontal"
                    size_hint_y: None
                    height: dp(72)
                    spacing: dp(14)

                    Button:
                        id: btn_test_output
                        text: ""
                        font_size: sp(28)
                        bold: True
                        background_normal: ""
                        background_color: 0.15,0.55,0.9,1
                        color: 1,1,1,1
                        size_hint_x: 0.45
                        on_release: root._on_test_output()
                        canvas.before:
                            Color:
                                rgba: self.background_color
                            RoundedRectangle:
                                size: self.size
                                pos: self.pos
                                radius: [dp(14),]

                    Button:
                        id: btn_save_output
                        text: ""
                        font_size: sp(28)
                        bold: True
                        background_normal: ""
                        background_color: 0.12,0.72,0.35,1
                        color: 1,1,1,1
                        size_hint_x: 0.55
                        on_release: root._on_save_output()
                        canvas.before:
                            Color:
                                rgba: self.background_color
                            RoundedRectangle:
                                size: self.size
                                pos: self.pos
                                radius: [dp(14),]

            # ── INPUT PANEL ──
            AudioPanelCard:
                id: panel_input
                size_hint_x: 0.5

                Label:
                    id: lbl_input_title
                    text: ""
                    font_size: sp(36)
                    bold: True
                    color: 0,0,0,1
                    size_hint_y: None
                    height: dp(50)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                Label:
                    id: lbl_input_hint
                    text: ""
                    font_size: sp(26)
                    color: 0.35,0.35,0.35,1
                    size_hint_y: None
                    height: dp(40)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                Spinner:
                    id: spinner_input
                    text: ""
                    values: []
                    font_size: sp(28)
                    size_hint_y: None
                    height: dp(68)
                    background_normal: ""
                    background_color: 0.95,0.95,0.95,1
                    color: 0,0,0,1

                Label:
                    id: lbl_vu
                    text: ""
                    font_size: sp(24)
                    color: 0.35,0.35,0.35,1
                    size_hint_y: None
                    height: dp(34)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                VUBar:
                    id: vu_bar
                    level: 0
                    size_hint_y: None
                    height: dp(44)

                Widget:
                    size_hint_y: 1

                BoxLayout:
                    orientation: "horizontal"
                    size_hint_y: None
                    height: dp(72)
                    spacing: dp(14)

                    Button:
                        id: btn_test_input
                        text: ""
                        font_size: sp(28)
                        bold: True
                        background_normal: ""
                        background_color: 0.15,0.55,0.9,1
                        color: 1,1,1,1
                        size_hint_x: 0.45
                        on_release: root._on_toggle_vu()
                        canvas.before:
                            Color:
                                rgba: self.background_color
                            RoundedRectangle:
                                size: self.size
                                pos: self.pos
                                radius: [dp(14),]

                    Button:
                        id: btn_save_input
                        text: ""
                        font_size: sp(28)
                        bold: True
                        background_normal: ""
                        background_color: 0.12,0.72,0.35,1
                        color: 1,1,1,1
                        size_hint_x: 0.55
                        on_release: root._on_save_input()
                        canvas.before:
                            Color:
                                rgba: self.background_color
                            RoundedRectangle:
                                size: self.size
                                pos: self.pos
                                radius: [dp(14),]

        # ── STATUS BAR ──
        Label:
            id: lbl_status
            text: ""
            font_size: sp(26)
            color: 0.15,0.55,0.35,1
            size_hint_y: None
            height: dp(44)
            halign: "center"
            valign: "middle"
            text_size: self.size
"""


# ─────────────────────────────────────────────────────────────────────────────
# VUBar widget — animated level bar with colour gradient
# ─────────────────────────────────────────────────────────────────────────────

class VUBar(Widget):
    """Canvas-drawn VU level bar. Set ``level`` (0.0–1.0) to update."""

    from kivy.properties import NumericProperty, ListProperty
    level = NumericProperty(0.0)
    _bar_color = ListProperty([0.15, 0.75, 0.35, 1.0])

    def on_level(self, _instance: Any, value: float) -> None:
        if value < 0.5:
            g = 0.4 + 0.7 * (value / 0.5)
            self._bar_color = [0.1, min(g, 1.0), 0.2, 1.0]
        elif value < 0.8:
            t = (value - 0.5) / 0.3
            self._bar_color = [t * 0.95, 0.75 - t * 0.4, 0.05, 1.0]
        else:
            self._bar_color = [0.9, 0.15, 0.05, 1.0]


Factory.register("VUBar", cls=VUBar)


# ─────────────────────────────────────────────────────────────────────────────
# AudioNavBack widget
# ─────────────────────────────────────────────────────────────────────────────

class AudioNavBack(ButtonBehavior, BoxLayout):
    icon_source = StringProperty("")


class AudioPanelCard(BoxLayout):
    pass


Factory.register("AudioNavBack", cls=AudioNavBack)
Factory.register("AudioPanelCard", cls=AudioPanelCard)


# ─────────────────────────────────────────────────────────────────────────────
# AudioRoot — the root widget that holds all interactive logic
# ─────────────────────────────────────────────────────────────────────────────

class AudioRoot(BoxLayout):
    """Internal root widget wired up in KV as AudioRoot@FloatLayout."""

    # ── public slots called from KV ──────────────────────────────────────────

    def _on_test_output(self) -> None:
        idx = self._selected_output_index()
        self._set_status(_("Reproduciendo pitido de prueba…"))
        play_test_beep(device_index=idx)
        Clock.schedule_once(lambda dt: self._set_status(""), 2.0)

    def _on_save_output(self) -> None:
        name = self._spinner_output_name()
        app = App.get_running_app()
        if app and hasattr(app, "cfg"):
            app.cfg.set_audio_output_device(name)
        apply_system_audio_devices(output_device=name)
        self._set_status(_("Salida de audio guardada: ") + (name or _("(sistema)")))
        Clock.schedule_once(lambda dt: self._set_status(""), 3.0)

    def _on_toggle_vu(self) -> None:
        if self._vu_running:
            self._stop_vu()
        else:
            self._start_vu()

    def _on_save_input(self) -> None:
        name = self._spinner_input_name()
        app = App.get_running_app()
        if app and hasattr(app, "cfg"):
            app.cfg.set_microphone_device(name)
        apply_system_audio_devices(input_device=name)
        self._set_status(_("Micrófono guardado: ") + (name or _("(sistema)")))
        Clock.schedule_once(lambda dt: self._set_status(""), 3.0)

    # ── internal helpers ─────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        try:
            self.ids.lbl_status.text = msg
        except Exception:
            pass

    def _spinner_output_name(self) -> str:
        text = self.ids.spinner_output.text
        if text.startswith("★ "):
            text = text[2:]
        if text == _("(sistema por defecto)"):
            return ""
        return text

    def _spinner_input_name(self) -> str:
        text = self.ids.spinner_input.text
        if text.startswith("★ "):
            text = text[2:]
        if text == _("(sistema por defecto)"):
            return ""
        return text

    def _selected_output_index(self) -> Optional[int]:
        name = self._spinner_output_name()
        if not name:
            return None
        from audio.audio_devices import find_output_device_index
        return find_output_device_index(name)

    def _selected_input_index(self) -> Optional[int]:
        name = self._spinner_input_name()
        if not name:
            return None
        return find_input_device_index(name)

    # ── VU meter lifecycle ───────────────────────────────────────────────────

    def _start_vu(self) -> None:
        idx = self._selected_input_index()
        if self._vu_meter is None:
            self._vu_meter = VUMeter(device_index=idx)
        else:
            self._vu_meter.change_device(idx)
        ok = self._vu_meter.start()
        if ok:
            self._vu_running = True
            self._vu_event = Clock.schedule_interval(self._tick_vu, 0.05)
            self.ids.btn_test_input.text = _("Detener")
            self.ids.btn_test_input.background_color = (0.82, 0.18, 0.18, 1)
            self.ids.lbl_vu.text = _("Nivel de entrada:")
        else:
            self._set_status(_("No se pudo abrir el micrófono seleccionado"))
            Clock.schedule_once(lambda dt: self._set_status(""), 3.0)

    def _stop_vu(self) -> None:
        if self._vu_event:
            self._vu_event.cancel()
            self._vu_event = None
        if self._vu_meter:
            self._vu_meter.stop()
        self._vu_running = False
        try:
            self.ids.vu_bar.level = 0.0
            self.ids.btn_test_input.text = _("Probar mic")
            self.ids.btn_test_input.background_color = (0.15, 0.55, 0.9, 1)
            self.ids.lbl_vu.text = _("Pulsa 'Probar mic' para comprobar el nivel")
        except Exception:
            pass

    def _tick_vu(self, _dt: float) -> None:
        if self._vu_meter:
            level = self._vu_meter.get_level()
            try:
                self.ids.vu_bar.level = level
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# AudioScreen — the Kivy Screen
# ─────────────────────────────────────────────────────────────────────────────

class AudioScreen(Screen):
    """Full audio device configuration screen."""

    _kv_loaded = False

    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg

        if not AudioScreen._kv_loaded:
            Builder.load_string(KV)
            AudioScreen._kv_loaded = True

        self._root_view: Optional[AudioRoot] = None
        self._vu_meter: Optional[VUMeter] = None
        self._vu_event = None
        self._vu_running = False

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = Factory.AudioRoot()
        # Inject VU state into the root widget so KV can call back
        root._vu_meter = None
        root._vu_event = None
        root._vu_running = False
        self._root_view = root
        self.add_widget(root)
        self._update_labels()

    def _update_labels(self) -> None:
        if self._root_view is None:
            return
        ids = self._root_view.ids
        ids.lbl_title.text       = _("Configuración de audio")
        ids.lbl_output_title.text = _("Salida (altavoz)")
        ids.lbl_output_hint.text  = _("Selecciona el dispositivo de reproducción")
        ids.lbl_input_title.text  = _("Entrada (micrófono)")
        ids.lbl_input_hint.text   = _("Selecciona el dispositivo de grabación")
        ids.lbl_vu.text           = _("Pulsa 'Probar mic' para comprobar el nivel")
        ids.btn_test_output.text  = _("Probar")
        ids.btn_save_output.text  = _("Guardar")
        ids.btn_test_input.text   = _("Probar mic")
        ids.btn_save_input.text   = _("Guardar")
        ids.lbl_status.text       = ""

    def _populate_spinners(self) -> None:
        """Fill device spinners and select the currently saved device."""
        if self._root_view is None:
            return
        ids = self._root_view.ids
        saved_out = (self.cfg.get_audio_output_device() if self.cfg else "") or ""
        saved_in  = (self.cfg.get_microphone_device()   if self.cfg else "") or ""

        # ── Output ──
        sinks = pa_list_sinks()
        if sinks:
            out_names = [_fmt_sink(s) for s in sinks]
        else:
            # Fallback to sounddevice
            out_names = [d["name"] for d in list_output_devices()]

        default_sink = pa_get_default_sink()
        spinner_out_values = []
        spinner_out_current = _("(sistema por defecto)")

        for name in out_names:
            raw = name
            if raw == default_sink or (not raw and default_sink == ""):
                display = f"★ {raw}" if raw else _("(sistema por defecto)")
            else:
                display = raw
            spinner_out_values.append(display)
            if saved_out and (saved_out in raw or raw in saved_out):
                spinner_out_current = display

        if not spinner_out_values:
            spinner_out_values = [_("(sistema por defecto)")]
        ids.spinner_output.values = spinner_out_values
        ids.spinner_output.text   = spinner_out_current \
            if spinner_out_current in spinner_out_values \
            else spinner_out_values[0]

        # ── Input ──
        sources = pa_list_sources()
        if sources:
            in_names = [s["name"] for s in sources]
        else:
            in_names = [d["name"] for d in list_input_devices()]

        default_src = pa_get_default_source()
        spinner_in_values = []
        spinner_in_current = _("(sistema por defecto)")

        for name in in_names:
            if name == default_src:
                display = f"★ {name}"
            else:
                display = name
            spinner_in_values.append(display)
            if saved_in and (saved_in in name or name in saved_in):
                spinner_in_current = display

        if not spinner_in_values:
            spinner_in_values = [_("(sistema por defecto)")]
        ids.spinner_input.values = spinner_in_values
        ids.spinner_input.text   = spinner_in_current \
            if spinner_in_current in spinner_in_values \
            else spinner_in_values[0]

    # ── Kivy lifecycle ────────────────────────────────────────────────────────

    def on_pre_enter(self, *args: Any) -> None:
        self._update_labels()
        threading.Thread(target=self._populate_spinners_bg, daemon=True).start()

    def _populate_spinners_bg(self) -> None:
        """Enumerate devices in background, then schedule UI update."""
        # Pre-collect on background thread (pactl can be slow)
        sinks   = pa_list_sinks()
        sources = pa_list_sources()
        Clock.schedule_once(lambda dt: self._populate_spinners(), 0)

    def on_leave(self, *args: Any) -> None:
        if self._root_view:
            self._root_view._stop_vu()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_sink(sink: dict) -> str:
    """Return a human-readable sink label."""
    name = sink.get("name", "")
    desc = sink.get("description", "")
    return desc if desc and desc != name else name


Factory.register("AudioRoot", cls=AudioRoot)
Factory.register("AudioScreen", cls=AudioScreen)
