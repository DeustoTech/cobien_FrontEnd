# Logging Audit

This document captures the current state of the furniture runtime logs before
they are exposed through the web administration UI.

## Scope

The review focuses on the three operational log files created by the launcher:

- `cobien-app-YYYYMMDD.log`
- `can-bus-YYYYMMDD.log`
- `mqtt-can-bridge-YYYYMMDD.log`

The goal is to define what should remain visible for support, what should be
translated or normalized, and what should be removed or downgraded before these
logs are made available on the web.

## Current Retention Policy

The launcher already prunes old dated logs through `cleanup_old_logs()`.

Current default retention after this change:

- `COBIEN_LOG_RETENTION_DAYS=90`

This applies to:

- `can-bus-*.log`
- `mqtt-can-bridge-*.log`
- `cobien-app-*.log`

## Findings

## Translation Status

### Already normalized to English

The core runtime logs have already been translated to English in:

- `app/mainApp.py`
- `app/notifications/notification_manager.py`
- `app/events/eventsScreen.py`
- `app/events/dayEventsScreen.py`
- `app/settings/weatherChoice.py`
- `app/settings/rfidActionsScreen.py`
- `app/settings/notificationsScreen.py`
- `app/settings/settingsScreen.py`
- `app/settings/pinCodeScreen.py`
- `app/settings/jokeCategoryScreen.py`
- `app/weather/weatherScreen.py`
- `app/videocall/videocall_launcher.py`
- `app/videocall/confirmation_popup.py`
- `app/videocall/request_call.py`
- `app/mqtt_publisher.py`
- `app/translation.py`
- `app/virtual_assistant/recognizer.py`
- `app/settings/buttonColorsScreen.py`
- `app/settings/languageScreen.py`
- `app/events/loadEvents.py`
- `app/jokes/jokesScreen.py`
- `app/compile_translations.py`

This includes the main operational paths used during support:

- startup and device identity
- backend polling
- backend notification handling
- message and videocall notification flow
- cache and weather fallback messages
- assistant availability warnings
- main screen reload actions

Examples that were normalized:

- `Erreur résolution nom` -> `Name resolution error`
- `Demande d'appel` -> `Call request`
- `Notification envoyée` -> `Notification sent`
- `Météo` -> `Weather`
- `Événement ignoré (mauvaise ville)` -> `Event ignored (wrong city)`
- `Appel manqué` -> `Missed call`
- `Démarrage` -> `Starting`
- `Fermeture notification 'Appel entrant'` -> `Closing 'Incoming call' notification`

### Remaining minor cleanup targets

The remaining work is no longer about mixed-language logging in the main
runtime. It is now mostly about reducing verbosity and removing low-value
success chatter in secondary modules.

Current low-priority targets:

- `app/settings/notificationsScreen.py`
- `app/settings/buttonColorsScreen.py`
- `app/weather/weatherScreen.py`
- `app/videocall/videocall_launcher.py`
- `app/mqtt_publisher.py`
- `app/virtual_assistant/recognizer.py`

### 1. What is already useful and should be kept

These messages are relevant for remote support and incident diagnosis:

- App startup context
  - device id
  - videocall room
  - active location
  - language
  - idle timeout
- Backend polling and notification flow
  - poll enabled / missing config
  - poll failures
  - notification type received
  - board reload, events reload, contacts sync
- Videocall lifecycle
  - incoming call
  - accepted / declined / expired
  - launcher start failure
  - room / caller data
- Weather failures and fallback usage
  - fetch error
  - cache fallback loaded
- Contacts synchronization failures
- Bridge/CAN startup failures
  - build failure
  - missing binary
  - missing CAN tooling

These areas should remain visible in the future web log viewer.

### 2. Logging direction after normalization

Operational logs are now expected to stay in English.

Current direction:

- keep runtime and support logs in English
- keep log prefixes stable, for example:
  - `[APP]`
  - `[BACKEND POLL]`
  - `[BACKEND NOTIF]`
  - `[NOTIF]`
  - `[EVENTS]`
  - `[WEATHER]`
  - `[CAN]`
  - `[BRIDGE]`

- keep prefixes stable and machine-friendly
- avoid mixed language strings inside the same subsystem

### 3. What is currently too noisy for web exposure

The following categories are too verbose and should be removed, reduced, or
downgraded before the logs are published on the web:

- repeated UI refresh traces
  - `Labels updated`
  - `on_pre_enter`
  - `on_enter terminé`
  - `Calendrier planifié`
- debug state dumps
  - `_subscribed_local = ...`
  - repeated `DEBUG` refresh traces
  - counts printed on every small UI action
- jokes subsystem chatter
  - joke reloads
  - joke previews
  - category fallback chatter
- decorative separators and emoji-heavy messages
  - repeated `========================================`
  - emoji-only signal noise
- repeated tracebacks in normal recovery paths
  - weather timeout traces
  - board refresh tracebacks
  - launcher fallback tracebacks after handled exceptions

Status after the first and second cleanup passes:

- major UI lifecycle chatter has already been reduced in:
  - `app/mainApp.py`
  - `app/notifications/notification_manager.py`
  - `app/settings/weatherChoice.py`
  - `app/events/eventsScreen.py`
  - `app/settings/rfidActionsScreen.py`
- secondary chatter has also been reduced in:
  - `app/settings/buttonColorsScreen.py`
  - `app/settings/jokeCategoryScreen.py`
  - `app/settings/languageScreen.py`
  - `app/settings/settingsScreen.py`
  - `app/settings/notificationsScreen.py`
  - `app/weather/weatherScreen.py`
  - `app/events/dayEventsScreen.py`
  - `app/videocall/videocall_launcher.py`
  - `app/mqtt_publisher.py`
  - `app/virtual_assistant/recognizer.py`

Recommendation:

- keep one concise line for success paths
- keep warnings only when there is user-visible degradation or recovery
- keep tracebacks only for real `ERROR` cases

### 4. What should not be exposed to the web without filtering

Before publishing logs in the furniture admin UI, these details should be
reviewed and possibly redacted or truncated:

- notification payload fragments
- sender names
- caller names
- room names
- device identifiers
- local filesystem paths
- raw JSON payloads
- Python tracebacks with local path disclosure

Recommendation:

- show at most the last two days in the web
- truncate long payloads
- hide full tracebacks behind a secondary details toggle if needed

## Concrete Classification

### Keep

- startup summary
- backend poll status
- notification type handling
- videocall accepted / declined / expired
- bridge build start / build error / launch error
- CAN logger enabled / disabled / unavailable
- weather fetch failure and cache fallback
- contacts sync failure
- event reload request

### Translate / Normalize

- keep new runtime log strings in English only
- reject new French or mixed-language log additions during review

### Remove or Downgrade

- joke reload chatter
- UI lifecycle chatter
- `DEBUG` traces
- repeated separators
- success spam that repeats every refresh cycle

## Suggested Next Step

Before implementing the web viewer, the safest next move is:

1. finish reducing remaining low-value success chatter
2. define a minimal severity model for future replacements of ad-hoc `print()`
3. decide redaction rules for names, rooms, payloads, and local paths
4. design the backend storage and retrieval shape for the last two days only
5. implement the web viewer in furniture administration

## Remaining Files To Revisit

- `app/settings/notificationsScreen.py`
- `app/settings/buttonColorsScreen.py`
- `app/weather/weatherScreen.py`
- `app/videocall/videocall_launcher.py`
- `app/mqtt_publisher.py`
- `app/virtual_assistant/recognizer.py`
