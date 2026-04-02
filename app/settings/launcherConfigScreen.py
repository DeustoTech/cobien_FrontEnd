"""Launcher runtime-parameter settings screen.

This module provides an admin UI to edit launcher environment parameters and
trigger an immediate update/reload workflow.
"""

import os
import subprocess
import threading
from typing import Any, Dict

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


class IconBadgeLauncher(ButtonBehavior, AnchorLayout):
    """Reusable icon badge button for launcher settings header."""

    icon_source = StringProperty("")


Factory.register("IconBadgeLauncher", cls=IconBadgeLauncher)

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<IconBadgeLauncher>:
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

<LauncherConfigRoot@FloatLayout>:
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
        spacing: dp(18)

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
            Widget:
            IconBadgeLauncher:
                icon_source: "data/images/back.png"
                on_release: root.parent_screen.go_back() if root.parent_screen else None

        BoxLayout:
            orientation: "vertical"
            size_hint: 1, 1
            padding: dp(24)
            spacing: dp(12)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.88
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [dp(20),]

            GridLayout:
                cols: 2
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                row_default_height: dp(58)
                row_force_default: True

                Label:
                    text: "Workspace (ruta raíz con ambos repos)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_workspace
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Frontend repo (nombre carpeta frontend)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_frontend
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "MQTT repo (nombre carpeta bridge/CAN)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_mqtt
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Branch (rama Git para updates)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_branch
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Remote (normalmente origin)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_remote
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Device ID (identificador del mueble)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_device_id
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Videocall room (sala exacta, sensible a mayúsculas)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_room
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Location (ciudad del mueble)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_location
                    multiline: False
                    font_size: sp(18)

                Label:
                    text: "Update interval (sec, watch mode)"
                    color: 0,0,0,1
                    font_size: sp(20)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                TextInput:
                    id: input_interval
                    multiline: False
                    font_size: sp(18)

            Label:
                id: lbl_status
                text: ""
                size_hint_y: None
                height: dp(56)
                color: 0,0,0,0.75
                font_size: sp(18)

            Button:
                id: btn_save
                text: ""
                size_hint_y: None
                height: dp(62)
                background_normal: ""
                background_color: 0.18, 0.62, 0.25, 1
                color: 1,1,1,1
                font_size: sp(24)
                on_release: root.parent_screen.save_changes() if root.parent_screen else None

            Button:
                id: btn_update_reload
                text: ""
                size_hint_y: None
                height: dp(62)
                background_normal: ""
                background_color: 0.12, 0.32, 0.78, 1
                color: 1,1,1,1
                font_size: sp(22)
                on_release: root.parent_screen.run_full_update_reload() if root.parent_screen else None
"""


class LauncherConfigScreen(Screen):
    """Screen used to edit launcher/runtime parameters."""

    def __init__(self, sm: Any, cfg: Any, **kwargs: Any) -> None:
        """Initialize launcher config screen."""
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        if not hasattr(LauncherConfigScreen, "_kv_loaded"):
            Builder.load_string(KV)
            LauncherConfigScreen._kv_loaded = True
        self.root_view = Factory.LauncherConfigRoot()
        self.root_view.parent_screen = self
        self.add_widget(self.root_view)
        self._update_labels()

    def _env_path(self) -> str:
        """Return absolute path to launcher environment file."""
        env_from_var = os.getenv("COBIEN_UPDATE_ENV_FILE", "").strip()
        if env_from_var:
            return env_from_var
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "deploy", "ubuntu", "cobien-update.env")
        )

    def _read_env(self) -> Dict[str, str]:
        """Load environment key/values from launcher env file."""
        values = {}
        path = self._env_path()
        if not os.path.exists(path):
            return values
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
        return values

    def _write_env(self, data: Dict[str, str]) -> None:
        """Persist launcher environment key/values to disk."""
        path = self._env_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = [f"{k}={v}" for k, v in data.items()]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _update_labels(self) -> None:
        """Refresh translated labels for this screen."""
        self.root_view.ids.lbl_title.text = _("Parámetros de lanzamiento")
        self.root_view.ids.btn_save.text = _("Guardar parámetros")
        self.root_view.ids.btn_update_reload.text = _("Actualizar y recargar ahora")

    def go_back(self) -> None:
        """Navigate back to settings dashboard."""
        self.sm.current = "settings"

    def load_values(self) -> None:
        """Load persisted values into input widgets."""
        env = self._read_env()
        ids = self.root_view.ids
        default_workspace = os.path.join(os.path.expanduser("~"), "cobien")
        ids.input_workspace.text = env.get("COBIEN_WORKSPACE_ROOT", default_workspace)
        ids.input_frontend.text = env.get("COBIEN_FRONTEND_REPO_NAME", "cobien_FrontEnd")
        ids.input_mqtt.text = env.get("COBIEN_MQTT_REPO_NAME", "cobien_MQTT_Dictionnary")
        ids.input_branch.text = env.get("COBIEN_UPDATE_BRANCH", "development_fix")
        ids.input_remote.text = env.get("COBIEN_UPDATE_REMOTE", "origin")
        ids.input_device_id.text = env.get("COBIEN_DEVICE_ID", self.cfg.get_device_id())
        ids.input_room.text = env.get("COBIEN_VIDEOCALL_ROOM", self.cfg.get_videocall_room())
        ids.input_location.text = env.get("COBIEN_DEVICE_LOCATION", self.cfg.get_device_location())
        ids.input_interval.text = env.get("COBIEN_UPDATE_INTERVAL_SEC", "60")
        ids.lbl_status.text = f"{_('Configuración cargada desde')}: {self._env_path()}"

    def save_changes(self) -> None:
        """Save current form values to env file and runtime config."""
        ids = self.root_view.ids
        data = {
            "COBIEN_WORKSPACE_ROOT": ids.input_workspace.text.strip(),
            "COBIEN_FRONTEND_REPO_NAME": ids.input_frontend.text.strip(),
            "COBIEN_MQTT_REPO_NAME": ids.input_mqtt.text.strip(),
            "COBIEN_UPDATE_BRANCH": ids.input_branch.text.strip() or "development_fix",
            "COBIEN_UPDATE_REMOTE": ids.input_remote.text.strip() or "origin",
            "COBIEN_DEVICE_ID": ids.input_device_id.text.strip(),
            "COBIEN_VIDEOCALL_ROOM": ids.input_room.text.strip(),
            "COBIEN_DEVICE_LOCATION": ids.input_location.text.strip(),
            "COBIEN_UPDATE_INTERVAL_SEC": ids.input_interval.text.strip() or "60",
        }
        self._write_env(data)

        # sync runtime app config for immediate consistency
        self.cfg.data["device_id"] = data["COBIEN_DEVICE_ID"] or self.cfg.data.get("device_id", "CoBien1")
        self.cfg.data["videocall_room"] = data["COBIEN_VIDEOCALL_ROOM"] or self.cfg.data.get("videocall_room", "CoBien1")
        self.cfg.data["device_location"] = data["COBIEN_DEVICE_LOCATION"] or self.cfg.data.get("device_location", "Bilbao")
        self.cfg.save()

        app = App.get_running_app()
        if app and hasattr(app, "main_ref") and app.main_ref:
            app.main_ref.DEVICE_ID = self.cfg.get_device_id()
            app.main_ref.VIDEOCALL_ROOM = self.cfg.get_videocall_room()
            app.main_ref.DEVICE_LOCATION = self.cfg.get_device_location()

        ids.lbl_status.text = f"{_('Parámetros guardados en')}: {self._env_path()}"

    def _launcher_script_path(self) -> str:
        """Resolve absolute path to `cobien-launcher.sh` script."""
        ids = self.root_view.ids
        workspace = ids.input_workspace.text.strip() or os.path.join(os.path.expanduser("~"), "cobien")
        frontend_name = ids.input_frontend.text.strip() or "cobien_FrontEnd"
        return os.path.join(workspace, frontend_name, "deploy", "ubuntu", "cobien-launcher.sh")

    def run_full_update_reload(self) -> None:
        """Run full update-and-reload sequence in a background thread."""
        # Persist current values first so launcher runs with the latest config.
        self.save_changes()
        ids = self.root_view.ids

        launcher_script = self._launcher_script_path()
        if not os.path.isfile(launcher_script):
            ids.lbl_status.text = f"{_('Error')}: launcher no encontrado: {launcher_script}"
            return

        workspace = ids.input_workspace.text.strip() or os.path.join(os.path.expanduser("~"), "cobien")
        frontend_name = ids.input_frontend.text.strip() or "cobien_FrontEnd"
        mqtt_name = ids.input_mqtt.text.strip() or "cobien_MQTT_Dictionnary"
        branch = ids.input_branch.text.strip() or "development_fix"
        device_id = ids.input_device_id.text.strip() or self.cfg.get_device_id()
        room = ids.input_room.text.strip() or self.cfg.get_videocall_room()
        location = ids.input_location.text.strip() or self.cfg.get_device_location()

        # Full update + clean relaunch sequence.
        cmd = [
            "/bin/bash", launcher_script,
            "--non-interactive",
            "--yes",
            "--force-restart",
            "--run-update-once",
            "--mode", "run",
            "--workspace", workspace,
            "--frontend-name", frontend_name,
            "--mqtt-name", mqtt_name,
            "--branch", branch,
            "--device-id", device_id,
            "--videocall-room", room,
            "--device-location", location,
        ]

        ids.lbl_status.text = _("Actualizando software y relanzando servicios...")

        def _run():
            try:
                completed = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if completed.returncode == 0:
                    Clock.schedule_once(
                        lambda _dt: setattr(
                            ids.lbl_status,
                            "text",
                            _("Secuencia de actualización completada. Runtime recargado.")
                        ),
                        0,
                    )
                else:
                    stderr_tail = (completed.stderr or "").strip().splitlines()[-1:] or [""]
                    error_msg = stderr_tail[0] if stderr_tail[0] else f"return code {completed.returncode}"
                    Clock.schedule_once(
                        lambda _dt: setattr(
                            ids.lbl_status,
                            "text",
                            f"{_('Error en actualización')}: {error_msg}"
                        ),
                        0,
                    )
            except Exception as exc:
                Clock.schedule_once(
                    lambda _dt: setattr(ids.lbl_status, "text", f"{_('Error en actualización')}: {exc}"),
                    0,
                )

        threading.Thread(target=_run, daemon=True).start()

    def on_pre_enter(self, *args: Any) -> None:
        """Refresh labels/values before entering this screen."""
        self._update_labels()
        self.load_values()
