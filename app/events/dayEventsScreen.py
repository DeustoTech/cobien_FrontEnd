"""Daily events screen with voice-assisted personal event creation.

This module renders events for a specific day/location, supports deletion of
personal events, and integrates voice input to create personal events.
"""

from datetime import datetime, timedelta, date
import os, json
import threading
from typing import Any, Optional

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import ListProperty, StringProperty, ObjectProperty, BooleanProperty
from kivy.clock import Clock
from translation import _
from kivy.app import App
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from app_config import AppConfig

# Voz
#import pyttsx3
#import pyaudio
#from vosk import Model, KaldiRecognizer
#from virtual_assistant.main_assistant import AssistantOrchestrator

from events.loadEvents import delete_event_mongo, add_personal_event_mongo

# ✅ STEP 4: Global variable for translation



# ---------- Widgets reutilizables ----------
class LegendDot(Widget):
    """Colored dot used in row legend and audience markers."""

    rgba = ListProperty([0.15, 0.55, 0.95, 1.0])


class IconBadge(ButtonBehavior, AnchorLayout):
    """Reusable rounded icon button widget."""

    icon_source = StringProperty("")


class ImageButton(ButtonBehavior, AnchorLayout):
    """Reusable image button widget for screen navigation."""

    src = StringProperty("")


class AddButton(ButtonBehavior, BoxLayout):
    """Clickable widget for the 'add personal event' action."""
    pass


class EventRow(BoxLayout):
    """Visual row for one event with optional delete action.

    Exposes an `on_trash` event so screen logic can handle deletion flow.
    """
    title = StringProperty("")
    description = StringProperty("")
    audience_color = ListProperty([0.15, 0.55, 0.95, 1])
    show_trash = BooleanProperty(False)
    event_id = StringProperty("")

    def __init__(self, **kwargs: Any) -> None:
        """Initialize event row and register custom Kivy event."""
        self.register_event_type('on_trash')
        super().__init__(**kwargs)

    def on_trash(self, *args: Any) -> None:
        """Default callback for trash action event."""
        pass


# ---------- KV (completo) ----------
KV_DAY = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set C_MUTED 0,0,0,0.62
#:set C_BORDER 0,0,0,0.85
#:set C_BLUE 0.15,0.55,0.95,1
#:set C_RED 1,0.23,0.18,1
#:set R_CARD dp(20)
#:set R_BTN dp(16)
#:set LEGEND_FONT sp(20)
#:set LEGEND_DOT dp(22)
#:set GAP_Y dp(18)
#:set H_HEADER dp(110)

<LegendDot>:
    size_hint: None, None
    size: LEGEND_DOT, LEGEND_DOT
    canvas:
        Color:
            rgba: self.rgba
        Ellipse:
            pos: self.pos
            size: self.size

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

<ImageButton>:
    size_hint: None, None
    size: dp(72), dp(72)
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
        source: root.src
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(42), dp(42)

<EventRow>:
    padding: dp(16), dp(14)
    spacing: dp(16)
    size_hint_y: None
    height: dp(100)
    canvas.before:
        Color:
            rgba: 1,1,1,1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(18),]
        Color:
            rgba: C_BORDER
        Line:
            width: 1.6
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(18))
    # Columna del punto
    BoxLayout:
        size_hint_x: None
        width: dp(84)
        padding: dp(4)
        AnchorLayout:
            anchor_x: "center"
            anchor_y: "center"
            LegendDot:
                rgba: root.audience_color
                size: dp(48), dp(48)
    # Texto (título + descripción)
    BoxLayout:
        orientation: "vertical"
        spacing: dp(4)
        Label:
            text: root.title
            font_size: sp(24)
            color: C_BLACK
            halign: "left"
            valign: "middle"
            text_size: self.size
        Label:
            text: root.description
            font_size: sp(18)
            color: C_MUTED
            halign: "left"
            valign: "middle"
            text_size: self.size
            size_hint_y: None
            height: sp(18) + dp(8)
    Widget:
    # Papelera centrada verticalmente (solo para personales)
    AnchorLayout:
        size_hint: None, 1
        width: dp(86)
        anchor_x: "center"
        anchor_y: "center"
        IconBadge:
            id: trash_btn
            size_hint: None, None
            size: dp(72), dp(72)
            icon_source: "data/images/trash.png"
            opacity: 1 if root.show_trash else 0
            disabled: not root.show_trash
            on_release: root.dispatch('on_trash')

<AddButton@ButtonBehavior+BoxLayout>:
    # Botón clicable para el bloque de añadir
    on_release: app.root.get_screen('day_events').children[0].voice_add()
    canvas.before:
        Color:
            rgba: 1,1,1,1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(16),]
        Color:
            rgba: C_BORDER
        Line:
            width: 1.6
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))

<DayRoot@FloatLayout>:
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if hasattr(app, "bg_image") and app.has_bg_image else ""

    # CONTENEDOR con separaciones simétricas arriba/entre/abajo
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
                id: lbl_calendar
                text: ""
                font_size: sp(40)
                bold: True
                color: C_BLACK
                size_hint_x: None
                width: dp(290)
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

            # Fecha/hora en vivo
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

            Label:
                text: "|"
                font_size: sp(40)
                color: C_BLACK
                size_hint_x: None
                width: dp(14)
                halign: "center"
                valign: "middle"
                text_size: self.size

            # Leyenda
            AnchorLayout:
                size_hint_x: None
                width: dp(380)
                anchor_x: "center"
                anchor_y: "center"
                BoxLayout:
                    orientation: "horizontal"
                    size_hint: 1, None
                    height: LEGEND_DOT
                    spacing: dp(18)
                    padding: [0, 0, 0, 0]
                    BoxLayout:
                        orientation: "horizontal"
                        size_hint_x: None
                        width: dp(170)
                        height: LEGEND_DOT
                        spacing: dp(10)
                        LegendDot:
                            rgba: C_BLUE
                        Label:
                            id: lbl_public
                            text: ""
                            font_size: LEGEND_FONT
                            color: C_BLACK
                            size_hint_y: None
                            height: LEGEND_DOT
                            valign: "middle"
                            halign: "left"
                            text_size: self.size
                    BoxLayout:
                        orientation: "horizontal"
                        size_hint_x: None
                        width: dp(170)
                        height: LEGEND_DOT
                        spacing: dp(10)
                        LegendDot:
                            rgba: C_RED
                        Label:
                            id: lbl_personal
                            text: ""
                            font_size: LEGEND_FONT
                            color: C_BLACK
                            size_hint_y: None
                            height: LEGEND_DOT
                            valign: "middle"
                            halign: "left"
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
                    on_release: app.root.current = "events"
                IconBadge:
                    icon_source: app.mic_icon if hasattr(app, 'mic_icon') else ""
                    on_release: app.start_assistant()

        # ---------- TARJETA: LISTA DEL DÍA con flechas igual que calendario ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            # Mismo layout que en eventsScreen: flecha izq, contenido, flecha dcha
            BoxLayout:
                orientation: "horizontal"
                size_hint: 0.96, 0.90
                spacing: dp(12)
                padding: [dp(12), 0, dp(12), 0]

                # Flecha izquierda
                AnchorLayout:
                    anchor_x: "left"
                    anchor_y: "center"
                    size_hint: None, 1
                    width: dp(84)
                    ImageButton:
                        src: "data/images/arrowback.png"
                        size_hint: None, None
                        size: dp(72), dp(72)
                        on_release: app.root.get_screen('day_events').children[0].switch_day(-1)

                # Contenido central
                AnchorLayout:
                    anchor_x: "center"
                    anchor_y: "center"
                    size_hint_x: 1
                    BoxLayout:
                        orientation: "vertical"
                        size_hint: 1, 1
                        spacing: dp(12)
                        padding: [0, dp(8), 0, dp(8)]

                        # Cabecera de la lista (fecha del día mostrado)
                        BoxLayout:
                            size_hint_y: None
                            height: dp(64)
                            padding: dp(16), 0
                            Label:
                                id: lbl_day_title
                                text: ""
                                font_size: sp(32)
                                bold: True
                                color: C_BLACK
                                halign: "center"
                                valign: "middle"
                                text_size: self.size

                        # Botón Añadir — por voz
                        BoxLayout:
                            size_hint_y: None
                            height: dp(90)
                            padding: dp(24), 0
                            AnchorLayout:
                                anchor_x: "left"
                                anchor_y: "center"
                                AddButton:
                                    size_hint: None, None
                                    size: dp(420), dp(70)
                                    padding: dp(10), 0
                                    spacing: dp(10)
                                    AnchorLayout:
                                        size_hint: None, 1
                                        width: dp(54)
                                        anchor_x: "center"
                                        anchor_y: "center"
                                        Image:
                                            source: "data/images/plus.png"
                                            size_hint: None, None
                                            size: dp(46), dp(46)
                                    Label:
                                        id: lbl_add_event
                                        text: ""
                                        font_size: sp(22)
                                        color: C_BLACK
                                        halign: "left"
                                        valign: "middle"
                                        text_size: self.size

                        # Liste avec Scroll
                        ScrollView:
                            bar_width: dp(6)
                            do_scroll_x: False
                            BoxLayout:
                                id: list_box
                                orientation: "vertical"
                                size_hint_y: None
                                height: self.minimum_height
                                spacing: dp(12)
                                padding: dp(16), dp(12)

                # Flecha derecha
                AnchorLayout:
                    anchor_x: "right"
                    anchor_y: "center"
                    size_hint: None, 1
                    width: dp(84)
                    ImageButton:
                        src: "data/images/arrowforward.png"
                        size_hint: None, None
                        size: dp(72), dp(72)
                        on_release: app.root.get_screen('day_events').children[0].switch_day(1)
"""


# ---------- Pantalla ----------
class DayEventsScreen(Screen):
    """Daily event detail screen with CRUD and voice-assistant hooks.

    Examples:
        >>> # day_screen.show_day(date.today(), "Bilbao")
        >>> # day_screen.voice_add()
    """

    store = ObjectProperty(allownone=True)
    current_location = StringProperty("")
    current_day = ObjectProperty(allownone=True)

    VOSK_MODEL_DIR_CANDIDATES = [
        os.path.join(os.path.dirname(__file__), "..", "virtual_assistant/vosk_models/vosk-model-small-es-0.42"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize day-events screen, labels, and periodic header refresh.

        Args:
            **kwargs: Standard Kivy `Screen` keyword arguments.
        """
        super().__init__(**kwargs)
        self.cfg = AppConfig()
        self.current_location = self.cfg.get_device_location()
        Builder.load_string(KV_DAY)
        self.root_view = Factory.DayRoot()
        self.add_widget(self.root_view)
        Clock.schedule_interval(lambda *_: self._refresh_header_clock(), 60)

        # Voz
        #self.tts = pyttsx3.init()
        #self.tts.setProperty("rate", 155)
        #self.tts.setProperty("volume", 0.9)
        #self._vosk_model = self._load_vosk_model()


        
        if hasattr(self.root_view, 'ids'):
            ids = self.root_view.ids
            if 'lbl_calendar' in ids:
                ids.lbl_calendar.text = _("Calendario")
            if 'lbl_public' in ids:
                ids.lbl_public.text = _("Público")
            if 'lbl_personal' in ids:
                ids.lbl_personal.text = _("Personal")
            if 'lbl_add_event' in ids:
                ids.lbl_add_event.text = _("Añadir evento personal (voz)")
        
        # Rafraîchir aussi les autres labels dynamiques
        self._refresh_header_clock()
        self._refresh_day_title()

    def update_labels(self) -> None:
        """Refresh all translatable labels rendered by this screen."""
        # Mettre à jour le titre si disponible
        if hasattr(self, 'root_view') and hasattr(self.root_view, 'ids'):
            ids = self.root_view.ids
            
            # Mettre à jour les labels principaux
            if 'lbl_calendar' in ids:
                ids.lbl_calendar.text = _("Calendario")
            
            if 'lbl_public' in ids:
                ids.lbl_public.text = _("Público")
            
            if 'lbl_personal' in ids:
                ids.lbl_personal.text = _("Personal")
            
            if 'lbl_add_event' in ids:
                ids.lbl_add_event.text = _("Añadir evento personal (voz)")
        
        # Rafraîchir l'affichage
        if hasattr(self, '_refresh_header_clock'):
            self._refresh_header_clock()
        
        if hasattr(self, '_refresh_day_title'):
            self._refresh_day_title()
        
        print("[DAY_EVENTS] Labels mis à jour")

    # ---------- API ----------
    def set_store(self, store: Any) -> None:
        """Inject shared event store instance.

        Args:
            store: Store-like object exposing `events_on` and optional `reload`.
        """
        self.store = store

    def show_day(self, day: date, location: str = "Bilbao") -> None:
        """Display one day/location context and rebuild list.

        Args:
            day: Target day.
            location: Location used for event filtering.
        """
        self.current_day = day
        self.current_location = location
        self._refresh_header_clock()
        self._refresh_day_title()
        self._build_list()

    def switch_day(self, delta: int) -> None:
        """Move current day by delta and refresh list.

        Args:
            delta: Number of days to move (e.g. `-1`, `+1`).
        """
        if not self.current_day:
            return
        self.current_day += timedelta(days=delta)
        self.current_location = self.cfg.get_device_location()
        self._refresh_day_title()
        self._build_list()

    # ---------- Voice-based add flow ----------
    def voice_add(self) -> None:
        """Start asynchronous voice-driven personal event creation flow.

        Returns:
            None.
        """
        if not self.current_day:
            return

        threading.Thread(
            target=self._voice_add_worker,
            daemon=True
        ).start()


    def _voice_add_worker(self) -> None:
        """Run voice flow in background thread and schedule UI updates on main loop.

        Returns:
            None.
        """
        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("Preparando asistente de voz…")))

        title_prompt = _("Di el título del evento personal")
        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, title_prompt))
        title_voice = self.listen(title_prompt)

        if not title_voice or not title_voice.strip():
            Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("No he entendido el título.")))
            Clock.schedule_once(lambda dt: self.speak(_("No he entendido el título.")))
            Clock.schedule_once(lambda dt: self._set_voice_flow_popup(False, ""))
            return

        title = title_voice.strip()
        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("Título detectado:") + f"\n{title}"))

        desc_prompt = _("Di la descripción del evento")
        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, desc_prompt))
        desc_voice = self.listen(desc_prompt)
        desc = (desc_voice or "").strip() or _("Sin descripción")
        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("Descripción detectada:") + f"\n{desc}"))

        ok = add_personal_event_mongo(
            day_date=self.current_day,
            title=title,
            description=desc,
            location=self.current_location,
            device_name=self.cfg.get_device_id()
        )

        if ok:
            Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("Guardando evento…")))
            Clock.schedule_once(lambda dt: self._after_event_added())
        else:
            Clock.schedule_once(lambda dt: self._set_voice_flow_popup(True, _("Ha ocurrido un error al añadir el evento.")))
            Clock.schedule_once(lambda dt: self.speak(_("Ha ocurrido un error al añadir el evento.")))

        Clock.schedule_once(lambda dt: self._set_voice_flow_popup(False, ""), 1.0)

    def _set_voice_flow_popup(self, active: bool, message: str) -> None:
        """Show/hide/update voice flow status popup.

        Args:
            active: Whether popup should be visible.
            message: Status message displayed in popup body.
        """
        if active:
            if not hasattr(self, "_voice_flow_popup") or self._voice_flow_popup is None:
                card = BoxLayout(
                    orientation="vertical",
                    size_hint=(None, None),
                    size=(dp(980), dp(500)),
                    pos_hint={"center_x": 0.5, "center_y": 0.5},
                    spacing=dp(16),
                    padding=dp(24),
                )
                with card.canvas.before:
                    Color(1, 1, 1, 0.98)
                    self._voice_flow_card_bg = RoundedRectangle(
                        pos=card.pos,
                        size=card.size,
                        radius=[dp(24)],
                    )
                card.bind(pos=self._sync_voice_flow_card_bg, size=self._sync_voice_flow_card_bg)

                title_label = Label(
                    text=_("Asistente de voz activo"),
                    color=(0, 0, 0, 1),
                    font_size=sp(28),
                    bold=True,
                    halign="center",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(50),
                )
                title_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

                self._voice_flow_label = Label(
                    text="",
                    color=(0, 0, 0, 1),
                    font_size=sp(24),
                    halign="center",
                    valign="middle",
                )
                self._voice_flow_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

                card.add_widget(title_label)
                card.add_widget(self._voice_flow_label)

                self._voice_flow_popup = ModalView(
                    auto_dismiss=False,
                    size_hint=(1, 1),
                    background="",
                    background_color=(0, 0, 0, 0.55),
                )
                self._voice_flow_popup.add_widget(card)

            self._voice_flow_label.text = message or ""
            if not self._voice_flow_popup.parent:
                self._voice_flow_popup.open()
            return

        if hasattr(self, "_voice_flow_popup") and self._voice_flow_popup and self._voice_flow_popup.parent:
            self._voice_flow_popup.dismiss()

    def _sync_voice_flow_card_bg(self, widget: Any, *_args: Any) -> None:
        """Synchronize popup card background geometry with widget geometry."""
        if hasattr(self, "_voice_flow_card_bg") and self._voice_flow_card_bg is not None:
            self._voice_flow_card_bg.pos = widget.pos
            self._voice_flow_card_bg.size = widget.size
    
    def _after_event_added(self) -> None:
        """Finalize successful event creation: speak, reload, rebuild, notify."""
        self.speak(_("Evento añadido."))

        if hasattr(self.store, "reload"):
            self.store.reload()

        self._build_list()
        self._notify_refresh()



    # ---------- Eliminar ----------
    def _confirm_delete_event(self, event_id: str) -> None:
        """Open delete confirmation popup for a personal event.

        Args:
            event_id: Event identifier to delete if confirmed.
        """
        if not event_id:
            return

        popup = ModalView(
            size_hint=(None, None),
            size=(dp(980), dp(520)),
            auto_dismiss=False,
            background="",
            background_color=(0, 0, 0, 0.7),
        )

        content = BoxLayout(orientation="vertical", spacing=dp(24), padding=dp(40))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(24)])
            Color(0, 0, 0, 0.2)
            border = Line(
                rounded_rectangle=(content.x, content.y, content.width, content.height, dp(24)),
                width=3,
            )

        def _sync_bg(*_args):
            bg.pos = content.pos
            bg.size = content.size
            border.rounded_rectangle = (content.x, content.y, content.width, content.height, dp(24))

        content.bind(pos=_sync_bg, size=_sync_bg)

        title = Label(
            text=_("Confirmar borrado"),
            color=(0, 0, 0, 1),
            font_size=sp(42),
            bold=True,
            size_hint_y=None,
            height=dp(60),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        lbl = Label(
            text=_("¿Seguro que quieres eliminar este evento?"),
            color=(0.2, 0.2, 0.2, 1),
            font_size=sp(30),
            size_hint_y=None,
            height=dp(90),
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        buttons = BoxLayout(size_hint_y=None, height=dp(75), spacing=dp(20))
        btn_cancel = Button(
            text=_("Cancelar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            font_size=sp(30),
            bold=True,
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
        )
        btn_confirm = Button(
            text=_("Confirmar"),
            size_hint=(None, None),
            size=(dp(220), dp(75)),
            font_size=sp(30),
            bold=True,
            background_normal="",
            background_color=(0.15, 0.55, 0.95, 1),
            color=(1, 1, 1, 1),
        )
        buttons.add_widget(BoxLayout())
        buttons.add_widget(btn_cancel)
        buttons.add_widget(btn_confirm)
        buttons.add_widget(BoxLayout())

        content.add_widget(BoxLayout(size_hint_y=0.15))
        content.add_widget(title)
        content.add_widget(lbl)
        content.add_widget(BoxLayout(size_hint_y=0.2))
        content.add_widget(buttons)

        popup.add_widget(content)

        btn_cancel.bind(on_release=popup.dismiss)
        btn_confirm.bind(on_release=lambda *_: (popup.dismiss(), self._delete_event(event_id)))
        popup.open()

    def _delete_event(self, event_id: str) -> None:
        """Delete event, refresh lists, and emit synchronization hooks.

        Args:
            event_id: Event identifier.

        Returns:
            None.
        """
        if not event_id:
            return
        ok = delete_event_mongo(event_id)
        if ok:
            if hasattr(self.store, "reload"):
                self.store.reload()
            self._build_list()
            self.speak(_("Evento eliminado."))
            self._notify_refresh()
        else:
            self.speak(_("No he podido eliminar el evento."))

    # ---------- Sincronización ----------
    def _notify_refresh(self) -> None:
        """Notify related screens (`events`, `main`) to refresh event summaries."""
        try:
            sm = self.manager
            if not sm:
                return
            if sm.has_screen("events"):
                ev_screen = sm.get_screen("events").children[0]
                if hasattr(ev_screen, "refresh_calendar"):
                    ev_screen.refresh_calendar()
            if sm.has_screen("main"):
                main_screen = sm.get_screen("main").children[0]
                if hasattr(main_screen, "refresh_events"):
                    main_screen.refresh_events()
        except Exception as e:
            print(f"[SYNC] {_('Error al refrescar pantallas')}: {e}")

    # ---------- UI ----------
    def _refresh_header_clock(self) -> None:
        """Refresh top header date/time labels using translated month/day names."""
        now = datetime.now()
        
        # ✅ FIX : Définir correctement les listes de mois et jours
        meses = [
            _("enero"), _("febrero"), _("marzo"), _("abril"), _("mayo"), _("junio"),
            _("julio"), _("agosto"), _("septiembre"), _("octubre"), _("noviembre"), _("diciembre")
        ]
        
        dias = [
            _("lunes"), _("martes"), _("miércoles"),
            _("jueves"), _("viernes"), _("sábado"), _("domingo")
        ]
        
        if not hasattr(self.root_view, 'ids'):
            return
            
        ids = self.root_view.ids
        if 'lbl_today' in ids:
            ids.lbl_today.text = f"{dias[now.weekday()].capitalize()}, {now.day} {_('de')} {meses[now.month-1]}, {now.year}"
        if 'lbl_time' in ids:
            ids.lbl_time.text = now.strftime("%H:%M")

    def _refresh_day_title(self) -> None:
        """Refresh selected day title label."""
        d = self.current_day
        if not d:
            if hasattr(self.root_view, 'ids') and 'lbl_day_title' in self.root_view.ids:
                self.root_view.ids.lbl_day_title.text = ""
            return
        
        # ✅ FIX : Définir correctement les listes de mois et jours
        meses = [
            _("enero"), _("febrero"), _("marzo"), _("abril"), _("mayo"), _("junio"),
            _("julio"), _("agosto"), _("septiembre"), _("octubre"), _("noviembre"), _("diciembre")
        ]
        
        dias = [
            _("lunes"), _("martes"), _("miércoles"),
            _("jueves"), _("viernes"), _("sábado"), _("domingo")
        ]
        
        if hasattr(self.root_view, 'ids') and 'lbl_day_title' in self.root_view.ids:
            self.root_view.ids.lbl_day_title.text = f"{dias[d.weekday()].capitalize()}, {d.day} {_('de')} {meses[d.month-1]} {_('de')} {d.year}"

    def _build_list(self) -> None:
        """Build day event rows in UI with audience ordering and color coding."""
        if not hasattr(self.root_view, 'ids') or 'list_box' not in self.root_view.ids:
            return
            
        box = self.root_view.ids.list_box
        box.clear_widgets()
        if not self.store or not self.current_day:
            return
        events = sorted(self.store.events_on(self.current_day, self.current_location),
                        key=lambda e: 0 if (e.get("audience") or "") == "all" else 1)
        for e in events:
            aud = e.get("audience", "")
            color = [0.15,0.55,0.95,1] if aud == "all" else [1,0.23,0.18,1]
            row = EventRow(
                title=e.get("title", _("Sin título")),
                description=e.get("description", _("Sin descripción")),
                audience_color=color,
                show_trash=(aud=="device"),
                event_id=str(e.get("id") or "")
            )
            row.bind(on_trash=lambda inst,_id=row.event_id:self._confirm_delete_event(_id))
            box.add_widget(row)

    # ---------- Voz ----------
    """
    def _speak(self, text:str):
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception as e:
            print(f"[TTS] {_('Error')}: {e}")

    def _load_vosk_model(self):
        for cand in self.VOSK_MODEL_DIR_CANDIDATES:
            path=os.path.abspath(cand)
            if os.path.isdir(path):
                try:
                    return Model(path)
                except Exception as e:
                    print(f"[VOSK] {_('Error cargando modelo')} {path}: {e}")
        print(f"[VOSK] {_('Modelo no encontrado.')}")
        return None
    """

    # Call to speak of the mainApp which is a relais to the speak of the vocal assistant

    def speak(self, text: str) -> None:
        """Delegate text-to-speech output to running application.

        Args:
            text: Sentence to pronounce.
        """
        app = App.get_running_app()
        if app:
            app.speak(text)

    def listen(self, prompt: str) -> Optional[str]:
        """Delegate speech recognition prompt to assistant orchestrator.

        Args:
            prompt: Prompt spoken/displayed before recognition.

        Returns:
            Optional[str]: Recognized text or `None`.

        Raises:
            No exception is propagated. Assistant initialization errors are
            logged and `None` is returned.
        """
        app = App.get_running_app()
        if not app:
            return None

        # Si l'assistant n'existe pas encore, on le crée "on demand"
        if not hasattr(app, "assistant") or app.assistant is None:
            try:
                from virtual_assistant.main_assistant import AssistantOrchestrator

                # On essaye d'utiliser le MainScreen comme référence (souvent celui qui a on_nav, etc.)
                main_ref = None
                try:
                    if app.root and app.root.has_screen("main"):
                        main_ref = app.root.get_screen("main").children[0]
                except Exception:
                    main_ref = None

                # Fallback: utiliser app si on ne trouve pas le MainScreen
                app.assistant = AssistantOrchestrator(main_ref or app)

            except Exception as e:
                print(f"[ASR] Impossible d'initialiser l'assistant: {e}")
                return None

        return app.assistant.listen(prompt)

    """
    def listen(self, prompt: str) -> str | None:
        app = App.get_running_app()
        if hasattr(app, "assistant"):
            return app.assistant.listen(prompt)
        return None
    """

    """
    def _listen_spanish(self, prompt:str, seconds:int=6)->str|None:
        self.speak(prompt)
        if not self._vosk_model:
            return None
        try:
            import time
            pa=pyaudio.PyAudio()
            stream=pa.open(format=pyaudio.paInt16,channels=1,rate=16000,input=True,frames_per_buffer=4096)
            stream.start_stream()
            rec=KaldiRecognizer(self._vosk_model,16000)
            rec.SetWords(False)
            result=[]
            end=time.time()+seconds
            while time.time()<end:
                data=stream.read(4096,exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    js=json.loads(rec.Result())
                    t=(js.get("text") or "").strip()
                    if t: result.append(t)
            js=json.loads(rec.FinalResult())
            t=(js.get("text") or "").strip()
            if t: result.append(t)
            stream.stop_stream(); stream.close(); pa.terminate()
            return " ".join(result).strip().lower() or None
        except Exception as e:
            print(f"[ASR] {_('Error escucha')}: {e}")
            return None
    """
    def on_pre_enter(self, *args: Any) -> None:
        """Kivy lifecycle hook executed before displaying daily events screen."""
        self.current_location = self.cfg.get_device_location()
        self.update_labels()
