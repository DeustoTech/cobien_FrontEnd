# board/boardScreen.py
from datetime import datetime
from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.factory import Factory
from kivy.metrics import dp, sp
from translation import _
from kivy.app import App

from board.loadBoard import delete_board_item, fetch_board_items_from_mongo

from app_config import AppConfig, MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

import json
import paho.mqtt.client as mqtt

# ---------- Widgets reutilizados ----------
class LegendDot(Widget):
    rgba = ListProperty([0.15, 0.55, 0.95, 1.0])

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

class ImageButton(ButtonBehavior, AnchorLayout):
    src = StringProperty("")


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

        # ---------- CABECERA ----------
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
                    icon_source: app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "images/back.png"
                    on_release: app.root.current = "main"
                IconBadge:
                    icon_source: app.mic_icon if hasattr(app, 'mic_icon') else ""
                    on_release: app.start_assistant()

        # ---------- TARJETA CONTENIDO ----------
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

                # Flecha izquierda
                AnchorLayout:
                    size_hint: None, 1
                    width: dp(90)
                    anchor_x: "center"
                    anchor_y: "center"
                    ImageButton:
                        src: "images/arrowback.png"
                        on_release: root.parent_widget.goto_prev()

                # Card interior
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

                        # Texto
                        BoxLayout:
                            orientation: "vertical"
                            size_hint_x: 0.45
                            spacing: dp(12)
                            BoxLayout:
                                size_hint_y: None
                                height: dp(58)
                                spacing: dp(10)
                                Label:
                                    id: lbl_from
                                    text: "De —:"
                                    font_size: sp(38)
                                    bold: True
                                    color: C_BLACK
                                    halign: "left"
                                    valign: "middle"
                                    text_size: self.size
                                IconBadge:
                                    id: btn_delete
                                    size: dp(58), dp(58)
                                    icon_source: "images/trash.png"
                                    opacity: 0.4
                                    disabled: True
                                    on_release: root.parent_widget.delete_current()
                            Label:
                                id: lbl_body
                                text: ""
                                font_size: sp(28)
                                color: C_BLACK
                                halign: "left"
                                valign: "top"
                                text_size: self.size

                        # Imagen
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

                # Flecha derecha
                AnchorLayout:
                    size_hint: None, 1
                    width: dp(90)
                    anchor_x: "center"
                    anchor_y: "center"
                    ImageButton:
                        src: "images/arrowforward.png"
                        on_release: root.parent_widget.goto_next()
"""


class BoardScreen(Screen):
    """Visor de mensajes (texto + imagen) con flechas; datos desde Mongo (GridFS)."""
    RECIPIENT_KEY = "CoBien1"

    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        Builder.load_string(KV)

        self.cfg = AppConfig()
        self.RECIPIENT_KEY = self.cfg.get_device_id()
        
        print(f"[BOARD] Recipient: {self.RECIPIENT_KEY}")

        # root visible
        self.root_view = Factory.BoardRoot()
        # reference so internal buttons can call this object
        self.root_view.parent_widget = self
        self.add_widget(self.root_view)

        self.items = []
        self.idx = 0

        # ========== SETUP MQTT LISTENER ==========
        self.setup_mqtt_listener()

        Clock.schedule_once(lambda *_: self._refresh_header(), 0)
        Clock.schedule_interval(lambda *_: self._refresh_header(), 60)

        Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        Clock.schedule_interval(lambda *_: self.refresh_from_mongo(), 60 * 5)
        
        # Update labels
        Clock.schedule_once(lambda *_: self.update_labels(), 0.1)

    def update_labels(self):
        """✅ Met à jour les labels traduits"""
        print("[BOARD] 🔄 Mise à jour labels...")
        
        # Mettre à jour le titre
        self._update_title()
        
        # Mettre à jour les labels de l'interface
        self._refresh_header()
        self._render_current()
        
        print("[BOARD] ✅ Labels mis à jour")

    def _update_title(self, *args):
        """Met à jour le titre"""
        if not self._have_ids("lbl_title"):
            return
        self.root_view.ids.lbl_title.text = _("Pizarra")

    # ------- Helpers -------
    def _have_ids(self, *names):
        ids = getattr(self.root_view, "ids", None)
        return bool(ids) and all(name in ids for name in names)

    def _refresh_header(self):
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

    def _render_current(self):
        if not self._have_ids("lbl_from", "lbl_body", "img_photo", "btn_delete"):
            return
        if not self.items:
            ids = self.root_view.ids
            ids.lbl_from.text = f"{_('De')} —:"
            ids.lbl_body.text = _("No hay mensajes por ahora.")
            ids.img_photo.source = ""
            ids.btn_delete.disabled = True
            ids.btn_delete.opacity = 0.4
            return
        
        item = self.items[self.idx]
        ids = self.root_view.ids
        ids.lbl_from.text = f"{_('De')} {item.get('author','—')}:"
        ids.lbl_body.text = item.get("text","")
        ids.img_photo.source = item.get("image","") or ""
        ids.btn_delete.disabled = not bool(item.get("id"))
        ids.btn_delete.opacity = 1 if item.get("id") else 0.4

    def delete_current(self):
        if not self.items:
            return

        item = self.items[self.idx]
        post_id = item.get("id", "")
        if not post_id:
            print("[BOARD] Mensaje actual sin id, no se puede borrar")
            return

        try:
            ok = delete_board_item(post_id)
            if not ok:
                print(f"[BOARD] No se pudo borrar mensaje {post_id}")
                return
            print(f"[BOARD] ✅ Mensaje borrado: {post_id}")
            del self.items[self.idx]
            if self.idx >= len(self.items):
                self.idx = max(0, len(self.items) - 1)
            self._render_current()
            Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        except Exception as e:
            print(f"[BOARD] Error borrando mensaje {post_id}: {e}")

    # ------- Navegación flechas -------
    def goto_prev(self):
        if not self.items:
            return
        self.idx = (self.idx - 1) % len(self.items)
        self._render_current()

    def goto_next(self):
        if not self.items:
            return
        self.idx = (self.idx + 1) % len(self.items)
        self._render_current()

    # ------- Carga desde Mongo -------
    def refresh_from_mongo(self):
        try:
            new_items = fetch_board_items_from_mongo(recipient_key=self.RECIPIENT_KEY, limit=50)
            print(f"[BOARD] Cargados {len(new_items)} items para '{self.RECIPIENT_KEY}'")
            self.items = new_items or []
            
            # ✅ TOUJOURS afficher le dernier message (index 0)
            self.idx = 0
            print(f"[BOARD] ✅ Index reset to 0 (dernier message)")
            
            self._render_current()
        except Exception as e:
            print(f"[BOARD] refresh_from_mongo error: {e}")
    
    def refresh_and_show_last(self):
        """
        Recharge les messages depuis MongoDB ET affiche le dernier message (le plus récent).
        Utilisé quand on clique "Ver" sur une notification.
        """
        try:
            print("[BOARD] ========================================")
            print("[BOARD] 🔄 refresh_and_show_last() appelé")
            
            # ✅ Recharger les messages
            new_items = fetch_board_items_from_mongo(recipient_key=self.RECIPIENT_KEY, limit=50)
            print(f"[BOARD] 📥 {len(new_items)} messages chargés")
            
            self.items = new_items or []
            
            # ✅ TOUJOURS aller au dernier message (index 0)
            self.idx = 0
            print(f"[BOARD] ✅ Index = 0 (dernier message)")
            
            if self.items:
                print(f"[BOARD] ✅ Message affiché:")
                print(f"[BOARD]    De: {self.items[0].get('author', '?')}")
                print(f"[BOARD]    Texte: {self.items[0].get('text', '?')[:50]}...")
            
            print(f"[BOARD] ========================================")
            
            self._render_current()
        
        except Exception as e:
            print(f"[BOARD] ❌ refresh_and_show_last error: {e}")
            import traceback
            traceback.print_exc()

    def set_items(self, items):
        self.items = items or []
        self.idx = 0
        self._render_current()

    def on_pre_enter(self, *args):
        """✅ Mise à jour des traductions avant d'entrer dans l'écran"""
        print("[BOARD] ========================================")
        print("[BOARD] 🔄 on_pre_enter appelé")
        
        # ✅ TOUJOURS remettre à 0 au début
        self.idx = 0
        print(f"[BOARD]    Index reset to 0 (dernier message)")
        
        Clock.schedule_once(lambda *_: self._refresh_header(), 0)
        self.update_labels()
        
        # ✅ TOUJOURS recharger (simplifié)
        Clock.schedule_once(lambda *_: self.refresh_from_mongo(), 0)
        print("[BOARD] ✅ Scheduled refresh")
        
        print("[BOARD] ========================================")

    def setup_mqtt_listener(self):
        """
        Configure MQTT listener to receive reload requests
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
                        
                        # SUPPORT reload_last
                        if payload.get("target") == "board" and payload.get("type") == "reload_last":
                            print(f"[BOARD] 📥 Reload LAST request received via MQTT")
                            Clock.schedule_once(lambda dt: self.refresh_and_show_last(), 0)
                        
                        # Support ancien reload
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
