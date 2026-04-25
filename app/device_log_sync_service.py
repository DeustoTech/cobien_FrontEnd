import json
import os
import threading
from datetime import datetime, timedelta, timezone

import requests

from config_store import load_section


APP_DIR = os.path.dirname(__file__)
FRONTEND_ROOT = os.path.dirname(APP_DIR)
LOG_DIR = os.getenv("COBIEN_LOG_DIR") or os.path.join(FRONTEND_ROOT, "logs")
RUNTIME_STATE_DIR = os.getenv("COBIEN_RUNTIME_STATE_DIR") or os.path.join(APP_DIR, "runtime_state")
SYNC_STATE_PATH = os.path.join(RUNTIME_STATE_DIR, "device_log_sync_state.json")

DEFAULT_SYNC_STATE = {
    "last_sync_at": "",
    "last_error": "",
    "files": {},
}

SYNC_INTERVAL_SEC = 300
MAX_BYTES_PER_FILE = 120_000
MAX_LINES_PER_FILE = 1_500

LOG_SPECS = {
    "app": {"prefix": "cobien-app", "label": "Application"},
    "can_bus": {"prefix": "can-bus", "label": "CAN Bus"},
    "mqtt_can_bridge": {"prefix": "mqtt-can-bridge", "label": "MQTT-CAN Bridge"},
}

_SYNC_LOCK = threading.Lock()
_SYNC_THREAD = None
_SYNC_PENDING_FORCE = False


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
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def _load_sync_state():
    state = dict(DEFAULT_SYNC_STATE)
    state.update(_safe_read_json(SYNC_STATE_PATH, {}))
    files = state.get("files")
    state["files"] = files if isinstance(files, dict) else {}
    return state


def _save_sync_state(state):
    merged = dict(DEFAULT_SYNC_STATE)
    merged.update(state or {})
    if not isinstance(merged.get("files"), dict):
        merged["files"] = {}
    _safe_write_json(SYNC_STATE_PATH, merged)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _runtime_context():
    services = load_section("services", {}) or {}
    settings = load_section("settings", {}) or {}
    backend_base_url = str(services.get("backend_base_url", "") or "").strip().rstrip("/")
    logs_url = str(
        services.get("device_logs_ingest_url")
        or (f"{backend_base_url}/pizarra/api/device/logs/ingest/" if backend_base_url else "")
    ).strip()
    return {
        "device_id": str(settings.get("device_id", "") or "").strip(),
        "api_key": str(services.get("notify_api_key", "") or "").strip(),
        "logs_url": logs_url,
        "timeout_sec": float(services.get("http_timeout_sec", 8) or 8),
    }


def _build_headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    return headers


def _target_dates():
    today = datetime.now().date()
    return [today, today - timedelta(days=1)]


def _log_path(prefix, date_value):
    return os.path.join(LOG_DIR, f"{prefix}-{date_value.strftime('%Y%m%d')}.log")


def _tail_content(path, max_bytes=MAX_BYTES_PER_FILE, max_lines=MAX_LINES_PER_FILE):
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        file_size = fh.tell()
        start = max(0, file_size - max_bytes)
        fh.seek(start)
        raw = fh.read()

    if start > 0:
        newline_pos = raw.find(b"\n")
        if newline_pos >= 0:
            raw = raw[newline_pos + 1 :]

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = start > 0 or len(lines) > max_lines
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    content = "\n".join(lines).strip()
    return {
        "content": content,
        "line_count": len(lines),
        "byte_count": file_size,
        "truncated": truncated,
    }


def _fingerprint(path):
    stat = os.stat(path)
    return f"{int(stat.st_mtime)}:{stat.st_size}"


def _collect_log_payloads(force=False):
    state = _load_sync_state()
    previous_files = state.get("files", {})
    logs = []
    current_files = dict(previous_files)

    for log_type, spec in LOG_SPECS.items():
        prefix = spec["prefix"]
        for date_value in _target_dates():
            path = _log_path(prefix, date_value)
            file_key = f"{log_type}:{date_value.isoformat()}"
            if not os.path.exists(path):
                current_files.pop(file_key, None)
                continue

            fingerprint = _fingerprint(path)
            if not force and previous_files.get(file_key) == fingerprint:
                continue

            payload = _tail_content(path)
            logs.append(
                {
                    "log_type": log_type,
                    "log_date": date_value.isoformat(),
                    "filename": os.path.basename(path),
                    "content": payload["content"],
                    "line_count": payload["line_count"],
                    "byte_count": payload["byte_count"],
                    "truncated": payload["truncated"],
                    "sent_at": _utc_now_iso(),
                }
            )
            current_files[file_key] = fingerprint

    return logs, current_files, state


def sync_device_logs(force=False):
    context = _runtime_context()
    if not context["device_id"] or not context["api_key"] or not context["logs_url"]:
        print("[SUPPORT LOGS] Missing configuration; sync skipped")
        return {"ok": False, "reason": "missing_config"}

    logs, current_files, state = _collect_log_payloads(force=force)
    if not logs:
        return {"ok": True, "uploaded": 0, "skipped": True}

    response = requests.post(
        context["logs_url"],
        headers=_build_headers(context["api_key"]),
        json={
            "device_id": context["device_id"],
            "sent_at": _utc_now_iso(),
            "logs": logs,
        },
        timeout=context["timeout_sec"],
    )
    response.raise_for_status()

    state["files"] = current_files
    state["last_sync_at"] = _utc_now_iso()
    state["last_error"] = ""
    _save_sync_state(state)
    print(f"[SUPPORT LOGS] Synced {len(logs)} log snapshots")
    return {"ok": True, "uploaded": len(logs)}


def _sync_worker(force):
    global _SYNC_THREAD, _SYNC_PENDING_FORCE
    pending_force = force
    while True:
        try:
            sync_device_logs(force=pending_force)
        except Exception as exc:
            state = _load_sync_state()
            state["last_error"] = str(exc)
            _save_sync_state(state)
            print(f"[SUPPORT LOGS] Sync failed: {exc}")

        with _SYNC_LOCK:
            if _SYNC_PENDING_FORCE:
                pending_force = True
                _SYNC_PENDING_FORCE = False
                continue
            _SYNC_THREAD = None
            break


def schedule_device_log_sync(force=False):
    global _SYNC_THREAD, _SYNC_PENDING_FORCE
    state = _load_sync_state()
    last_sync = state.get("last_sync_at", "")
    if not force and last_sync:
        try:
            dt = datetime.fromisoformat(str(last_sync).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - dt).total_seconds() < SYNC_INTERVAL_SEC:
                return False
        except Exception:
            pass

    with _SYNC_LOCK:
        if force:
            _SYNC_PENDING_FORCE = True
        if _SYNC_THREAD and _SYNC_THREAD.is_alive():
            return False
        force_for_thread = force or _SYNC_PENDING_FORCE
        _SYNC_PENDING_FORCE = False
        _SYNC_THREAD = threading.Thread(
            target=_sync_worker,
            args=(force_for_thread,),
            daemon=True,
        )
        _SYNC_THREAD.start()
    return True
