from datetime import datetime, timedelta
import os

import requests


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


def fetch_weather_bundle(city_name, lat, lon, tz_name, api_lang, owm_api_key, forecast_days=7):
    cur_url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city_name}&appid={owm_api_key}&units=metric&lang={api_lang}"
    )
    cur = requests.get(cur_url, timeout=8).json()
    cur_temp = round(cur["main"]["temp"])
    desc = cur["weather"][0]["description"].capitalize()
    wid = int(cur["weather"][0]["id"])
    icon_code = cur["weather"][0].get("icon", "01d")
    icon_path = map_icon_owm(wid, icon_code)
    tz_offset = cur.get("timezone", 0)

    today = (datetime.utcnow() + timedelta(seconds=tz_offset)).date()
    start = end = today.isoformat()

    om_hourly = requests.get(
        "https://api.open-meteo.com/v1/forecast",
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
        "https://api.open-meteo.com/v1/forecast",
        params=dict(
            latitude=lat,
            longitude=lon,
            daily="weathercode,temperature_2m_min,temperature_2m_max,precipitation_probability_max",
            timezone=tz_name,
            forecast_days=forecast_days,
        ),
        timeout=8,
    ).json()

    tmin = round(om_daily["daily"]["temperature_2m_min"][0])
    tmax = round(om_daily["daily"]["temperature_2m_max"][0])

    times = om_hourly["hourly"]["time"]
    temps = om_hourly["hourly"]["temperature_2m"]
    codes = om_hourly["hourly"]["weathercode"]
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
