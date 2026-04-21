import threading
from datetime import datetime

import requests

from config_store import load_section
from hardware_inventory import get_heartbeat_hardware_payload


def _load_runtime_config():
    services_cfg = load_section("services", {}) or {}
    settings_cfg = load_section("settings", {}) or {}
    return {
        "url": (services_cfg.get("device_heartbeat_url", "") or "").strip(),
        "api_key": (services_cfg.get("notify_api_key", "") or "").strip(),
        "device_id": (settings_cfg.get("device_id", "") or "").strip(),
        "timeout": float(services_cfg.get("http_timeout_sec", 8) or 8),
    }


def send_device_heartbeat(screen_name="", extra_payload=None):
    cfg = _load_runtime_config()
    if not cfg["url"] or not cfg["device_id"] or not cfg["api_key"]:
        print("[HEARTBEAT] Missing configuration; heartbeat skipped")
        return

    payload = {
        "device_id": cfg["device_id"],
        "screen": str(screen_name or "").strip(),
        "sent_at": datetime.utcnow().isoformat() + "Z",
    }
    hardware_payload = get_heartbeat_hardware_payload()
    if hardware_payload:
        payload.update(hardware_payload)
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)

    headers = {
        "X-API-KEY": cfg["api_key"],
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(cfg["url"], json=payload, headers=headers, timeout=cfg["timeout"])
        response.raise_for_status()
        print(f"[HEARTBEAT] Sent for {cfg['device_id']} screen={payload.get('screen', '')}")
    except Exception as exc:
        print(f"[HEARTBEAT] Failed: {exc}")


def send_device_heartbeat_async(screen_name="", extra_payload=None):
    threading.Thread(
        target=send_device_heartbeat,
        kwargs={"screen_name": screen_name, "extra_payload": extra_payload or {}},
        daemon=True,
    ).start()
