# Events Module

Calendar and event-management module for CoBien.

## Scope

- Load events from MongoDB with fallback to local JSON cache.
- Filter by configured device and location.
- Display monthly calendar (`eventsScreen.py`) and daily detail view (`dayEventsScreen.py`).
- Add/delete personal events and propagate UI refresh signals.

## Files

- `loadEvents.py`
  - Data access layer for event retrieval, insertion, deletion.
  - Handles fallback to `eventos_local.json` when MongoDB is unavailable.

- `event_bus.py`
  - Lightweight Kivy `EventDispatcher` used to broadcast `on_events_changed`.

- `eventsScreen.py`
  - Monthly calendar UI.
  - Renders day markers for public/personal events.
  - Navigates to day detail screen.

- `dayEventsScreen.py`
  - Daily events UI with delete flow for personal entries.
  - Voice-assisted personal event creation flow.

- `eventos_local.json`
  - Local fallback cache file.
  - Contains normalized event payloads used when backend connectivity fails.

- `__init__.py`
  - Package marker and high-level module description.

## Local Cache Format (`eventos_local.json`)

Typical keys per event:

- `id`: event identifier (`ObjectId` string or `local-*` fallback id)
- `date`: `dd-mm-YYYY` string
- `title`
- `description`
- `location`
- `audience`: `all` or `device`
- `target_device` (optional)
- `color` (UI helper)

## Data Flow

1. UI requests events through `get_events()` / `fetch_events_from_mongo()`.
2. MongoDB is queried with `(audience, device, location)` filters.
3. Results are normalized and cached to `eventos_local.json`.
4. On backend errors, cached local events are used.
5. Mutations trigger `event_bus.notify_events_changed()` to refresh screens.
