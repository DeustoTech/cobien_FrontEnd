# file: weather/weatherScreen.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.uix.widget import Widget
from kivy.animation import Animation
from datetime import datetime, timedelta
import threading
import requests
import os
import pyttsx3
from translation import _
from kivy.app import App
import paho.mqtt.client as mqtt
import json
from app_config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
from weather.weather_data import daily_icon_path, fetch_weather_bundle, map_icon_openmeteo, map_icon_owm

KV = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

# ====== CONSTANTES VISUALES ======
#:set CARD_R dp(24)
#:set HEADER_ALPHA 0.72
#:set BUTTON_ALPHA 1
#:set BORDER_ALPHA 0.28
#:set SEP_ALPHA 0.28
#:set HEADER_ICON_RADIUS dp(14)

# Tamaño de los botones
#:set HEADER_BTN_SIZE dp(80)
#:set HEADER_BTN_PAD  dp(6)
#:set HEADER_BTN_RADIUS dp(16)
#:set HEADER_ROW_H dp(96)

<RoundedHeaderImage@Image>:
    canvas.before:
        StencilPush
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [HEADER_ICON_RADIUS, HEADER_ICON_RADIUS, HEADER_ICON_RADIUS, HEADER_ICON_RADIUS]
        StencilUse
    canvas.after:
        StencilUnUse
        StencilPop

<Divider@Widget>:
    size_hint_y: None
    height: 1.3
    canvas:
        Color:
            rgba: 0,0,0,SEP_ALPHA
        Rectangle:
            pos: self.pos
            size: self.size

<RoundCard@BoxLayout>:
    padding: [dp(22), dp(18), dp(22), dp(18)]
    spacing: dp(14)
    canvas.before:
        Color:
            rgba: 1, 1, 1, HEADER_ALPHA
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [CARD_R, CARD_R, CARD_R, CARD_R]

<IconBtn@ButtonBehavior+BoxLayout>:
    size_hint: None, None
    size: HEADER_BTN_SIZE, HEADER_BTN_SIZE
    padding: HEADER_BTN_PAD
    canvas.before:
        Color:
            rgba: 1, 1, 1, BUTTON_ALPHA
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [HEADER_BTN_RADIUS, HEADER_BTN_RADIUS, HEADER_BTN_RADIUS, HEADER_BTN_RADIUS]
        Color:
            rgba: 0, 0, 0, BORDER_ALPHA
        Line:
            width: 2.2
            rounded_rectangle: (self.x, self.y, self.width, self.height, HEADER_BTN_RADIUS)

<DayCard@BoxLayout>:
    orientation: "vertical"
    padding: [dp(22), dp(22), dp(22), dp(22)]
    spacing: dp(6)
    size_hint: 1, 1
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(22), dp(22), dp(22), dp(22)]

<WeatherScreenWidget>:
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if app.has_bg_image else ""

    orientation: "vertical"
    padding: [root.layout_gap, root.layout_gap, root.layout_gap, root.layout_gap]
    spacing: root.layout_gap
    on_size: root._recalc_heights()


    BoxLayout:
        x: root.transition_x
        opacity: root.transition_alpha
        orientation: "vertical"
        spacing: root.layout_gap

        RoundCard:
            id: card_header
            size_hint_y: None
            height: root.cards_height
            canvas.before:
                Color:
                    rgba: 1, 1, 1, HEADER_ALPHA * root.transition_alpha

            BoxLayout:
                orientation: "vertical"
                spacing: dp(10)

                BoxLayout:
                    orientation: "horizontal"
                    size_hint_x: 1
                    padding: [dp(8), 0, dp(8), 0]
                    size_hint_y: None
                    height: HEADER_ROW_H

                    AnchorLayout:
                        anchor_y: "center"
                        anchor_x: "left"
                        
                        BoxLayout:
                            orientation: "vertical"
                            spacing: dp(10)
                            size_hint: None, None
                            width: dp(900)
                            height: dp(400)

                            Label:
                                id: lbl_title
                                text: ""
                                bold: True
                                font_size: sp(80)
                                color: 0,0,0,1
                                halign: "left"
                                valign: "middle"
                                size_hint_y: None
                                height: self.texture_size[1]
                                text_size: (self.width, None)

                            Widget:
                                size_hint_y: None
                                height: dp(10)

                            Label:
                                text: root.city
                                bold: True
                                font_size: sp(120)
                                color: 0,0,0,1
                                halign: "left"
                                valign: "middle"
                                size_hint_y: None
                                height: self.texture_size[1]
                                text_size: (self.width, None)

                        
                        AnchorLayout:
                            anchor_x: "right"
                            anchor_y: "top"
                            size_hint_x: None
                            width: dp(200) if root.show_city_navigation else 0
                            opacity: 1 if root.show_city_navigation else 0
                        
                            BoxLayout:
                                orientation: "horizontal"
                                spacing: dp(10)
                                size_hint: None, None
                                width: dp(200)
                                height: dp(250)

                                IconBtn:
                                    disabled: not root.show_city_navigation
                                    on_release: root.prev_city()
                                    RoundedHeaderImage:
                                        source: root.arrow_back
                                        size_hint: None, None
                                        size: dp(72), dp(72)

                                IconBtn:
                                    disabled: not root.show_city_navigation
                                    on_release: root.next_city()
                                    RoundedHeaderImage:
                                        source: root.arrow_forward
                                        size_hint: None, None
                                        size: dp(72), dp(72)
                                    
                        AnchorLayout:
                            anchor_x: "right"
                            anchor_y: "center"
                        
                            BoxLayout:
                                orientation: "horizontal"
                                spacing: dp(10)
                                size_hint: None, None
                                width: dp(200)
                                height: dp(90)

                                IconBtn:
                                    on_touch_up: (root.go_back(), setattr(self,'state','normal')) if self.collide_point(*args[1].pos) else None
                                    RoundedHeaderImage:
                                        source: root.icon_back
                                        allow_stretch: True
                                        keep_ratio: True

                                IconBtn:
                                    #on_touch_up: (root.speak_window_info(), setattr(self,'state','normal')) if self.collide_point(*args[1].pos) else None
                                    on_release:
                                        root.speak_window_info()
                                        self.state = 'normal'
                                    RoundedHeaderImage:
                                        source: root.icon_voice
                                        allow_stretch: True
                                        keep_ratio: True

                AnchorLayout:
                    size_hint_y: 1
                    anchor_y: "top"
                    anchor_x: "center"
                    padding: [dp(200), 0, 0, 0]

                    BoxLayout:
                        orientation: "horizontal"
                        size_hint: None, None
                        height: dp(160)
                        width: self.minimum_width
                        spacing: dp(18)

                        Image:
                            source: root.current_icon
                            size_hint: None, None
                            size: dp(120), dp(120)
                            allow_stretch: True
                            keep_ratio: True

                        BoxLayout:
                            orientation: "vertical"
                            size_hint: None, None
                            width: dp(500)
                            height: dp(160)

                            BoxLayout:
                                orientation: "horizontal"
                                size_hint_y: None
                                height: dp(96)
                                spacing: dp(0)

                                Label:
                                    text: root.current_temp
                                    font_size: sp(96)
                                    bold: True
                                    color: 0,0,0,1
                                    halign: "left"
                                    valign: "center"
                                    text_size: self.size
                                    size_hint_x: None
                                    width: dp(300)

                                BoxLayout:
                                    orientation: "vertical"
                                    size_hint_x: None
                                    width: dp(180)
                                    Label:
                                        text: root.today_minmax_left
                                        font_size: sp(35)
                                        color: 0,0,0,1
                                        halign: "left"
                                        valign: "top"
                                        text_size: self.size
                                        size_hint_y: None
                                        height: dp(34)
                                    Widget:
                                        size_hint_y: 1
                                    Label:
                                        text: root.today_minmax_right
                                        font_size: sp(35)
                                        color: 0,0,0,1
                                        halign: "left"
                                        valign: "bottom"
                                        text_size: self.size
                                        size_hint_y: None
                                        height: dp(34)

                            Label:
                                text: root.current_desc
                                font_size: sp(40)
                                color: 0,0,0,1
                                halign: "left"
                                valign: "middle"
                                text_size: self.size
                                size_hint_y: None
                                height: dp(60)

                Divider:

                ScrollView:
                    size_hint_y: None
                    height: dp(160)
                    bar_width: 0
                    do_scroll_y: False
                    GridLayout:
                        id: hourly_grid
                        cols: 12
                        size_hint_y: None
                        height: dp(150)
                        row_default_height: dp(150)
                        col_default_width: dp(120)
                        spacing: dp(16)
                        padding: [0,0,0,0]

        RoundCard:
            id: card_daily
            size_hint_y: None
            height: root.cards_height
            padding: [dp(22), dp(18), dp(22), dp(18)]
            BoxLayout:
                id: daily_row
                orientation: "horizontal"
                spacing: dp(22)
"""

Builder.load_string(KV)


def _am_pm_label(dt: datetime) -> str:
    h = dt.hour
    return f"{(h % 12) or 12} {_('a.m.')}" if h < 12 else f"{(h % 12) or 12} {_('p.m.')}"


def _weekday_name(dt: datetime) -> str:
    dias_keys = [_("Lunes"), _("Martes"), _("Miércoles"), _("Jueves"), _("Viernes"), _("Sábado"), _("Domingo")]
    return dias_keys[dt.weekday()]


class WeatherScreenWidget(BoxLayout):

    transition_alpha = NumericProperty(1.0)
    transition_x = NumericProperty(0)
    city = StringProperty("")
    current_temp = StringProperty("—°")
    current_desc = StringProperty("")
    current_icon = StringProperty("images/sol.png")
    today_minmax_left = StringProperty("")
    today_minmax_right = StringProperty("")

    arrow_back = StringProperty("images/arrowback.png")
    arrow_forward = StringProperty("images/arrowforward.png")
    icon_back = StringProperty("images/back.png")
    icon_voice = StringProperty("images/voice.png")
    show_city_navigation = BooleanProperty(False)

    layout_gap = NumericProperty(dp(20))
    cards_height = NumericProperty(0)
    
    weekday_names = ListProperty([])

    owm_api_key = os.getenv("OWM_API_KEY", "6128e2f97c533ad711be849699cb4d47")

    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm

        self.setup_mqtt_listener()

        # Vocal assistant
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty("rate", 150)
        self.tts_engine.setProperty("volume", 0.9)

        # List of cities
        self.cities = []
        self.city_index = 0

        # City parameters
        self.city = ""
        self.lat = 0
        self.lon = 0
        self.tz_name = "UTC"

        # ✅ Language parameter for API - will be updated dynamically
        self.api_lang = "es"  # Default

        # Initialiser les textes traduits
        self.update_labels()

        Clock.schedule_once(lambda dt: self._recalc_heights())
        Clock.schedule_once(lambda dt: self._update_title())
        Clock.schedule_interval(lambda dt: self._refresh_async(), 120)

    
    def update_labels(self):
        """✅ Met à jour les labels ET la langue de l'API"""
        # ✅ Mettre à jour la langue de l'API selon la langue de l'interface
        app = App.get_running_app()
        lang = app.cfg.data.get("language", "es")
        self.api_lang = lang
        print(f"[WEATHER] 🌍 API language set to: {self.api_lang}")
        
        self.current_desc = _("Cargando…")
        self.today_minmax_left = f"{_('Min')} —°"
        self.today_minmax_right = f"{_('Max')} —°"
        
        # Mettre à jour le titre si disponible
        if hasattr(self, 'ids') and 'lbl_title' in self.ids:
            self._update_title()

    def _update_title(self, *args):
        """Met à jour le titre avec la ville actuelle"""
        if hasattr(self, 'ids') and 'lbl_title' in self.ids:
            self.ids.lbl_title.text = f"{_('Tiempo')}"

    def set_city_list(self, cities):
        if not cities:
            print("[WEATHER] The list is empty")
            self.show_city_navigation = False
            return
        
        self.cities = cities
        self.show_city_navigation = len(self.cities) > 1
        self.city_index = 0
        self._set_city(self.cities[0])
        self._refresh_async()

    def _geocode_city(self, name):
        """Résout automatiquement lat/lon/tz via OpenStreetMap."""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            resp = requests.get(
                url,
                params={"format": "json", "q": name},
                headers={"User-Agent": "CoBien-Meteo-App"},
                timeout=5
            )
            data = resp.json()

            if not data:
                print(f"[GEO] {_('Aucune correspondance pour la ville')} : {name}")
                return None

            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            tz_url = (
                "https://api.open-meteo.com/v1/timezone?"
                f"latitude={lat}&longitude={lon}"
            )
            tz_resp = requests.get(tz_url, timeout=5).json()
            tz = tz_resp.get("timezone", "UTC")

            return {"name": name, "lat": lat, "lon": lon, "tz": tz}

        except Exception as e:
            print(f"[GEO] {_('Erreur géocodage')} {name}: {e}")
            return None
    
    def setup_mqtt_listener(self):
        """Configure l'écoute MQTT pour les mises à jour"""
        try:
            def on_message(client, userdata, msg):
                if msg.topic == "app/nav":
                    try:
                        payload = json.loads(msg.payload.decode("utf-8"))
                        if payload.get("target") == "weather_list":
                            cities = payload.get("extra", {}).get("cities", [])
                            print(f"[WEATHER] 📥 {len(cities)} villes reçues")
                            Clock.schedule_once(lambda dt: self.set_city_list(cities))
                    except Exception as e:
                        print(f"[WEATHER] Erreur MQTT: {e}")
            
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_message = on_message
            self.mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
            self.mqtt_client.subscribe("app/nav")
            self.mqtt_client.loop_start()
            print("[WEATHER] ✅ Listener MQTT activé")
        
        except Exception as e:
            print(f"[WEATHER] ⚠️ Erreur setup MQTT: {e}")

    def set_city_dynamic(self, name, lat, lon, tz):
        """Met à jour dynamiquement la ville appelée par une carte RFID."""

        # On garde exactement le nom reçu (déjà normalisé côté publisher)
        target = name.strip()

        # 1) Chercher cette ville dans la liste existante
        for i, c in enumerate(self.cities):
            if c["name"].lower() == target.lower():
                # On met l'index interne AU BON endroit
                self.city_index = i
                # Et on applique la ville via la même logique que les flèches
                self._set_city(c)
                return

        # 2) Si jamais la ville n'est pas dans la liste (ne devrait pas arriver
        #    si tout vient bien du fichier texte), on loggue juste et on affiche quand même
        print(f"[RFID] ⚠️ Ville '{target}' non trouvée dans self.cities (liste météo)")
        self.city = target
        self.lat = lat
        self.lon = lon
        self.tz_name = tz
        self._refresh_async()

    def _set_city(self, c):
        self.city = c["name"]
        self.lat = c["lat"]
        self.lon = c["lon"]
        self.tz_name = c["tz"]
        self._update_title()
        self._refresh_async()

    def next_city(self):
        if len(self.cities) < 2:
            return
    
        anim_out = Animation(
            transition_x=-self.width,
            transition_alpha=0,
            duration=0.25,
            t='in_out_cubic'
        )
    
        def on_animation_complete(anim, widget):
            self.city_index = (self.city_index + 1) % len(self.cities)
            self._set_city(self.cities[self.city_index])
            self._refresh_async()
            
            self.transition_x = self.width
            self.transition_alpha = 0
        
            anim_in = Animation(
                transition_x=0,
                transition_alpha=1,
                duration=0.25,
                t='in_out_cubic'
            )
            anim_in.start(self)
    
        anim_out.bind(on_complete=on_animation_complete)
        anim_out.start(self)

    def prev_city(self):
        if len(self.cities) < 2:
            return
        
        anim_out = Animation(
            transition_x=self.width,
            transition_alpha=0,
            duration=0.25,
            t='in_out_cubic'
        )
        
        def on_animation_complete(anim, widget):
            self.city_index = (self.city_index - 1) % len(self.cities)
            self._set_city(self.cities[self.city_index])
            self._refresh_async()
            
            self.transition_x = -self.width
            self.transition_alpha = 0
            
            anim_in = Animation(
                transition_x=0,
                transition_alpha=1,
                duration=0.25,
                t='in_out_cubic'
            )
            anim_in.start(self)
        
        anim_out.bind(on_complete=on_animation_complete)
        anim_out.start(self)
        
    def go_back(self):
        self.sm.current = "main"

    def _refresh_async(self):
        if not self.city:
            return
        threading.Thread(target=self._fetch_all_and_render, daemon=True).start()

    def _recalc_heights(self, *args):
        avail = self.height - 2 * self.layout_gap - self.layout_gap
        self.cards_height = max(0, avail / 2.0)

    def speak_window_info(self):
        texto = (
            f"{self.current_desc}. {_('Temperatura actual')} "
            f"{self.current_temp.replace('°', ' ' + _('grados'))}. "
            #f"{self.today_minmax_left.replace('°', ' ' + _('grados'))} {_('y')} "
            #f"{self.today_minmax_right.replace('°', ' ' + _('grados'))}."
        )
        print(texto)
        if hasattr(self, "main_ref"):
            self.main_ref.speak(texto)
        #self.tts_engine.say(texto)
        #self.tts_engine.runAndWait()s

    def _fetch_all_and_render(self):
        try:
            print(f"[WEATHER] 🌐 Fetching weather with lang={self.api_lang}")
            bundle = fetch_weather_bundle(
                city_name=self.city,
                lat=self.lat,
                lon=self.lon,
                tz_name=self.tz_name,
                api_lang=self.api_lang,
                owm_api_key=self.owm_api_key,
                forecast_days=7,
            )
            days = []
            daily = bundle["daily"]
            for i in range(1, 7):
                d_dt = datetime.fromisoformat(daily["time"][i])
                code_val = int(daily["weathercode"][i])
                pop_list = daily.get("precipitation_probability_max", [None] * len(daily["time"]))
                days.append(
                    dict(
                        name=_weekday_name(d_dt),
                        code=code_val,
                        tmin=round(daily["temperature_2m_min"][i]),
                        tmax=round(daily["temperature_2m_max"][i]),
                        pop=pop_list[i] if i < len(pop_list) else None,
                    )
                )

            def _apply(_dt):
                self.current_temp = f"{bundle['temp']}°"
                self.current_desc = bundle["description"]
                self.today_minmax_left = f"{_('Min')} {bundle['temp_min']}°"
                self.today_minmax_right = f"{_('Max')} {bundle['temp_max']}°"
                if os.path.exists(bundle["icon"]):
                    self.current_icon = bundle["icon"]
                self._render_hourly(bundle["hourly_items"])
                self._render_daily(days)

            Clock.schedule_once(_apply)

        except Exception as e:
            print(f"[WEATHER] Error: {e}")

    def _render_hourly(self, items):
        grid = self.ids.hourly_grid
        grid.clear_widgets()
        for dt, temp, code in items:
            col = BoxLayout(orientation="vertical", padding=dp(2), spacing=dp(6))
            lbl_t = Label(text=_am_pm_label(dt), font_size=sp(20), color=(0, 0, 0, 1),
                          halign="center", valign="middle", size_hint_y=None, height=dp(24))
            icon = Image(source=self._map_icon_openmeteo(code, is_day=6 <= dt.hour < 20),
                         size_hint_y=None, height=dp(84), allow_stretch=True, keep_ratio=True)
            lbl_v = Label(text=f"{temp}°", font_size=sp(26), bold=True, color=(0, 0, 0, 1),
                          halign="center", valign="middle", size_hint_y=None, height=dp(32))
            col.add_widget(lbl_t); col.add_widget(icon); col.add_widget(lbl_v)
            grid.add_widget(col)

    def _render_daily(self, days):
        row = self.ids.daily_row
        row.clear_widgets()
        for d in days:
            card = Factory.DayCard()
            title = Label(text=d["name"], font_size=sp(40), color=(0, 0, 0, 1),
                          size_hint_y=None, height=dp(40), halign="center", valign="middle")
            icon = Image(source=self._daily_icon_path(d["code"], True),
                         allow_stretch=True, keep_ratio=True,
                         size_hint_y=None, height=dp(128))
            pop_txt = f"{d['pop']}%" if d.get("pop") not in (None, 0) else ""
            pop = Label(text=pop_txt, font_size=sp(30), color=(0, 0, 0, 1),
                        size_hint_y=None, height=dp(28), halign="center", valign="middle")
            mm = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(76), spacing=dp(6))
            mm.add_widget(Label(text=f"{_('Min')} {d['tmin']}°", font_size=sp(30), color=(0, 0, 0, 1),
                                halign="center", valign="middle"))
            mm.add_widget(Label(text=f"{_('Max')} {d['tmax']}°", font_size=sp(30), color=(0, 0, 0, 1),
                                halign="center", valign="middle"))

            card.add_widget(Widget(size_hint_y=1)); card.add_widget(title)
            card.add_widget(Widget(size_hint_y=1)); card.add_widget(icon)
            card.add_widget(Widget(size_hint_y=1)); card.add_widget(pop)
            card.add_widget(Widget(size_hint_y=1)); card.add_widget(mm)
            card.add_widget(Widget(size_hint_y=1))
            row.add_widget(card)

    def _daily_icon_path(self, code, is_day=True):
        try:
            code_int = int(code)
        except Exception:
            code_int = 3
        return daily_icon_path(code_int, is_day)

    def _map_icon_owm(self, weather_id: int, icon_code: str) -> str:
        return map_icon_owm(weather_id, icon_code)

    def set_city_by_name(self, name: str):
        from weather.weatherScreen import cities
        for i, c in enumerate(cities):
            if c["name"].lower() == name.lower():
                self.city_index = i
                self._set_city(c)
                self._refresh_async()
                break

    def _map_icon_openmeteo(self, code: int, is_day: bool) -> str:
        return map_icon_openmeteo(code, is_day)

    def on_pre_enter(self, *args):
        """✅ Mise à jour des traductions avant d'entrer dans l'écran"""
        self.update_labels()
        Clock.schedule_once(lambda *_: self._update_title(), 0)
        # ✅ Rafraîchir les données météo avec la nouvelle langue
        if self.city:
            self._refresh_async()
