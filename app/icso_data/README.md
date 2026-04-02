# ICSO Data Module

ICSO telemetry layer for local analytics and operational traceability.

## Scope

- Maintain a persistent aggregated state snapshot (`icso_log.json`).
- Append readable chronological logs (`icso_log.txt`).
- Keep proximity sensor traces separated (`icso_proximity_sensors.txt`).
- Provide domain loggers for navigation, IMU, notifications, wakeups, video calls, and proximity.

## Files

- `log_writer.py`
  - Core state loader/writer and text-line formatter.
  - Output directory: `app/logs/`.

- `navigation_logger.py`
  - Increments page view and input-channel counters.

- `imu_logger.py`
  - Tracks movement start/stop transitions and movement count.

- `notification_logger.py`
  - Tracks board photo and event notification intake.

- `videocall_logger.py`
  - Tracks call requests, call starts, call durations.

- `wakeup_logger.py`
  - Tracks screen wake-up events.

- `proximity_sensor_logger.py`
  - Updates per-direction proximity counters from CAN-derived event codes.

- `proximity_sensors_logger.py`
  - Compatibility wrapper exposing the same API under legacy naming.

## Output Artifacts (Stored in `app/logs`)

- `icso_log.json`: Aggregated telemetry snapshot.
- `icso_log.txt`: General readable chronological log.
- `icso_proximity_sensors.txt`: Dedicated proximity chronological log.

## Data Flow

1. Feature module triggers a domain logger (for example `log_navigation`).
2. Domain logger loads current state via `load_full_state()`.
3. Counters/state values are updated.
4. Updated state is persisted with `write_log_json()`.
5. A readable trace line is appended with `write_log_txt()` where applicable.

## Known Technical Debt / Bad Practices

- No concurrency control for JSON/TXT writes (risk of race conditions under parallel writes).
- Domain loggers are tightly coupled to dictionary key names and hardcoded state schema.
- Minimal input validation on logger APIs (unexpected values are often accepted silently).
- No log rotation/retention policy in this module; output files can grow indefinitely.
- Structured logging (`logging` with levels/context) is not used; plain text lines are generated manually.
