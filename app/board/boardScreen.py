"""Board screen UI and interaction logic.

This module provides the Kivy screen responsible for rendering board messages
for the current device, navigating between entries, deleting entries through
the backend, and reacting to MQTT-triggered refresh commands.
"""
from datetime import datetime
from typing import Any, Dict, List
from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from translation import _
from popup_style import wrap_popup_content, popup_theme_kwargs
from kivy.app import App

import threading
from board.loadBoard import delete_board_item, fetch_board_items_from_mongo, mark_message_read, submit_quick_reply

from app_config import AppConfig, MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

import json
import paho.mqtt.client as mqtt

# ---------- Reusable widgets ----------
class LegendDot(Widget):
    """Simple reusable color-dot widget used by board-related UI components."""

    rgba = ListProperty([0.15, 0.55, 0.95, 1.0])

class IconBadge(ButtonBehavior, AnchorLayout):
    """Clickable icon container with rounded visual style."""

    icon_source = StringProperty("")

class ImageButton(ButtonBehavior, AnchorLayout):
    """Clickable image button used for board navigation controls."""

    src = StringProperty("")


class AvatarCircle(FloatLayout):
    """Circular sender avatar that can fall back to an initial."""

    source = StringProperty("")
    initial = StringProperty("")


KV = r"""
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
            rgba: 1, 1, 1, 1
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

<ImageButton>:
    size_hint: None, None
    size: dp(72), dp(72)
    padding: dp(6)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
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
        source: root.src
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(42), dp(42)

<AvatarCircle>:
    size_hint: None, None
    size: dp(74), dp(74)
    canvas.before:
        StencilPush
        Ellipse:
            pos: self.pos
            size: self.size
        StencilUse
        Color:
            rgba: 0.95, 0.77, 0.48, 1 if not root.source else 0
        Ellipse:
            pos: self.pos
            size: self.size
    canvas.after:
        StencilUnUse
        Color:
            rgba: 0, 0, 0, 0.18
        Line:
            circle: (self.center_x, self.center_y, self.width / 2)
            width: 1.8
        StencilPop
    Image:
        source: root.source
        allow_stretch: True
        keep_ratio: False
        opacity: 1 if root.source else 0
        size: root.size
        pos: root.pos
    Label:
        text: root.initial
        font_size: sp(28)
        bold: True
        color: 0,0,0,1
        opacity: 1 if not root.source else 0
        center: root.center
        size_hint: None, None
        size: root.size
        halign: "center"
        valign: "middle"
        text_size: self.size

<BoardRoot@FloatLayout>:
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
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
                    rgba: 1, 1, 1, 0.85
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
                width: dp(390)
                halign: "left"
                valign: "middle"
                text_size: self.size

            Label:
                text: "|"
                font_size: sp(40)
                color: C_BLACK
                size_hint_x: None
                width: dp(14)
                halign: "center"
                valign: "middle"
                text_size: self.size

            BoxLayout:
                orientation: "vertical"
                size_hint_x: None
                width: dp(520)
                Label:
                    id: lbl_today
                    text: ""
                    font_size: sp(26)
                    color: C_BLACK
                    halign: "left"
                    valign: "bottom"
                    text_size: self.size
                Label:
                    id: lbl_time
                    text: ""
                    font_size: sp(18)
                    color: C_BLACK
                    halign: "left"
                    valign: "top"
                    text_size: self.size

            Widget:

            BoxLayout:
                orientation: "horizontal"
                size_hint_x: None
                width: self.minimum_width
                spacing: dp(12)
                padding: [0, 0, dp(22), 0]
                IconBadge:
                    icon_source: app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "data/images/back.png"
                    on_release: app.root.current = "main"
                IconBadge:
                    icon_source: app.mic_icon if hasattr(app, 'mic_icon') else ""
                    on_release: app.start_assistant()

        # ---------- CONTENT CARD ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            BoxLayout:
                orientation: "horizontal"
                size_hint: 0.96, 0.94
                spacing: dp(12)
                padding: [dp(12), dp(12), dp(12), dp(12)]

                # Left arrow
                AnchorLayout:
                    size_hint: None, 1
                    width: dp(90)
                    anchor_x: "center"
                    anchor_y: "center"
                    ImageButton:
                        id: btn_prev
                        src: "data/images/arrowback.png"
                        opacity: 1
                        disabled: False
                        on_release: root.parent_widget.goto_prev()

                # Inner card
                AnchorLayout:
                    size_hint_x: 1
                    anchor_x: "center"
                    anchor_y: "center"
                    BoxLayout:
                        orientation: "horizontal"
                        size_hint: 1, None
                        height: max(dp(620), self.minimum_height)
                        spacing: dp(24)
                        padding: [dp(24), dp(32), dp(24), dp(32)]
                        canvas.before:
                            Color:
                                rgba: 1, 1, 1, 1
                            RoundedRectangle:
                                size: self.size
                                pos: self.pos
                                radius: [dp(16),]

                        # Text
                        BoxLayout:
                            orientation: "vertical"
                            size_hint_x: 0.45
                            spacing: dp(12)
                            BoxLayout:
                                size_hint_y: None
                                height: dp(94)
                                spacing: dp(14)
                                AvatarCircle:
                                    id: sender_avatar
                                BoxLayout:
                                    orientation: "vertical"
                                    spacing: dp(4)
                                    Label:
                                        id: lbl_from
                                        text: "De —:"
                                        font_size: sp(32)
                                        bold: True
                                        color: C_BLACK
                                        halign: "left"
                                        valign: "middle"
                                        text_size: self.size
                                    Label:
                                        id: lbl_sent_at
                                        text: ""
                                        font_size: sp(20)
                                        color: 0, 0, 0, 0.72
                                        halign: "left"
                                        valign: "middle"
                                        text_size: self.size
                            Label:
                                id: lbl_body
                                text: ""
                                font_size: sp(28)
                                color: C_BLACK
                                halign: "left"
                                valign: "top"
                                text_size: self.size
                            BoxLayout:
                                id: quick_replies_box
                                orientation: "vertical"
                                size_hint_y: None
                                height: self.minimum_height
                                spacing: dp(10)
                            AnchorLayout:
                                anchor_x: "right"
                                anchor_y: "bottom"
                                size_hint_y: None
                                height: dp(72)
                                IconBadge:
                                    id: btn_delete
                                    size: dp(58), dp(58)
                                    icon_source: "data/images/trash.png"
                                    opacity: 0.4
                                    disabled: True
                                    on_release: root.parent_widget.confirm_delete_current()

                        # Image
                        AnchorLayout:
                            size_hint_x: 0.55
                            anchor_x: "center"
                            anchor_y: "center"
                            Image:
                                id: img_photo
                                source: ""
                                allow_stretch: True
                                keep_ratio: True
                                size_hint: 1, 1

                # Right arrow
                AnchorLayout:
                    size_hint: None, 1
                    width: dp(90)
                    anchor_x: "center"
                    anchor_y: "center"
                    ImageButton:
                        id: btn_next
                        src: "data/images/arrowforward.png"
                        opacity: 1
                        disabled: False
                        on_release: root.parent_widget.goto_next()
"""


class BoardScreen(Screen):
    """Board message viewer with navigation, delete, and MQTT refresh support.

    The screen displays the latest message first, supports left/right cycling,
    and can refresh data periodically or when commanded over MQTT.
    """
    RECIPIENT_KEY = "CoBien1"

    def __init__(self, sm: Any, **kwargs: Any) -> None:
        """Initialize the board screen and schedule periodic updates.

        Args:
            sm: Kivy `ScreenManager` instance that owns this screen.
            **kwargs: Standard Kivy `Screen` keyword arguments.

        Raises:
            No exception is intentionally raised. Runtime setup errors are logged
            by the underlying methods.

        Examples:
            >>> # screen = BoardScreen(screen_manager, name="board")
        """
        super().__init__(**kwargs)
        self.sm = sm
        Builder.load_string(KV)

        self.cfg = AppConfig()
        self.RECIPIENT_KEY = self._resolve_recipient_key()

        print(f"[BOARD] Recipient: {self.RECIPIENT_KEY}")

        # Root view
        self.root_view = Factory.BoardRoot()
        # Reference used by internal widget callbacks
        self.root_view.parent_widget = self
        self.add_widget(self.root_view)

        self.items = []
        self.idx = 0

    def _resolve_recipient_key(self) -> str:
        recipient_key = str(self.cfg.get_device_id() or "").strip()
        if recipient_key:
            return recipient_key

        app = App.get_running_app()
        runtime_device_id = (
            str(getattr(app, "DEVICE_ID", "") or "").strip()
            if app else ""
        )
        if runtime_device_id:
            print(
                f"[BOARD] Recipient fallback from runtime app: "
                f"{runtime_device_id}"
            )
            return runtime_device_id

        print(
            "[BOARD] Recipient missing in config and runtime; "
            "falling back to CoBien1"
        )
        return "CoBien1"

        # ========== MQTT listener setup ==========
        self.setup_mqtt_listener()

        Clock.schedule_once(lambda *_: self._refresh_header(), 0)
        Clock.schedule_interval(lambda *_: self._refresh_header(), 60)

        Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        Clock.schedule_interval(lambda *_: self.refresh_from_mongo(), 60 * 5)
        
        # Initial translated labels refresh
        Clock.schedule_once(lambda *_: self.update_labels(), 0.1)

    def update_labels(self) -> None:
        """Refresh all visible translatable labels in the current screen.

        Returns:
            None.
        """
        print("[BOARD] 🔄 Refreshing translated labels...")
        
        # Refresh title and dynamic labels
        self._update_title()
        
        self._refresh_header()
        self._render_current()
        
        print("[BOARD] ✅ Labels refreshed")

    def _update_title(self, *args: Any) -> None:
        """Update the board screen title in the active language.

        Args:
            *args: Optional Kivy callback arguments.

        Returns:
            None.
        """
        if not self._have_ids("lbl_title"):
            return
        self.root_view.ids.lbl_title.text = _("Pizarra")

    # ------- Helpers -------
    def _have_ids(self, *names: str) -> bool:
        """Check whether required KV `ids` are available.

        Args:
            *names: Widget id names expected in `self.root_view.ids`.

        Returns:
            `True` when all ids are present, otherwise `False`.
        """
        ids = getattr(self.root_view, "ids", None)
        return bool(ids) and all(name in ids for name in names)

    def _refresh_header(self) -> None:
        """Refresh date/time labels displayed in the board header.

        Returns:
            None.
        """
        if not self._have_ids("lbl_today", "lbl_time"):
            return
        now = datetime.now()
        meses = [
            _("enero"), _("febrero"), _("marzo"), _("abril"), _("mayo"), _("junio"),
            _("julio"), _("agosto"), _("septiembre"), _("octubre"), _("noviembre"), _("diciembre")
        ]
        dias = [
            _("lunes"), _("martes"), _("miércoles"),
            _("jueves"), _("viernes"), _("sábado"), _("domingo")
        ]
        ids = self.root_view.ids
        ids.lbl_today.text = f"{dias[now.weekday()].capitalize()}, {now.day} {_('de')} {meses[now.month-1]}, {now.year}"
        ids.lbl_time.text = now.strftime("%H:%M")

    def _render_current(self) -> None:
        """Render current board item or empty-state UI.

        Returns:
            None.
        """
        if not self._have_ids("lbl_from", "lbl_sent_at", "sender_avatar", "lbl_body", "img_photo", "btn_delete", "btn_prev", "btn_next"):
            return
        if not self.items:
            ids = self.root_view.ids
            ids.lbl_from.text = ""
            ids.lbl_from.opacity = 0
            ids.lbl_sent_at.text = ""
            ids.lbl_sent_at.opacity = 0
            ids.sender_avatar.source = ""
            ids.sender_avatar.initial = ""
            ids.lbl_body.text = _("No hay mensajes por ahora.")
            ids.img_photo.source = ""
            ids.btn_delete.disabled = True
            ids.btn_delete.opacity = 0
            ids.btn_prev.disabled = True
            ids.btn_prev.opacity = 0
            ids.btn_next.disabled = True
            ids.btn_next.opacity = 0
            return
        
        item = self.items[self.idx]
        ids = self.root_view.ids
        ids.lbl_from.text = f"{_('De')} {item.get('author','—')}:"
        ids.lbl_from.opacity = 1
        created_at_human = str(item.get("created_at_human") or "").strip()
        if not created_at_human and item.get("created_at"):
            try:
                created_dt = item["created_at"]
                created_at_human = created_dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                created_at_human = ""
        ids.lbl_sent_at.text = created_at_human
        ids.lbl_sent_at.opacity = 1 if created_at_human else 0
        ids.sender_avatar.source = item.get("author_avatar", "") or ""
        author_name = str(item.get("author", "—") or "—").strip()
        ids.sender_avatar.initial = (author_name[:1] or "?").upper()
        ids.lbl_body.text = item.get("text","")
        ids.img_photo.source = item.get("image","") or ""
        ids.btn_delete.disabled = not bool(item.get("id"))
        ids.btn_delete.opacity = 1 if item.get("id") else 0.4
        can_navigate = len(self.items) > 1
        ids.btn_prev.disabled = not can_navigate
        ids.btn_prev.opacity = 1 if can_navigate else 0
        ids.btn_next.disabled = not can_navigate
        ids.btn_next.opacity = 1 if can_navigate else 0

        self._render_quick_replies(item)

        post_id = item.get("id", "")
        if post_id and self.RECIPIENT_KEY not in (item.get("read_by") or []):
            threading.Thread(
                target=mark_message_read,
                args=(post_id, self.RECIPIENT_KEY),
                daemon=True,
            ).start()
            item.setdefault("read_by", []).append(self.RECIPIENT_KEY)
        self._update_main_screen_unread()

    def _render_quick_replies(self, item: Dict) -> None:
        try:
            ids = self.root_view.ids
        except Exception:
            return
        qr_box = ids.get("quick_replies_box")
        if qr_box is None:
            return
        qr_box.clear_widgets()

        selected = item.get("quick_reply_selected")
        if selected:
            reply_text = selected.get("text", str(selected)) if isinstance(selected, dict) else str(selected)
            lbl = Label(
                text=f"✓ {_('Ya has respondido')}: {reply_text}",
                font_size=sp(26),
                color=(0.1, 0.65, 0.3, 1),
                size_hint_y=None,
                height=sp(38),
                halign="left",
                valign="middle",
            )
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            qr_box.add_widget(lbl)
            return

        quick_replies = list(item.get("quick_replies") or [])
        if not quick_replies:
            return

        post_id = item.get("id", "")
        for reply_text in quick_replies:
            btn = Button(
                text=reply_text,
                font_size=sp(28),
                size_hint_y=None,
                height=dp(76),
                background_normal="",
                background_color=(0.93, 0.96, 1.0, 1),
                color=(0.1, 0.3, 0.8, 1),
            )
            btn.bind(on_release=lambda b, rt=reply_text, pid=post_id, it=item: self._on_quick_reply(b, pid, rt, it))
            qr_box.add_widget(btn)

    def _on_quick_reply(self, btn, post_id: str, reply_text: str, item: Dict) -> None:
        item["quick_reply_selected"] = {"text": reply_text}
        self._render_quick_replies(item)
        threading.Thread(
            target=submit_quick_reply,
            args=(post_id, self.RECIPIENT_KEY, reply_text),
            daemon=True,
        ).start()

    def _update_main_screen_unread(self) -> None:
        try:
            from kivy.app import App
            app = App.get_running_app()
            unread = sum(
                1 for it in self.items
                if it.get("id") and self.RECIPIENT_KEY not in (it.get("read_by") or [])
            )
            label = _("Pizarra")
            app.btn_pizarra_texto = f"{label} ({unread})" if unread else label
        except Exception:
            pass

    def delete_current(self) -> None:
        """Delete the currently selected message and refresh local view state.

        Returns:
            None.

        Raises:
            No exception is propagated. Errors are logged and the screen remains
            in a consistent state.
        """
        if not self.items:
            return

        item = self.items[self.idx]
        post_id = item.get("id", "")
        if not post_id:
            print("[BOARD] Current message has no id; cannot delete")
            return

        try:
            ok = delete_board_item(post_id, source="device")
            if not ok:
                print(f"[BOARD] Could not delete message {post_id}")
                return
            print(f"[BOARD] ✅ Message deleted: {post_id}")
            del self.items[self.idx]
            if self.idx >= len(self.items):
                self.idx = max(0, len(self.items) - 1)
            self._render_current()
            Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        except Exception as e:
            print(f"[BOARD] Error deleting message {post_id}: {e}")

    def confirm_delete_current(self) -> None:
        """Open a confirmation popup before deleting the current message.

        Returns:
            None.
        """
        if not self.items:
            return

        content = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(20))
        lbl = Label(
            text=_("¿Seguro que quieres eliminar este mensaje?"),
            color=(0, 0, 0, 1),
            font_size=sp(30),
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        actions = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(12))
        btn_cancel = Button(text=_("Cancelar"), font_size=sp(28))
        btn_confirm = Button(text=_("Confirmar"), font_size=sp(28))
        actions.add_widget(btn_cancel)
        actions.add_widget(btn_confirm)

        content.add_widget(lbl)
        content.add_widget(actions)

        popup = Popup(
            title=_("Confirmar borrado"),
            content=wrap_popup_content(content),
            auto_dismiss=False,
            size_hint=(0.6, 0.38),
            **popup_theme_kwargs()
        )

        btn_cancel.bind(on_release=popup.dismiss)
        btn_confirm.bind(on_release=lambda *_: (popup.dismiss(), self.delete_current()))
        popup.open()

    # ------- Arrow navigation -------
    def goto_prev(self) -> None:
        """Move selection to the previous board item (circular navigation).

        Returns:
            None.
        """
        if not self.items:
            return
        self.idx = (self.idx - 1) % len(self.items)
        self._render_current()

    def goto_next(self) -> None:
        """Move selection to the next board item (circular navigation).

        Returns:
            None.
        """
        if not self.items:
            return
        self.idx = (self.idx + 1) % len(self.items)
        self._render_current()

    # ------- Data loading -------
    def refresh_from_mongo(self) -> None:
        """Reload board items and display the latest message first.

        Despite the method name, retrieval is delegated to the resilient loader
        (`API -> MongoDB -> local cache`).

        Returns:
            None.

        Raises:
            No exception is propagated. Errors are logged.
        """
        try:
            resolved_recipient = self._resolve_recipient_key()
            if resolved_recipient != self.RECIPIENT_KEY:
                print(
                    f"[BOARD] Recipient updated: {self.RECIPIENT_KEY} "
                    f"-> {resolved_recipient}"
                )
                self.RECIPIENT_KEY = resolved_recipient
            new_items = fetch_board_items_from_mongo(recipient_key=self.RECIPIENT_KEY, limit=50)
            print(f"[BOARD] Loaded {len(new_items)} items for '{self.RECIPIENT_KEY}'")
            old_first_id = self.items[0].get("id") if self.items else None
            new_first_id = new_items[0].get("id") if new_items else None
            self.items = new_items or []
            if old_first_id != new_first_id:
                self.idx = 0
                print("[BOARD] ✅ Index reset to 0 (latest message)")
            else:
                self.idx = min(self.idx, max(0, len(self.items) - 1))
                print(f"[BOARD] Position preserved at {self.idx}")
            self._render_current()
        except Exception as e:
            print(f"[BOARD] refresh_from_mongo error: {e}")
    
    def refresh_and_show_last(self) -> None:
        """Reload board messages and force selection of index 0.

        Returns:
            None.

        Raises:
            No exception is propagated. Detailed traceback is logged on failure.
        """
        try:
            print("[BOARD] ========================================")
            print("[BOARD] 🔄 refresh_and_show_last() called")

            resolved_recipient = self._resolve_recipient_key()
            if resolved_recipient != self.RECIPIENT_KEY:
                print(
                    f"[BOARD] Recipient updated: {self.RECIPIENT_KEY} "
                    f"-> {resolved_recipient}"
                )
                self.RECIPIENT_KEY = resolved_recipient

            new_items = fetch_board_items_from_mongo(recipient_key=self.RECIPIENT_KEY, limit=50)
            print(f"[BOARD] 📥 {len(new_items)} messages loaded")

            self.items = new_items or []

            self.idx = 0
            print("[BOARD] ✅ Index = 0 (latest message)")

            if self.items:
                print("[BOARD] ✅ Displayed message:")
                print(f"[BOARD]    From: {self.items[0].get('author', '?')}")
                print(f"[BOARD]    Text: {self.items[0].get('text', '?')[:50]}...")

            print(f"[BOARD] ========================================")

            self._render_current()
        
        except Exception as e:
            print(f"[BOARD] ❌ refresh_and_show_last error: {e}")
            import traceback
            traceback.print_exc()

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        """Replace current in-memory item list and rerender the screen.

        Args:
            items: List of normalized board items.

        Returns:
            None.
        """
        self.items = items or []
        self.idx = 0
        self._render_current()

    def on_pre_enter(self, *args: Any) -> None:
        """Kivy lifecycle hook executed before the screen becomes visible.

        Args:
            *args: Optional Kivy lifecycle arguments.

        Returns:
            None.
        """
        Clock.schedule_once(lambda *_: self._refresh_header(), 0)
        self.update_labels()
        Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        
        print("[BOARD] ========================================")

    def setup_mqtt_listener(self) -> None:
        """Configure MQTT subscriptions for board refresh commands.

        Subscribed topics:
        - `app/nav` for `reload` / `reload_last` board targets.
        - `board/reload` for legacy reload command compatibility.

        Returns:
            None.

        Raises:
            No exception is propagated. Setup failures are logged.

        Examples:
            >>> # Called automatically in __init__.
            >>> # screen.setup_mqtt_listener()
        """
        try:
            def on_message(client, userdata, msg):
                if msg.topic == "board/reload":
                    print("[BOARD] 📥 Legacy reload request received via MQTT")
                    Clock.schedule_once(lambda dt: self.refresh_from_mongo(), 0)
                    return

                if msg.topic == "app/nav":
                    try:
                        payload = json.loads(msg.payload.decode("utf-8"))
                        
                        # Support reload_last
                        if payload.get("target") == "board" and payload.get("type") == "reload_last":
                            print(f"[BOARD] 📥 Reload LAST request received via MQTT")
                            Clock.schedule_once(lambda dt: self.refresh_and_show_last(), 0)
                        
                        # Legacy reload support
                        elif payload.get("target") == "board" and payload.get("type") == "reload":
                            print(f"[BOARD] 📥 Reload request received via MQTT")
                            Clock.schedule_once(lambda dt: self.refresh_from_mongo(), 0)
                    
                    except Exception as e:
                        print(f"[BOARD] MQTT error: {e}")
            
            self.mqtt_client = mqtt.Client(client_id="board_screen_client")
            self.mqtt_client.on_message = on_message
            self.mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
            self.mqtt_client.subscribe("app/nav")
            self.mqtt_client.subscribe("board/reload")
            self.mqtt_client.loop_start()
            print("[BOARD] ✅ MQTT listener activated")
        except Exception as e:
            print(f"[BOARD] ⚠️ MQTT setup error: {e}")
