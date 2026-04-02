# Reminders Module

## Overview

The `reminders` module provides local, offline reminder scheduling for the
CoBien application. It persists reminders in JSON format and restores pending
timers after application restarts.

Main responsibilities:

- Create reminders from a delay and message.
- Persist reminders to `recordatorios.json`.
- Reschedule pending reminders during startup.
- Trigger reminder feedback (voice + log output).
- Remove reminders once executed or expired.

## Files

- `reminders.py`: Reminder lifecycle manager (`RecordatorioManager`).
- `recordatorios.json` (runtime data): Stored reminder entries.

## Data Contract

Each reminder entry follows:

```json
{
  "mensaje": "Tomar medicación",
  "hora": "2026-04-02 14:30:00"
}
```

## Runtime Flow

1. A reminder is configured with a delay in seconds.
2. The manager computes the target datetime and stores it in JSON.
3. A Kivy `Clock.schedule_once` callback is registered.
4. On startup, pending reminders are reloaded and rescheduled.
5. When triggered, the reminder is spoken (if available) and removed from file.

## Known Technical Debt / Bad Practices

- Persistence key uses reminder message text as delete identifier; duplicate
  messages can cause accidental multi-delete behavior.
- Startup rescheduling parses datetimes without per-entry error isolation; one
  malformed entry can break the full reload path.
- No file locking or atomic write strategy, which can be risky under concurrent
  writes.
- Logging uses `print` instead of centralized structured logging.
- Hardcoded language in user-visible strings (Spanish) and no i18n integration
  inside this module.
