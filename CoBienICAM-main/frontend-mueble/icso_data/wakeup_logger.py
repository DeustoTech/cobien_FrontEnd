# icso_data/wakeup_logger.py
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt

# Received Photos
def log_wakeup():
    state = load_full_state()

    # Update
    state["screen_wakeup"]["wakeups"] += 1
   
    # JSON
    write_log_json(state)

    # TXT
    write_log_txt(f"NEW SCREEN WAKEUP")
