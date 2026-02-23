# icso_data/videocall_logger.py
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt

# Call Requests
def log_call_request():
    state = load_full_state()

    # Update
    state["video_calls"]["call_requests"] += 1
   
    # JSON
    write_log_json(state)


# Start video call
def log_call_start():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_log_txt(f"[{timestamp}] VIDEO_CALL → start")


# End video call
def log_call_end(duration_sec: int):
    state = load_full_state()

    # Update
    state["video_calls"]["calls_made"] += 1
    state["video_calls"]["last_duration_sec"] = duration_sec
    state["video_calls"]["total_duration_sec"] += duration_sec

    # TXT
    write_log_txt(f"VIDEO_CALL → END ({duration_sec}s)")

    # JSON
    write_log_json(state)
