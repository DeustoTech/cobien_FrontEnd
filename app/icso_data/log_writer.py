"""Core ICSO telemetry state and text-log writer utilities.

This module centralizes:

- Persistent aggregate telemetry state (`icso_log.json`).
- Human-readable activity logs (`icso_log.txt`).
- Dedicated proximity event log (`icso_proximity_sensors.txt`).

All outputs are stored under ``app/logs``.
"""

import copy
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

MODULE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.dirname(MODULE_DIR)
LOG_DIR = os.path.join(APP_DIR, "logs")

LOG_TXT = os.path.join(LOG_DIR, "icso_log.txt")
LOG_JSON = os.path.join(LOG_DIR, "icso_log.json")
LOG_PROXIMITY_TXT = os.path.join(LOG_DIR, "icso_proximity_sensors.txt")

os.makedirs(LOG_DIR, exist_ok=True)

DEFAULT_STATE = {
    "page_views": {
        "weather": 0,
        "events": 0,
        "day_events": 0,
        "contacts": 0,
        "board": 0
    },
    "navigation_inputs": {
        "touchscreen": 0,
        "home_button": 0,
        "vocal_assistant": 0,
        "rfid_cards": 0
    },
    "imu": {
        "state": "idle",
        "movements": 0
    },
    "video_calls": {
        "call_requests": 0,
        "calls_made": 0,
        "last_duration_sec": 0,
        "total_duration_sec": 0
    },
    "board": {
        "received_photos": 0
    },
    "events": {
        "added_events": 0
    },
    "screen_wakeup": {
        "wakeups": 0
    },
    "proximity": {
        "north": {
            "motion_detected": 0,
            "approach_detected": 0
        },
        "south": {
            "motion_detected": 0,
            "approach_detected": 0
        },
        "east": {
            "motion_detected": 0,
            "approach_detected": 0
        },
        "west": {
            "motion_detected": 0,
            "approach_detected": 0
        }
    }
}


def _schedule_background_sync(force_snapshot: bool = False) -> None:
    try:
        from .sync_service import schedule_icso_sync

        schedule_icso_sync(force_snapshot=force_snapshot)
    except Exception:
        pass


def _deep_merge_defaults(current: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively populate missing keys from a default state template.

    Args:
        current: Current loaded state.
        defaults: Default state schema and values.

    Returns:
        Dict[str, Any]: State dictionary containing all required keys.

    Examples:
        >>> _deep_merge_defaults({"imu": {}}, {"imu": {"state": "idle"}})
        {'imu': {'state': 'idle'}}
    """
    if not isinstance(current, dict) or not isinstance(defaults, dict):
        return copy.deepcopy(defaults)

    for key, default_val in defaults.items():
        if key not in current:
            current[key] = copy.deepcopy(default_val)
            continue
        if isinstance(default_val, dict):
            if not isinstance(current[key], dict):
                current[key] = copy.deepcopy(default_val)
            else:
                _deep_merge_defaults(current[key], default_val)
    return current


def load_full_state() -> Dict[str, Any]:
    """Load telemetry state from disk with schema self-healing.

    If the state file is missing or unreadable, the default state is returned.
    Missing nested sections are automatically restored from ``DEFAULT_STATE``.

    Returns:
        Dict[str, Any]: Complete telemetry state.

    Raises:
        No exception is propagated. Disk and parsing errors are handled
        internally with fallback to defaults.

    Examples:
        >>> state = load_full_state()
        >>> state["imu"]["state"]
        'idle'
    """
    if not os.path.exists(LOG_JSON):
        return copy.deepcopy(DEFAULT_STATE)

    try:
        with open(LOG_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return copy.deepcopy(DEFAULT_STATE)

    # Fill all missing sections recursively.
    return _deep_merge_defaults(data, DEFAULT_STATE)


def write_log_json(state: Dict[str, Any]) -> None:
    """Persist telemetry state snapshot to JSON.

    Args:
        state: Telemetry state dictionary to serialize.

    Returns:
        None.

    Raises:
        OSError: If output file cannot be written.
        TypeError: If state contains non-serializable values.
    """
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    _schedule_background_sync(force_snapshot=True)


def write_log_txt(
    source: Any,
    target: Optional[str] = None,
    recognized: Optional[str] = None,
) -> None:
    """Append one formatted telemetry line to text logs.

    Routing rules:
    - Proximity events are written to ``icso_proximity_sensors.txt``.
    - All other events are written to ``icso_log.txt``.

    Args:
        source: Event source identifier (for example, ``"touchscreen"``).
        target: Optional target/action descriptor.
        recognized: Optional ASR recognized phrase (used for vocal assistant logs).

    Returns:
        None.

    Raises:
        OSError: If target log file cannot be written.

    Examples:
        >>> write_log_txt(source="touchscreen", target="events")
        >>> write_log_txt(source="vocal_assistant", target="weather", recognized="qué tiempo hace")
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    label_map = {
        "touchscreen": "TOUCHSCREEN",
        "home_button": "HOME BUTTON",
        "vocal_assistant": "VOCAL ASSISTANT",
        "rfid_cards": "RFID CARD",
        "imu": "IMU",
        "videocall": "VIDEO CALL",
        "notification": "NOTIFICATION",
        "wakeup": "SCREEN WAKEUP",
        "proximity": "PROXIMITY",
    }

    source_str = str(source or "").strip()
    if not source_str:
        source_str = "SYSTEM"

    # Backward-compatible raw message mode.
    if target is None and source_str not in label_map:
        line = f"[{now}] {source_str}"
        with open(LOG_TXT, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return

    label = label_map.get(source_str, source_str.upper())

    if source_str == "rfid_cards" and target == "videocall":
        target = "videocall request"

    if source_str == "vocal_assistant" and target in (None, "assistant_triggered"):
        line = f"[{now}] ACTIVATION VOCAL ASSISTANT"
    elif source_str == "vocal_assistant" and target is not None:
        recog_text = (recognized or "").strip()
        if recog_text:
            line = f"[{now}] VOCAL ASSISTANT → {target} (recognized: {recog_text})"
        else:
            line = f"[{now}] VOCAL ASSISTANT → {target}"
    elif source_str == "proximity" and target is not None:
        line = f"[{now}] PROXIMITY → {target}"
    elif target is not None:
        line = f"[{now}] VIA {label} → {target}"
    else:
        line = f"[{now}] {label}"

    log_path = LOG_PROXIMITY_TXT if source_str == "proximity" else LOG_TXT

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    _schedule_background_sync(force_snapshot=False)
