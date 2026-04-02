"""Navigation telemetry logger.

This module increments aggregated counters for page views and navigation input
channels, then writes both JSON snapshot and readable text traces.
"""

from .log_writer import load_full_state, write_log_json, write_log_txt


def log_navigation(source: str, target: str, recognized: str = None) -> None:
    """Log one navigation action in ICSO telemetry.

    Args:
        source: Navigation origin (`touchscreen`, `home_button`, etc.).
        target: Navigation destination/page key.
        recognized: Optional recognized ASR phrase associated with action.

    Returns:
        None.

    Raises:
        OSError: If state or text logs cannot be written.

    Examples:
        >>> log_navigation("touchscreen", "events")
        >>> log_navigation("vocal_assistant", "weather", recognized="ver el tiempo")
    """
    state = load_full_state()
    target = (target or "").lower()
    source = (source or "").lower()

    if target in state["page_views"]:
        state["page_views"][target] += 1

    if source in state["navigation_inputs"]:
        state["navigation_inputs"][source] += 1

    write_log_txt(source, target, recognized)
    write_log_json(state)
