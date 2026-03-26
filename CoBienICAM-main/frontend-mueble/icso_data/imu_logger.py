# icso_data/imu_logger.py

import os
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt


def log_imu_event(event_type: str):
    """
    event_type ∈ {"movement_start", "movement_stop"}
    """

    state = load_full_state()

    # Assurer que la section IMU existe
    if "imu" not in state:
        state["imu"] = {
            "state": "idle",
            "movements": 0
        }

    # Mapping event → texte humain
    if event_type == "movement_start":
        readable = "IMU → Moving"
        state["imu"]["state"] = "moving"

    elif event_type == "movement_stop":
        readable = "IMU → Idle"
        state["imu"]["state"] = "idle"
        state["imu"]["movements"] += 1

    else:
        readable = f"IMU → {event_type}"

    # --- LOG TXT ---
    write_log_txt(readable)

    # --- LOG JSON ---
    write_log_json(state)
