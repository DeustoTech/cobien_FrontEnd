"""IMU telemetry logger.

This module records IMU movement state transitions into the shared ICSO state
and appends a readable event line through the common log writer.
"""

from .log_writer import load_full_state, write_log_json, write_log_txt


def log_imu_event(event_type: str) -> None:
    """Record one IMU state transition.

    Supported values:
    - ``"movement_start"``
    - ``"movement_stop"``

    Args:
        event_type: IMU transition event identifier.

    Returns:
        None.

    Raises:
        OSError: If underlying state/log files cannot be written.

    Examples:
        >>> log_imu_event("movement_start")
        >>> log_imu_event("movement_stop")
    """

    state = load_full_state()

    # Ensure IMU section exists.
    if "imu" not in state:
        state["imu"] = {
            "state": "idle",
            "movements": 0
        }

    if event_type == "movement_start":
        state["imu"]["state"] = "moving"
        target = "moving"

    elif event_type == "movement_stop":
        state["imu"]["state"] = "idle"
        state["imu"]["movements"] += 1
        target = "idle"

    else:
        target = event_type

    write_log_txt(source="imu", target=target)
    write_log_json(state)
