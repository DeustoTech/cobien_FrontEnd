# icso_data/navigation_logger.py
import os
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt


def log_navigation(source: str, target: str, recognized: str = None):
    state = load_full_state()
    target = (target or "").lower()
    source = (source or "").lower()

    if target in state["page_views"]:
        state["page_views"][target] += 1

    if source in state["navigation_inputs"]:
        state["navigation_inputs"][source] += 1

    write_log_txt(source, target, recognized)
    write_log_json(state)
