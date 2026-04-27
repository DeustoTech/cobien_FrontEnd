"""Daily 8am event summary overlay.

Shows a full-screen modal with today's events at 8:00 every day.
Only displayed when at least one event exists for today.
Dismissed on tap or automatically after AUTO_DISMISS_SECS seconds.
"""

from datetime import datetime, date, timedelta
from typing import Any, List, Dict

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse

from app_config import AppConfig

AUTO_DISMISS_SECS = 45
_TARGET_HOUR = 8


def _seconds_until_next_8am() -> float:
    now = datetime.now()
    target = now.replace(hour=_TARGET_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _build_time_label(event: Dict[str, Any]) -> str:
    if event.get("all_day", True) or not event.get("start_time"):
        return ""
    t = event["start_time"]
    if event.get("end_time"):
        t += f" – {event['end_time']}"
    return t


def _make_dot(rgba) -> Widget:
    dot = Widget(size_hint=(None, None), size=(dp(26), dp(26)))
    with dot.canvas:
        Color(*rgba)
        dot._ellipse = Ellipse(pos=dot.pos, size=dot.size)
    dot.bind(pos=lambda w, _: setattr(w._ellipse, 'pos', w.pos))
    return dot


def _build_overlay(events: List[Dict[str, Any]]) -> ModalView:
    overlay = ModalView(
        auto_dismiss=True,
        size_hint=(1, 1),
        background="",
        background_color=(0, 0, 0, 0.60),
    )

    card = BoxLayout(
        orientation="vertical",
        size_hint=(None, None),
        size=(dp(1050), dp(780)),
        pos_hint={"center_x": 0.5, "center_y": 0.5},
        spacing=dp(16),
        padding=(dp(40), dp(32), dp(40), dp(32)),
    )

    with card.canvas.before:
        Color(1, 1, 1, 0.97)
        _bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(28)])
        Color(0, 0, 0, 0.18)
        _border = Line(rounded_rectangle=(card.x, card.y, card.width, card.height, dp(28)), width=2)

    def _sync(*_):
        _bg.pos = card.pos
        _bg.size = card.size
        _border.rounded_rectangle = (card.x, card.y, card.width, card.height, dp(28))

    card.bind(pos=_sync, size=_sync)

    # --- Header ---
    now = datetime.now()
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    date_text = f"{dias[now.weekday()].capitalize()}, {now.day} de {meses[now.month-1]}"

    header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90), spacing=dp(4))
    lbl_title = Label(
        text="Buenos días",
        font_size=sp(40),
        bold=True,
        color=(0, 0, 0, 1),
        halign="center",
        valign="middle",
        size_hint_y=None,
        height=dp(52),
    )
    lbl_title.bind(size=lambda w, _: setattr(w, "text_size", w.size))
    lbl_date = Label(
        text=date_text,
        font_size=sp(22),
        color=(0, 0, 0, 0.55),
        halign="center",
        valign="middle",
        size_hint_y=None,
        height=dp(34),
    )
    lbl_date.bind(size=lambda w, _: setattr(w, "text_size", w.size))
    header.add_widget(lbl_title)
    header.add_widget(lbl_date)
    card.add_widget(header)

    # --- Divider ---
    div = Widget(size_hint_y=None, height=dp(1))
    with div.canvas:
        Color(0, 0, 0, 0.15)
        div._rect = RoundedRectangle(pos=div.pos, size=div.size, radius=[dp(1)])
    div.bind(pos=lambda w, _: setattr(w._rect, 'pos', w.pos),
             size=lambda w, _: setattr(w._rect, 'size', w.size))
    card.add_widget(div)

    # --- Subtitle ---
    n = len(events)
    subtitle_txt = f"Tienes {n} evento{'s' if n != 1 else ''} hoy"
    lbl_sub = Label(
        text=subtitle_txt,
        font_size=sp(24),
        color=(0.15, 0.55, 0.95, 1),
        halign="center",
        valign="middle",
        size_hint_y=None,
        height=dp(38),
        bold=True,
    )
    lbl_sub.bind(size=lambda w, _: setattr(w, "text_size", w.size))
    card.add_widget(lbl_sub)

    # --- Event list ---
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(6))
    list_box = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(10),
        padding=(0, dp(4), 0, dp(4)),
    )
    list_box.bind(minimum_height=list_box.setter("height"))

    for ev in events:
        aud = ev.get("audience", "all")
        dot_color = (0.15, 0.55, 0.95, 1) if aud == "all" else (1, 0.23, 0.18, 1)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(72),
            spacing=dp(14),
            padding=(dp(14), dp(10), dp(14), dp(10)),
        )
        with row.canvas.before:
            Color(1, 1, 1, 1)
            row._bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(16)])
            Color(0, 0, 0, 0.12)
            row._border = Line(rounded_rectangle=(row.x, row.y, row.width, row.height, dp(16)), width=1.4)

        def _sync_row(w, *_):
            w._bg.pos = w.pos
            w._bg.size = w.size
            w._border.rounded_rectangle = (w.x, w.y, w.width, w.height, dp(16))

        row.bind(pos=_sync_row, size=_sync_row)

        dot_anchor = BoxLayout(size_hint=(None, 1), width=dp(40))
        dot = _make_dot(dot_color)
        dot_anchor.add_widget(Widget())
        dot_anchor.add_widget(dot)
        dot_anchor.add_widget(Widget())
        row.add_widget(dot_anchor)

        txt_col = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=dp(2))
        t_label = _build_time_label(ev)
        title_text = ev.get("title", "Sin título")
        if t_label:
            title_text = f"{title_text}  [{t_label}]"
        lbl_ev_title = Label(
            text=title_text,
            font_size=sp(22),
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(30),
        )
        lbl_ev_title.bind(size=lambda w, _: setattr(w, "text_size", w.size))
        lbl_ev_desc = Label(
            text=ev.get("description", ""),
            font_size=sp(17),
            color=(0, 0, 0, 0.55),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(24),
        )
        lbl_ev_desc.bind(size=lambda w, _: setattr(w, "text_size", w.size))
        txt_col.add_widget(lbl_ev_title)
        txt_col.add_widget(lbl_ev_desc)
        row.add_widget(txt_col)
        list_box.add_widget(row)

    scroll.add_widget(list_box)
    card.add_widget(scroll)

    # --- Close hint ---
    lbl_hint = Label(
        text="Toca para cerrar",
        font_size=sp(18),
        color=(0, 0, 0, 0.38),
        halign="center",
        valign="middle",
        size_hint_y=None,
        height=dp(30),
    )
    lbl_hint.bind(size=lambda w, _: setattr(w, "text_size", w.size))
    card.add_widget(lbl_hint)

    overlay.add_widget(card)
    overlay.bind(on_touch_up=lambda *_: overlay.dismiss())
    return overlay


def _fetch_todays_events() -> List[Dict[str, Any]]:
    from events.loadEvents import cargar_eventos_locales
    cfg = AppConfig()
    today = date.today()
    today_str = today.strftime("%d-%m-%Y")
    try:
        events = cargar_eventos_locales(cfg.get_device_location()) or []
    except Exception:
        events = []
    return [e for e in events if e.get("date", "") == today_str]


def _show_if_events(*_args: Any) -> None:
    """Load today's events and show overlay if any exist."""
    try:
        events = _fetch_todays_events()
        if not events:
            return
        overlay = _build_overlay(events)
        overlay.open()
        Clock.schedule_once(lambda *_: overlay.dismiss(), AUTO_DISMISS_SECS)
    except Exception as exc:
        print(f"[MORNING SUMMARY] Error: {exc}")
    finally:
        _schedule_next()


def _schedule_next(*_args: Any) -> None:
    delay = _seconds_until_next_8am()
    Clock.schedule_once(_show_if_events, delay)
    print(f"[MORNING SUMMARY] Next summary in {delay/3600:.1f}h")


def schedule_morning_summary() -> None:
    """Call once from app.on_start to activate the daily 8am summary."""
    delay = _seconds_until_next_8am()
    # If already past 8am today but within 2 minutes, show immediately
    now = datetime.now()
    target_today = now.replace(hour=_TARGET_HOUR, minute=0, second=0, microsecond=0)
    if now >= target_today and (now - target_today).total_seconds() < 120:
        Clock.schedule_once(_show_if_events, 1)
    else:
        Clock.schedule_once(_show_if_events, delay)
    print(f"[MORNING SUMMARY] Scheduled. Next fire in {delay/3600:.1f}h")
