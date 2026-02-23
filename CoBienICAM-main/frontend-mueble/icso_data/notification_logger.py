# icso_data/notification_logger.py
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt

# Received Photos
def log_received_photos():
    state = load_full_state()

    # Update
    state["board"]["received_photos"] += 1
   
    # JSON
    write_log_json(state)

    # TXT
    write_log_txt(f"NEW NOTIFICATION : ADDED PICTURE")


# Added events
def log_added_events():
    state = load_full_state()

    # Update
    state["events"]["added_events"] += 1
   
    # JSON
    write_log_json(state)

    # TXT
    write_log_txt(f"NEW NOTIFICATION : ADDED EVENT")

