# icso_data/wakeup_logger.py
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt


def log_wakeup():
    state = load_full_state()
    state["screen_wakeup"]["wakeups"] += 1
    write_log_json(state)
    write_log_txt(f"NEW SCREEN WAKEUP")
