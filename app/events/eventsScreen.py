"""Monthly calendar screen for device events.

This module renders the monthly events view, builds day cells with audience
markers, and routes day selection to `DayEventsScreen`.
"""

from datetime import datetime, date, timedelta
import calendar
from collections import defaultdict
from typing import Any, Dict, List

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.app import App

from icso_data.navigation_logger import log_navigation

from translation import _

from events.loadEvents import fetch_events_from_mongo, cargar_eventos_locales
from events.event_bus import event_bus

from app_config import AppConfig, MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT

import paho.mqtt.client as mqtt
import threading
import json

# ---------- Widgets ----------
class LegendDot(Widget):
    """Colored dot used in legend and day cells."""

    rgba = ListProperty([0.15, 0.55, 0.95, 1.0])


class IconBadge(ButtonBehavior, AnchorLayout):
    """Reusable rounded icon button widget."""

    icon_source = StringProperty("")


class ImageButton(ButtonBehavior, AnchorLayout):
    """Reusable image button widget for left/right navigation."""

    src = StringProperty("")


# ---------- Datos ----------
class EventStore:
    """In-memory normalized event store optimized for calendar access.

    Events are indexed by `(date, normalized_location)` to support fast daily
    queries for the currently selected location.

    Examples:
        >>> store = EventStore()
        >>> today_items = store.events_on(date.today(), "Bilbao")
    """

    def __init__(self) -> None:
        """Initialize from local cache only; call reload() for a full Mongo sync."""
        raw = cargar_eventos_locales() or []
        self.events = self._normalize(raw)
        self.index = self._build_index(self.events)

    def reload(self, device_name: str = "", location_name: str = "") -> None:
        """Reload events from primary/fallback sources and rebuild the index.

        Returns:
            None.

        Raises:
            No exception is propagated. Data source failures fall back to local
            cache via loader functions.
        """
        try:
            raw = fetch_events_from_mongo(device_name=device_name or None, location_name=location_name or None) or []
            if not raw:
                raise RuntimeError("Mongo vacío")
        except Exception:
            raw = cargar_eventos_locales(location_name or None) or []
        self.events = self._normalize(raw)
        self.index = self._build_index(self.events)

    @staticmethod
    def _normalize(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize raw events to store schema.

        Args:
            raw: Raw event dictionaries from loader.

        Returns:
            List[Dict[str, Any]]: Filtered and normalized events.
        """
        out = []
        for e in raw:
            raw_date = e.get("date") or e.get("fecha_inicio") or e.get("fecha")
            d = None
            if isinstance(raw_date, datetime):
                d = raw_date.date()
            else:
                d_str = str(raw_date or "").strip().replace("T", " ")
                for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
                    try:
                        d = datetime.strptime(d_str, fmt).date()
                        break
                    except Exception:
                        pass
                if d is None:
                    try:
                        d = datetime.fromisoformat(d_str).date()
                    except Exception:
                        d = None
            if d is None:
                continue
            loc = (e.get("location") or "Desconocido").strip()
            _id = str(e.get("id") or "")
            out.append({**e, "id": _id, "date": d, "location": loc, "_loc_key": loc.casefold()})
        return out

    @staticmethod
    def _build_index(events: List[Dict[str, Any]]) -> Dict[Any, List[Dict[str, Any]]]:
        """Build index by `(date, normalized_location)` key.

        Args:
            events: Normalized events list.

        Returns:
            Dict[Any, List[Dict[str, Any]]]: Indexed mapping for fast lookup.
        """
        idx = defaultdict(list)
        for e in events:
            idx[(e["date"], e["_loc_key"])].append(e)
        return idx

    def events_on(self, day: date, location_text: str) -> List[Dict[str, Any]]:
        """Return events for one day and location.

        Args:
            day: Target date.
            location_text: User/location label.

        Returns:
            List[Dict[str, Any]]: Matching events.
        """
        return self.index.get((day, location_text.strip().casefold()), [])

    def get_upcoming(self, n: int = 2) -> List[Dict[str, Any]]:
        """Return the next `n` upcoming events from today.

        Args:
            n: Maximum number of upcoming events to return.

        Returns:
            List[Dict[str, Any]]: Minimal upcoming event payloads for summary use.
        """
        today = date.today()
        upcoming = [e for e in self.events if e["date"] >= today]
        upcoming.sort(key=lambda x: x["date"])
        out = []
        for e in upcoming[:n]:
            out.append({
                "title": e.get("title", "Sin título"),
                "dt": datetime.combine(e["date"], datetime.min.time())
            })
        return out


# ---------- KV ----------
KV = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set C_BORDER 0,0,0,0.85
#:set C_BLUE 0.15,0.55,0.95,1
#:set C_RED 1,0.23,0.18,1
#:set R_CARD dp(20)
#:set R_CELL dp(16)
#:set R_BTN dp(16)
#:set H_HEADER dp(110)
#:set H_WEEK dp(44)
#:set COL_W dp(180)
#:set ROW_H dp(120)
#:set SP_X dp(22)
#:set SP_Y dp(20)
#:set PAD_X dp(8)
#:set LEGEND_FONT sp(24)
#:set LEGEND_DOT dp(22)
#:set DAY_NUM_FONT sp(22)
#:set DAY_DOT dp(28)
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

<LegendDot>:
    size_hint: None, None
    size: LEGEND_DOT, LEGEND_DOT
    canvas:
        Color:
            rgba: self.rgba
        Ellipse:
            pos: self.pos
            size: self.size

<DayAudienceMarker@BoxLayout>:
    dot_rgba: 0.15, 0.55, 0.95, 1
    size_hint: None, None
    height: dp(29)
    width: self.minimum_width
    spacing: dp(0)
    LegendDot:
        size: dp(29), dp(29)
        rgba: root.dot_rgba

<DayCell@ButtonBehavior+BoxLayout>:
    day_num: 0
    selected: False
    orientation: "vertical"
    padding: dp(6)
    spacing: dp(6)
    size_hint: None, None
    size: COL_W, ROW_H
    canvas.before:
        Color:
            rgba: (0,0,0,1) if self.selected else (1,1,1,1)
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [R_CELL,]
        Color:
            rgba: C_BORDER
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, R_CELL)
    AnchorLayout:
        size_hint: 1, 1
        BoxLayout:
            orientation: "vertical"
            size_hint: 1, None
            height: dp(30) + dp(8) + DAY_DOT
            spacing: dp(8)
            pos_hint: {"center_x": 0.5, "center_y": 0.5}
            Label:
                id: lbl_day
                text: str(root.day_num) if root.day_num else ""
                font_size: DAY_NUM_FONT
                color: (1,1,1,1) if root.selected else (0,0,0,1)
                size_hint_x: 1
                size_hint_y: None
                height: dp(30)
                halign: "center"
                valign: "middle"
                text_size: self.size
            AnchorLayout:
                size_hint_y: None
                height: DAY_DOT
                anchor_x: "center"
                anchor_y: "center"
                BoxLayout:
                    id: dots_box
                    size_hint: None, None
                    height: DAY_DOT
                    width: self.minimum_width
                    spacing: dp(8)

<EventsRoot@FloatLayout>:
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
                id: lbl_calendar_title
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
                    font_size: sp(22)
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
                    on_release: app.root.current = "main"
                IconBadge:
                    icon_source: app.mic_icon if hasattr(app, 'mic_icon') else ""
                    on_release: app.start_assistant()

        # ---------- TARJETA CALENDARIO ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            BoxLayout:
                orientation: "horizontal"
                size_hint: 0.98, 0.94
                spacing: dp(16)
                padding: [dp(8), 0, dp(8), 0]

                AnchorLayout:
                    anchor_x: "left"
                    anchor_y: "center"
                    size_hint: None, 1
                    width: dp(84)
                    ImageButton:
                        src: "data/images/arrowback.png"
                        size_hint: None, None
                        size: dp(72), dp(72)
                        on_release: app.root.get_screen('events').goto_prev()

                AnchorLayout:
                    anchor_x: "center"
                    anchor_y: "center"
                    pos_hint: {"center_y": 0.40}
                    size_hint_x: 1
                    BoxLayout:
                        orientation: "vertical"
                        size_hint: None, None
                        width: COL_W*7 + SP_X*6 + PAD_X*2
                        height: dp(56) + dp(24) + H_WEEK + ROW_H*6 + SP_Y*5 + PAD_X*2
                        spacing: dp(24)
                        Label:
                            id: lbl_month
                            text: ""
                            font_size: sp(46)
                            bold: True
                            color: C_BLACK
                            size_hint_y: None
                            height: dp(56)
                            halign: "center"
                            valign: "middle"
                            text_size: self.size
                        GridLayout:
                            id: weekday_header
                            cols: 7
                            size_hint: None, None
                            width: COL_W*7 + SP_X*6 + PAD_X*2
                            height: H_WEEK
                            spacing: SP_X, 0
                            padding: [PAD_X, 0, PAD_X, 0]
                        GridLayout:
                            id: grid
                            cols: 7
                            rows: 5
                            size_hint: None, None
                            width: COL_W*7 + SP_X*6 + PAD_X*2
                            height: ROW_H*6 + SP_Y*5 + PAD_X*2
                            row_default_height: ROW_H
                            row_force_default: True
                            col_default_width: COL_W
                            col_force_default: True
                            spacing: SP_X, SP_Y
                            padding: [PAD_X, PAD_X, PAD_X, PAD_X]

                AnchorLayout:
                    anchor_x: "right"
                    anchor_y: "center"
                    size_hint: None, 1
                    width: dp(84)
                    ImageButton:
                        src: "data/images/arrowforward.png"
                        size_hint: None, None
                        size: dp(72), dp(72)
                        on_release: app.root.get_screen('events').goto_next()
"""


# ---------- Pantalla ----------
class EventsScreen(Screen):
    """Monthly calendar screen with MQTT/event-bus-driven refresh support.

    Examples:
        >>> # screen = EventsScreen(sm, name="events")
        >>> # screen.refresh_calendar()
    """

    def __init__(self, sm: Any, **kwargs: Any) -> None:
        """Initialize calendar screen and subscribe to refresh signals.

        Args:
            sm: Parent Kivy `ScreenManager`.
            **kwargs: Standard Kivy `Screen` keyword arguments.

        Raises:
            No exception is intentionally raised. Runtime integration failures
            are logged by setup methods.
        """
        super().__init__(**kwargs)
        self.sm = sm
        Builder.load_string(KV)

        self.cfg = AppConfig()
        self.DEFAULT_LOCATION = self.cfg.get_device_location()

        self.store = EventStore()  # loads local cache instantly, no network
        self.today = date.today()
        self.current = date(self.today.year, self.today.month, 1)
        self.root_view = Factory.EventsRoot()
        self.add_widget(self.root_view)

        event_bus.bind(on_events_changed=lambda *_: self.refresh_calendar())

        Clock.schedule_once(lambda *_: self._refresh_header(), 0)
        Clock.schedule_once(lambda *_: self._build_calendar(), 0)
        Clock.schedule_interval(lambda *_: self._refresh_header(), 60)
        # Sync with Mongo in background so startup is not blocked
        Clock.schedule_once(lambda *_: self._reload_store_async(), 1)

        self.setup_mqtt_listener()

    def _reload_store_async(self) -> None:
        """Reload event store from MongoDB in a background thread."""
        def _worker() -> None:
            try:
                self.store.reload(
                    device_name=self.cfg.get_device_id(),
                    location_name=self.cfg.get_device_location(),
                )
            except Exception as e:
                print(f"[EVENTS] Background reload error: {e}")
            Clock.schedule_once(lambda *_: self._build_calendar(), 0)
        threading.Thread(target=_worker, daemon=True).start()

    def update_labels(self) -> None:
        """Refresh translated labels without reloading data."""
        self._refresh_header()
        self._update_weekday_header()

    def _get_day_events_widget(self) -> Any:
        """Locate day-events screen implementation instance.

        Returns:
            Any: Widget implementing `set_store` and `show_day`, or `None`.
        """
        try:
            cont = self.sm.get_screen('day_events')
        except Exception:
            return None
        if hasattr(cont, 'set_store') and hasattr(cont, 'show_day'):
            return cont
        stack = list(getattr(cont, 'children', []))
        while stack:
            w = stack.pop()
            if hasattr(w, 'set_store') and hasattr(w, 'show_day'):
                return w
            stack.extend(getattr(w, 'children', []))
        return None

    def _have_ids(self, *names: str) -> bool:
        """Check whether required KV ids are present in the root view."""
        ids = getattr(self.root_view, "ids", None)
        if not ids:
            return False
        try:
            return all(name in ids for name in names)
        except Exception:
            return False

    def _refresh_header(self) -> None:
        """Refresh date/time, title, legend, and month labels."""
        if not self._have_ids("lbl_today", "lbl_time", "lbl_month", "lbl_calendar_title", "lbl_public", "lbl_personal"):
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
        
        # ✅ Titre "Calendario"
        ids.lbl_calendar_title.text = _("Calendario")
        
        # ✅ Date du jour
        ids.lbl_today.text = f"{dias[now.weekday()].capitalize()}, {now.day} {_('de')} {meses[now.month-1]} {_('de')} {now.year}"
        ids.lbl_time.text = now.strftime("%H:%M")
        
        # ✅ Mois du calendrier affiché
        ids.lbl_month.text = f"{meses[self.current.month-1].capitalize()} {self.current.year}"
        
        # ✅ Légende Público / Personal
        ids.lbl_public.text = _("Público")
        ids.lbl_personal.text = _("Personal")

    def _update_weekday_header(self) -> None:
        """Refresh translated weekday header row."""
        if not self._have_ids("weekday_header"):
            return
        
        weekday_header = self.root_view.ids.weekday_header
        weekday_header.clear_widgets()
        
        # ✅ Jours de la semaine traduits
        dias = [
            _("Lunes"), _("Martes"), _("Miércoles"),
            _("Jueves"), _("Viernes"), _("Sábado"), _("Domingo")
        ]
        
        from kivy.uix.label import Label
        for day_name in dias:
            weekday_header.add_widget(Label(
                text=day_name,
                font_size=sp(28),
                color=(0, 0, 0, 1)
            ))

    def goto_prev(self) -> None:
        """Navigate to previous month and rebuild calendar."""
        y, m = self.current.year, self.current.month
        m -= 1
        if m < 1:
            y -= 1
            m = 12
        self.current = date(y, m, 1)
        self._build_calendar()

    def goto_next(self) -> None:
        """Navigate to next month and rebuild calendar."""
        y, m = self.current.year, self.current.month
        m += 1
        if m > 12:
            y += 1
            m = 1
        self.current = date(y, m, 1)
        self._build_calendar()

    def _build_calendar(self) -> None:
        """Build the current month calendar grid and event markers."""
        if not self._have_ids("grid", "lbl_month"):
            return
        
        # ✅ Mettre à jour les en-têtes des jours
        self._update_weekday_header()
        
        grid = self.root_view.ids.grid
        grid.clear_widgets()
        y, m = self.current.year, self.current.month
        first_wd, ndays = calendar.monthrange(y, m)

        MAX_CELLS = 35

        prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
        _, prev_ndays = calendar.monthrange(prev_y, prev_m)
        leading_days = list(range(prev_ndays - first_wd + 1, prev_ndays + 1))

        current_days = list(range(1, ndays + 1))

        next_days_needed = MAX_CELLS - (len(leading_days) + len(current_days))
        next_days = list(range(1, next_days_needed + 1))

        all_days = [
            (prev_y, prev_m, d, "prev") for d in leading_days
        ] + [
            (y, m, d, "current") for d in current_days
        ] + [
            ((y + 1 if m == 12 else y), (1 if m == 12 else m + 1), d, "next")
            for d in next_days
        ]

        for yy, mm, d, month_type in all_days:
            day_date = date(yy, mm, d)
            evs = self.store.events_on(day_date, self.DEFAULT_LOCATION)
            cell = Factory.DayCell()
            cell.day_num = d

            if month_type == "current":
                cell.opacity = 1.0
            else:
                cell.opacity = 0.4

            cell.selected = (day_date == self.today)

            if evs:
                audience_counts = defaultdict(int)
                for event in evs:
                    audience = (event.get("audience") or "").lower().strip()
                    if audience in {"all", "device"}:
                        audience_counts[audience] += 1

                if audience_counts["all"]:
                    marker = Factory.DayAudienceMarker()
                    marker.dot_rgba = [0.15, 0.55, 0.95, 1]
                    cell.ids.dots_box.add_widget(marker)
                if audience_counts["device"]:
                    marker = Factory.DayAudienceMarker()
                    marker.dot_rgba = [1, 0.23, 0.18, 1]
                    cell.ids.dots_box.add_widget(marker)

            def _open_day(_inst, _d=day_date):
                day_screen = self._get_day_events_widget()
                if day_screen is None:
                    print("[EVENTS] No se encontró DayEventsScreen dentro de 'day_events'.")
                    return
                day_screen.set_store(self.store)
                day_screen.show_day(_d, self.DEFAULT_LOCATION)
                log_navigation("touchscreen", "day_events")
                self.sm.current = 'day_events'

            cell.bind(on_release=_open_day)
            if len(grid.children) < 35:
                grid.add_widget(cell)

        self._refresh_header()

    def get_upcoming_events(self, n: int = 2) -> List[Dict[str, Any]]:
        """Expose upcoming events summary for other screens.

        Args:
            n: Maximum number of events to return.

        Returns:
            List[Dict[str, Any]]: Upcoming event summary list.
        """
        return self.store.get_upcoming(n=n)

    def on_enter(self, *args: Any) -> None:
        """Kivy lifecycle hook executed on every screen entry."""
        self.today = date.today()
        self.current = date(self.today.year, self.today.month, 1)
        self.update_labels()
        self._build_calendar()
        # Refresh from Mongo in background; calendar rebuilds when done
        self._reload_store_async()

    def on_pre_enter(self, *args: Any) -> None:
        """Kivy lifecycle hook executed before screen becomes visible."""
        self.update_labels()
        self._build_calendar()

    def refresh_calendar(self) -> None:
        """Reload store and schedule full calendar rebuild."""
        try:
            old_count = len(self.store.events)
            self.store.reload(
                device_name=self.cfg.get_device_id(),
                location_name=self.cfg.get_device_location(),
            )
            new_count = len(self.store.events)
            
            if new_count > old_count:
                print(f"[EVENTS] {new_count - old_count} new events loaded")
        except Exception as e:
            print(f"[EVENTS] Calendar refresh error: {e}")
        
        Clock.schedule_once(lambda *_: self._build_calendar(), 0)
    
    def setup_mqtt_listener(self) -> None:
        """Configure MQTT listener for remote calendar refresh commands.

        Subscribed topic:
            - `app/nav` with payload target `events` and type `reload`.

        Raises:
            No exception is propagated. Setup failures are logged.
        """
        try:
            def on_message(client, userdata, msg):
                if msg.topic == "app/nav":
                    try:
                        payload = json.loads(msg.payload.decode("utf-8"))
                        
                        if payload.get("target") == "events" and payload.get("type") == "reload":
                            print("[EVENTS] Reload request received via MQTT")
                            Clock.schedule_once(lambda dt: self.refresh_calendar(), 0)
                    
                    except Exception as e:
                        print(f"[EVENTS] MQTT error: {e}")
            
            self.mqtt_client = mqtt.Client(client_id="events_screen_client")
            self.mqtt_client.on_message = on_message
            self.mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
            self.mqtt_client.subscribe("app/nav")
            self.mqtt_client.loop_start()
            print("[EVENTS] MQTT listener enabled")
        
        except Exception as e:
            print(f"[EVENTS] ⚠️ MQTT setup error: {e}")
