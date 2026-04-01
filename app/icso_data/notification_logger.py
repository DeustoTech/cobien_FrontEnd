# icso_data/notification_logger.py
from .log_writer import load_full_state, write_log_json, write_log_txt


def log_received_photos():
    state = load_full_state()
    state["board"]["received_photos"] += 1
    write_log_json(state)
    write_log_txt(source="notification", target="added_picture")


def log_added_events():
    state = load_full_state()
    state["events"]["added_events"] += 1
    write_log_json(state)
    write_log_txt(source="notification", target="added_event")
