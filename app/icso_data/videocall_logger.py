"""Video-call telemetry logger.

Tracks call requests, call lifecycle, and cumulative durations.
"""

from .log_writer import load_full_state, write_log_json, write_log_txt


def log_call_request() -> None:
    """Increment video-call request counter.

    Returns:
        None.

    Raises:
        OSError: If state file cannot be written.

    Examples:
        >>> log_call_request()
    """
    state = load_full_state()
    state["video_calls"]["call_requests"] += 1
    write_log_json(state)


def log_call_start() -> None:
    """Write human-readable call start log line.

    Returns:
        None.

    Raises:
        OSError: If text log cannot be written.
    """
    write_log_txt(source="videocall", target="start")


def log_call_end(duration_sec: int) -> None:
    """Record call completion and update duration aggregates.

    Args:
        duration_sec: Call duration in seconds.

    Returns:
        None.

    Raises:
        OSError: If state/text logs cannot be written.

    Examples:
        >>> log_call_end(183)
    """
    state = load_full_state()
    state["video_calls"]["calls_made"] += 1
    state["video_calls"]["last_duration_sec"] = duration_sec
    state["video_calls"]["total_duration_sec"] += duration_sec
    write_log_txt(source="videocall", target=f"end ({duration_sec}s)")
    write_log_json(state)
