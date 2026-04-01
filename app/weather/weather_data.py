from datetime import datetime, timedelta
import os

import requests
from config_store import load_section


def map_icon_owm(weather_id: int, icon_code: str) -> str:
    is_day = str(icon_code).endswith("d")
    if weather_id // 100 == 2:
        return "images/tormenta.png"
    if weather_id // 100 == 3:
        return "images/lluvia.png"
    if weather_id // 100 == 5:
        return "images/lluvia.png"
    if weather_id // 100 == 6:
        return "images/nieve.png"
    if weather_id // 100 == 7:
        return "images/neblina.png"
    if weather_id == 800:
        return "images/sol.png" if is_day else "images/noche.png"
    if 801 <= weather_id <= 802:
        return "images/parcial.png"
    if 803 <= weather_id <= 804:
        return "images/nubes.png"
    return "images/nubes.png"


def map_icon_openmeteo(code: int, is_day: bool) -> str:
    if code == 0:
        return "images/sol.png" if is_day else "images/noche.png"
    if code in (1, 2):
        return "images/parcial.png"
    if code == 3:
        return "images/nubes.png"
    if code in (45, 48):
        return "images/neblina.png"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "images/lluvia.png"
    if code in (71, 73, 75, 77, 85, 86):
        return "images/nieve.png"
    if code in (95, 96, 99):
        return "images/tormenta.png"
    return "images/nubes.png"


def daily_icon_path(code: int, is_day: bool = True) -> str:
    path = map_icon_openmeteo(code, is_day)
    return path if os.path.exists(path) else "images/nubes.png"


def _openmeteo_description(code: int, api_lang: str) -> str:
    desc_es = {
        0: "Despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Niebla",
        48: "Niebla",
        51: "Llovizna",
        53: "Llovizna",
        55: "Llovizna",
        61: "Lluvia",
        63: "Lluvia",
        65: "Lluvia intensa",
        71: "Nieve",
        73: "Nieve",
        75: "Nieve intensa",
        80: "Chubascos",
        81: "Chubascos",
        82: "Chubascos intensos",
        95: "Tormenta",
    }
    desc_fr = {
        0: "Dégagé",
        1: "Plutôt dégagé",
        2: "Partiellement nuageux",
        3: "Nuageux",
        45: "Brouillard",
        48: "Brouillard",
        51: "Bruine",
        53: "Bruine",
        55: "Bruine",
        61: "Pluie",
        63: "Pluie",
        65: "Forte pluie",
        71: "Neige",
        73: "Neige",
        75: "Forte neige",
        80: "Averses",
        81: "Averses",
        82: "Fortes averses",
        95: "Orage",
    }
    base = desc_fr if (api_lang or "").lower().startswith("fr") else desc_es
    return base.get(int(code), "Variable")


def fetch_weather_bundle(city_name, lat, lon, tz_name, api_lang, owm_api_key, forecast_days=7):
    services_cfg = load_section("services", {})
    openweather_current_url = services_cfg.get("openweather_current_url", "https://api.openweathermap.org/data/2.5/weather")
    open_meteo_url = services_cfg.get("open_meteo_url", "https://api.open-meteo.com/v1/forecast")
    today = datetime.utcnow().date()
    start = end = today.isoformat()

    om_hourly = requests.get(
        open_meteo_url,
        params=dict(
            latitude=lat,
            longitude=lon,
            hourly="temperature_2m,weathercode",
            timezone=tz_name,
            start_date=start,
            end_date=end,
        ),
        timeout=8,
    ).json()

    om_daily = requests.get(
        open_meteo_url,
        params=dict(
            latitude=lat,
            longitude=lon,
            daily="weathercode,temperature_2m_min,temperature_2m_max,precipitation_probability_max",
            timezone=tz_name,
            forecast_days=forecast_days,
        ),
        timeout=8,
    ).json()

    tz_offset = 0
    cur_temp = None
    desc = None
    icon_path = None

    # Try OpenWeather first if API key is configured; fallback to Open-Meteo when unavailable.
    if (owm_api_key or "").strip():
        try:
            cur_url = f"{openweather_current_url}?q={city_name}&appid={owm_api_key}&units=metric&lang={api_lang}"
            cur = requests.get(cur_url, timeout=8).json()
            if isinstance(cur, dict) and "main" in cur and "weather" in cur and cur["weather"]:
                cur_temp = round(float(cur["main"]["temp"]))
                desc = str(cur["weather"][0].get("description", "")).capitalize()
                wid = int(cur["weather"][0].get("id", 803))
                icon_code = cur["weather"][0].get("icon", "01d")
                icon_path = map_icon_owm(wid, icon_code)
                tz_offset = int(cur.get("timezone", 0) or 0)
        except Exception:
            pass

    tmin = round(om_daily["daily"]["temperature_2m_min"][0])
    tmax = round(om_daily["daily"]["temperature_2m_max"][0])

    times = om_hourly["hourly"]["time"]
    temps = om_hourly["hourly"]["temperature_2m"]
    codes = om_hourly["hourly"]["weathercode"]

    if cur_temp is None:
        try:
            cur_temp = round(float(temps[0]))
        except Exception:
            cur_temp = tmin
    if desc is None:
        try:
            desc = _openmeteo_description(int(codes[0]), api_lang)
        except Exception:
            desc = "Variable"
    if icon_path is None:
        try:
            icon_path = map_icon_openmeteo(int(codes[0]), True)
        except Exception:
            icon_path = "images/nubes.png"

    hourly_items = []
    now_local = datetime.utcnow() + timedelta(seconds=tz_offset)
    for t, tmp, code in zip(times, temps, codes):
        dt = datetime.fromisoformat(t)
        if dt >= now_local and len(hourly_items) < 12:
            hourly_items.append((dt, round(tmp), code))
    if len(hourly_items) < 12:
        for t, tmp, code in zip(times, temps, codes):
            dt = datetime.fromisoformat(t)
            if dt < now_local and len(hourly_items) < 12:
                hourly_items.append((dt, round(tmp), code))

    return {
        "city": city_name,
        "temp": cur_temp,
        "temp_min": tmin,
        "temp_max": tmax,
        "description": desc,
        "icon": icon_path,
        "tz_offset": tz_offset,
        "hourly_items": hourly_items,
        "daily": om_daily["daily"],
    }
