import json
import os
import threading
from datetime import datetime, timezone

import requests

from config_store import load_section
from icso_data.log_writer import (
    LOG_JSON,
    LOG_PROXIMITY_TXT,
    LOG_TXT,
    load_full_state,
)


MODULE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.dirname(MODULE_DIR)
RUNTIME_STATE_DIR = os.path.join(APP_DIR, "runtime_state")
SYNC_STATE_PATH = os.path.join(RUNTIME_STATE_DIR, "icso_sync_state.json")

DEFAULT_SYNC_STATE = {
    "txt_offset": 0,
    "proximity_offset": 0,
    "last_snapshot_sync_at": "",
    "last_events_sync_at": "",
    "last_error": "",
}

_SYNC_LOCK = threading.Lock()
_SYNC_THREAD = None
_SYNC_PENDING_FORCE_SNAPSHOT = False


def _safe_read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _safe_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)
    os.replace(tmp_path, path)


def _load_sync_state():
    state = dict(DEFAULT_SYNC_STATE)
    state.update(_safe_read_json(SYNC_STATE_PATH, {}))
    return state


def _save_sync_state(state):
    merged = dict(DEFAULT_SYNC_STATE)
    merged.update(state or {})
    _safe_write_json(SYNC_STATE_PATH, merged)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _build_headers():
    services = load_section("services", {})
    api_key = str(services.get("notify_api_key", "") or "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    return headers


def _load_runtime_context():
    settings = load_section("settings", {})
    services = load_section("services", {})
    backend_base_url = str(services.get("backend_base_url", "") or "").strip().rstrip("/")
    telemetry_url = str(
        services.get("icso_telemetry_url")
        or (f"{backend_base_url}/pizarra/api/icso/telemetry/" if backend_base_url else "")
    ).strip()
    events_url = str(
        services.get("icso_events_url")
        or (f"{backend_base_url}/pizarra/api/icso/events/" if backend_base_url else "")
    ).strip()
    timeout_sec = float(services.get("http_timeout_sec", 8) or 8)
    device_id = str(settings.get("device_id", "") or "").strip()
    return {
        "device_id": device_id,
        "telemetry_url": telemetry_url,
        "events_url": events_url,
        "timeout_sec": timeout_sec,
    }


def _read_new_lines(path, previous_offset):
    if not os.path.exists(path):
        return [], 0

    current_size = os.path.getsize(path)
    offset = previous_offset if isinstance(previous_offset, int) and previous_offset >= 0 else 0
    if offset > current_size:
        offset = 0

    with open(path, "r", encoding="utf-8") as fh:
        fh.seek(offset)
        chunk = fh.read()
        new_offset = fh.tell()

    if not chunk:
        return [], new_offset

    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    return lines, new_offset


def _build_snapshot_payload(device_id):
    snapshot = load_full_state()
    snapshot_updated_at = _utc_now_iso()
    if os.path.exists(LOG_JSON):
        try:
            with open(LOG_JSON, "r", encoding="utf-8") as fh:
                snapshot = json.load(fh)
        except Exception:
            snapshot = load_full_state()

    return {
        "device_id": device_id,
        "captured_at": snapshot_updated_at,
        "snapshot": snapshot,
    }


def _parse_timestamp_from_line(line):
    if not line.startswith("["):
        return ""
    closing = line.find("]")
    if closing <= 1:
        return ""
    raw = line[1:closing].strip()
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return ""


def _build_event_docs(device_id, source_name, lines):
    events = []
    for line in lines:
        events.append(
            {
                "device_id": device_id,
                "source": source_name,
                "logged_at": _parse_timestamp_from_line(line) or _utc_now_iso(),
                "message": line,
            }
        )
    return events


def sync_icso_to_backend(force_snapshot=False):
    context = _load_runtime_context()
    device_id = context["device_id"]
    telemetry_url = context["telemetry_url"]
    events_url = context["events_url"]
    timeout_sec = context["timeout_sec"]

    if not device_id:
        raise ValueError("ICSO sync requires settings.device_id")
    if not telemetry_url or not events_url:
        raise ValueError("ICSO sync URLs are not configured")

    headers = _build_headers()
    state = _load_sync_state()

    if force_snapshot or os.path.exists(LOG_JSON):
        snapshot_payload = _build_snapshot_payload(device_id)
        snapshot_response = requests.post(
            telemetry_url,
            headers=headers,
            json=snapshot_payload,
            timeout=timeout_sec,
        )
        snapshot_response.raise_for_status()
        state["last_snapshot_sync_at"] = _utc_now_iso()

    txt_lines, txt_offset = _read_new_lines(LOG_TXT, state.get("txt_offset", 0))
    proximity_lines, proximity_offset = _read_new_lines(
        LOG_PROXIMITY_TXT,
        state.get("proximity_offset", 0),
    )

    events = []
    events.extend(_build_event_docs(device_id, "icso_log", txt_lines))
    events.extend(_build_event_docs(device_id, "icso_proximity", proximity_lines))

    if events:
        events_payload = {
            "device_id": device_id,
            "sent_at": _utc_now_iso(),
            "events": events,
        }
        events_response = requests.post(
            events_url,
            headers=headers,
            json=events_payload,
            timeout=timeout_sec,
        )
        events_response.raise_for_status()
        state["txt_offset"] = txt_offset
        state["proximity_offset"] = proximity_offset
        state["last_events_sync_at"] = _utc_now_iso()

    state["last_error"] = ""
    _save_sync_state(state)
    return {
        "snapshot_synced": True,
        "events_sent": len(events),
        "device_id": device_id,
    }


def _sync_worker(force_snapshot):
    global _SYNC_THREAD, _SYNC_PENDING_FORCE_SNAPSHOT
    pending_force = force_snapshot
    while True:
        try:
            sync_icso_to_backend(force_snapshot=pending_force)
        except Exception as exc:
            state = _load_sync_state()
            state["last_error"] = str(exc)
            _save_sync_state(state)

        with _SYNC_LOCK:
            if _SYNC_PENDING_FORCE_SNAPSHOT:
                pending_force = True
                _SYNC_PENDING_FORCE_SNAPSHOT = False
                continue
            _SYNC_THREAD = None
            break


def schedule_icso_sync(force_snapshot=False):
    global _SYNC_THREAD, _SYNC_PENDING_FORCE_SNAPSHOT
    with _SYNC_LOCK:
        if force_snapshot:
            _SYNC_PENDING_FORCE_SNAPSHOT = True
        if _SYNC_THREAD and _SYNC_THREAD.is_alive():
            return False
        force_for_thread = force_snapshot or _SYNC_PENDING_FORCE_SNAPSHOT
        _SYNC_PENDING_FORCE_SNAPSHOT = False
        _SYNC_THREAD = threading.Thread(
            target=_sync_worker,
            args=(force_for_thread,),
            daemon=True,
        )
        _SYNC_THREAD.start()
        return True
