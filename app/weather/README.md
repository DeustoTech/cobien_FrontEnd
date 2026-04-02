# Weather Module

## Overview

The `weather` package provides the weather UI and data-access layer used by the
main app. It combines OpenWeather (current conditions) and Open-Meteo
forecasts, then renders:

- Current weather summary.
- Hourly forecast strip.
- Multi-day forecast cards.
- City switching with animated transitions.

## Files

- `weatherScreen.py`: Kivy widget tree, rendering, and interaction logic.
- `weather_data.py`: Provider API fetch and icon/description normalization.
- `weather_today.json`: Local weather cache/sample artifact used by runtime.

## Runtime Responsibilities

1. Receive selected city list from app/MQTT payloads.
2. Fetch provider weather data for active city.
3. Normalize data for UI consumption.
4. Render current, hourly, and daily sections.
5. Expose speech summary for accessibility.

## Known Technical Debt / Bad Practices

- `weatherScreen.py` is a large multi-responsibility file (UI, network
  orchestration, MQTT listener, TTS trigger, animation logic).
- Network and provider parsing errors rely mostly on `print` statements instead
  of structured logging and centralized telemetry.
- Some methods use implicit global assumptions (for example
  `set_city_by_name()` imports a `cities` symbol from the same module).
- API timeout values are duplicated in calls instead of being fully centralized.
- Geocoding and weather-provider calls are directly coupled to UI layer, making
  automated tests difficult without heavy mocking.
