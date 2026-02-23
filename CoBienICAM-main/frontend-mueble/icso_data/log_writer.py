# icso_data/log_writer.py

import os
import json
from datetime import datetime

DATA_DIR = os.path.dirname(__file__)
LOG_TXT = os.path.join(DATA_DIR, "icso_log.txt")
LOG_JSON = os.path.join(DATA_DIR, "icso_log.json")
LOG_PROXIMITY_TXT = os.path.join(DATA_DIR, "icso_proximity_sensors.txt")

os.makedirs(DATA_DIR, exist_ok=True)

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

def load_full_state():
    if not os.path.exists(LOG_JSON):
        return DEFAULT_STATE.copy()

    try:
        with open(LOG_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return DEFAULT_STATE.copy()

    # Ajouter les clés manquantes automatiquement
    for key, default_val in DEFAULT_STATE.items():
        if key not in data:
            data[key] = default_val

    return data


def write_log_json(state: dict):
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


def write_log_txt(source, target=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    label_map = {
        "touchscreen": "TOUCHSCREEN",
        "home_button": "HOME BUTTON",
        "vocal_assistant": "VOCAL ASSISTANT",
        "rfid_cards": "RFID CARD"
    }

    label = label_map.get(source, source.upper())

    if source == "rfid_cards" and target == "videocall":
        target = "videocall request"

    if source == "vocal_assistant":
        line = f"[{now}] ACTIVATION VOCAL ASSISTANT"
    elif target is not None:
        line = f"[{now}] VIA {label} → {target}"
    else:
        line = f"[{now}] {label}"
    
    log_path = LOG_PROXIMITY_TXT if source == "proximity" else LOG_TXT

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

