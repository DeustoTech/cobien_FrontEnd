"""Proximity sensor telemetry logger for CAN-derived events.

This module transforms filtered CAN proximity events into aggregated counters
and dedicated readable log lines.
"""

from typing import Dict

from icso_data.log_writer import load_full_state, write_log_json, write_log_txt

EVENT_MOTION_START = 0x5EBA1ADE
EVENT_APPROACH = 0xD157A4CE
EVENT_MOTION_END = 0xE5ABA1ED

SENSOR_MAP: Dict[int, str] = {
    0x475: "north",
    0x474: "south",
    0x476: "east",
    0x477: "west",
}

LABEL_MAP = {
    "north": "NORTH",
    "south": "SOUTH",
    "east": "EAST",
    "west": "WEST",
}


def log_proximity_event(can_id: int, event_code: int) -> None:
    """Log one proximity event and update aggregated counters.

    Args:
        can_id: CAN arbitration ID of proximity sensor.
        event_code: Decoded event code extracted from payload.

    Returns:
        None.

    Raises:
        OSError: If state or text logs cannot be written.

    Examples:
        >>> log_proximity_event(0x475, EVENT_MOTION_START)
    """
    if can_id not in SENSOR_MAP:
        return

    position = SENSOR_MAP[can_id]
    state = load_full_state()

    if "proximity" not in state:
        state["proximity"] = {}

    if position not in state["proximity"]:
        state["proximity"][position] = {
            "motion_detected": 0,
            "approach_detected": 0
        }

    changed = False
    log_label = None

    if event_code == EVENT_MOTION_START:
        state["proximity"][position]["motion_detected"] += 1
        changed = True
        log_label = "MOTION"

    elif event_code == EVENT_APPROACH:
        state["proximity"][position]["approach_detected"] += 1
        changed = True
        log_label = "APPROACH"

    elif event_code == EVENT_MOTION_END:
        log_label = "MOTION_END"

    if changed:
        write_log_json(state)

    if log_label is not None:
        write_log_txt(source="proximity", target=f"{log_label} {LABEL_MAP[position]}")
