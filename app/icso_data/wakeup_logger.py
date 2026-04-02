"""Screen wake-up telemetry logger."""

from .log_writer import load_full_state, write_log_json, write_log_txt


def log_wakeup() -> None:
    """Increment wake-up counter and append readable wake-up log.

    Returns:
        None.

    Raises:
        OSError: If state/text logs cannot be written.

    Examples:
        >>> log_wakeup()
    """
    state = load_full_state()
    state["screen_wakeup"]["wakeups"] += 1
    write_log_json(state)
    write_log_txt(source="wakeup")
