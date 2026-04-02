# Notifications Module

Runtime notification subsystem for CoBien.

## Scope

- Display modal notifications for incoming calls, new events, and new board messages.
- Trigger LED effects through MQTT according to per-type configuration.
- Play configured ringtones with backend fallback (`pygame` -> `playsound`).
- Publish MQTT refresh commands for target screens.
- Cache active notifications for runtime resilience.

## Files

- `notification_manager.py`
  - Main orchestration layer for popups and user actions.
  - Integrates screen navigation side effects, ring/LED triggers, and cache updates.

- `notification_runtime.py`
  - Runtime config loader/saver and ringtone playback helpers.
  - Abstracts audio backend detection and asynchronous playback.

- `mqtt_led_sender.py`
  - Central helper to publish LED strip config payloads over MQTT.

- `__init__.py`
  - Package marker and module description.

## Data and Runtime Paths

- Notification cache:
  - `app/notifications/cache/active_notifications.json`
- Notification config source:
  - Unified config via `config_store` section `notifications`
  - Legacy materialized file path variable points to `app/config/notifications_config.json`
- Ringtones directory:
  - `app/settings/ringtones/`

## Message Flow

1. Manager receives an incoming logical notification (`videocall`, `event`, `message`).
2. LED payload is sent via MQTT helper based on configured profile.
3. Ringtone playback starts from runtime config.
4. Popup is shown and action callback is bound.
5. User action triggers navigation/launch side effects and cache cleanup.

## Known Technical Debt / Bad Practices

- `notification_manager.py` is large and mixes UI construction, business logic, and transport side effects.
- Extensive use of `print()` instead of structured logging with severity/context.
- Broad exception handling patterns reduce root-cause visibility.
- Hardcoded resource paths and inline popup layout code increase maintenance cost.
- Cache and state updates have no explicit locking strategy for concurrent access scenarios.
