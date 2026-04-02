# Settings Module

## Overview

The `settings` package contains all administration and runtime configuration
screens for the CoBien frontend. It centralizes user-facing configuration flows
such as language, notifications, launcher parameters, weather cities, RFID
actions, logs inspection, and UI color tuning.

## Main Responsibilities

- Render settings navigation and feature-specific configuration screens.
- Persist user preferences through shared config helpers.
- Trigger runtime updates (MQTT publish, UI refresh, launcher hooks).
- Provide operational tools (logs viewer, launcher parameters, PIN gate).

## Files

- `settingsScreen.py`: Settings dashboard entrypoint.
- `languageScreen.py`: Language selection and save flow.
- `jokeCategoryScreen.py`: Joke category selector.
- `pinCodeScreen.py`: PIN-based admin access gate.
- `notificationsScreen.py`: Notification colors/ringtones configuration.
- `buttonColorsScreen.py`: Hardware button color behavior setup.
- `weatherChoice.py`: Weather city selection and prioritization.
- `rfidActionsScreen.py`: RFID card-to-action mapping.
- `launcherConfigScreen.py`: Launcher environment parameters.
- `logsScreen.py`: Runtime log browser screens.

## Known Technical Debt / Bad Practices

- Several files are very large and combine UI layout, business rules, IO, and
  integration logic in one module, increasing maintenance cost.
- Extensive use of `print` statements instead of centralized structured logging.
- Repeated widget definitions and duplicated styling patterns across files.
- Heavy reliance on dynamic `Any`-style dependencies and shared mutable app
  state, making strict typing and unit testing difficult.
- Broad exception handling blocks (`except Exception`) hide error specificity.
- Runtime side-effects (MQTT publish, file writes, subprocess calls) are often
  triggered directly from UI event handlers.

## Documentation Status

Documentation pass is in progress:

- Completed in this step:
  - `settingsScreen.py`
  - `languageScreen.py`
  - `jokeCategoryScreen.py`
  - `weatherChoice.py`
  - `notificationsScreen.py`
  - `rfidActionsScreen.py`
  - `buttonColorsScreen.py`
  - `launcherConfigScreen.py`
  - `logsScreen.py`
  - `pinCodeScreen.py`

No pending files in this package for the current documentation pass.
