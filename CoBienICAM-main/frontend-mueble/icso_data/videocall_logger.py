# icso_data/videocall_logger.py
from datetime import datetime
from .log_writer import load_full_state, write_log_json, write_log_txt


def log_call_request():
    state = load_full_state()
    state["video_calls"]["call_requests"] += 1
    write_log_json(state)


def log_call_start():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_log_txt(f"[{timestamp}] VIDEO_CALL → start")


def log_call_end(duration_sec: int):
    state = load_full_state()
    state["video_calls"]["calls_made"] += 1
    state["video_calls"]["last_duration_sec"] = duration_sec
    state["video_calls"]["total_duration_sec"] += duration_sec
    write_log_txt(f"VIDEO_CALL → END ({duration_sec}s)")
    write_log_json(state)
