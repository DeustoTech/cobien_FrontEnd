import json
import os
import subprocess
import threading
from datetime import datetime

import requests

from config_store import load_section
from hardware_inventory import get_heartbeat_hardware_payload

_VERSION_FILE = os.path.join(os.path.dirname(__file__), "VERSION")


def _read_software_version():
    try:
        with open(_VERSION_FILE) as f:
            return f.read().strip()
    except Exception:
        return ""


def _load_runtime_config():
    services_cfg = load_section("services", {}) or {}
    settings_cfg = load_section("settings", {}) or {}
    
    url = (services_cfg.get("device_heartbeat_url", "") or "").strip()
    if not url:
        backend_base = (services_cfg.get("backend_base_url", "") or os.getenv("COBIEN_BACKEND_BASE_URL", "https://portal.co-bien.eu")).rstrip('/')
        url = f"{backend_base}/pizarra/api/devices/heartbeat/"
        
    return {
        "url": url,
        "api_key": (services_cfg.get("notify_api_key", "") or "").strip(),
        "device_id": (settings_cfg.get("device_id", "") or "").strip(),
        "timeout": float(services_cfg.get("http_timeout_sec", 8) or 8),
    }


def _check_mosquitto() -> str:
    """ok = process running + TCP port accepts; warn = process up but port closed; error = not running."""
    try:
        running = subprocess.run(
            ["pgrep", "-x", "mosquitto"], capture_output=True, check=False, timeout=3
        ).returncode == 0
    except Exception:
        return "unknown"
    if not running:
        return "error"
    try:
        import socket
        s = socket.create_connection(("localhost", 1883), timeout=2)
        s.close()
        return "ok"
    except Exception:
        return "warn"


def _check_bridge() -> str:
    """ok = process running + broker reachable; warn = process up but broker unreachable; error = not running.

    The bridge process is kept alive across supervision loop restarts, so its
    stdout pipe to the log awk process is broken after the first run — the log
    only reflects the initial connection event, not the current state. Instead
    of parsing stale log entries, we check liveness via: process exists AND
    broker accepts a TCP connection on :1883.
    """
    try:
        running = subprocess.run(
            ["pgrep", "-f", "cobien_bridge"], capture_output=True, check=False, timeout=3
        ).returncode == 0
    except Exception:
        return "unknown"
    if not running:
        return "error"
    # Process is alive — verify broker reachability as proxy for connectivity
    try:
        import socket
        s = socket.create_connection(("localhost", 1883), timeout=2)
        s.close()
        return "ok"
    except Exception:
        return "warn"


def _check_can() -> str:
    """ok = up + has packets; warn = up but 0 packets; error = down or absent."""
    try:
        with open("/sys/class/net/can0/operstate") as f:
            if f.read().strip() != "up":
                return "error"
    except Exception:
        return "error"
    try:
        rx = int(open("/sys/class/net/can0/statistics/rx_packets").read().strip())
        tx = int(open("/sys/class/net/can0/statistics/tx_packets").read().strip())
        return "ok" if (rx + tx) > 0 else "warn"
    except Exception:
        return "warn"


def _get_services_status():
    return {
        "app": "ok",
        "mosquitto": _check_mosquitto(),
        "mqtt_can_bridge": _check_bridge(),
        "can_interface": _check_can(),
        "checked_at": datetime.utcnow().isoformat() + "Z",
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
        "software_version": _read_software_version(),
    }
    hardware_payload = get_heartbeat_hardware_payload()
    if hardware_payload:
        payload.update(hardware_payload)
        # Extract a compact CAN status summary (if available) to include in every heartbeat
        try:
            # inventory shape: { 'hardware_inventory': { ... 'can': { ... } }, 'hardware_summary': ... }
            inv = hardware_payload.get("hardware_inventory") or {}
            can_info = inv.get("can") or hardware_payload.get("can") or {}
            if can_info:
                payload["can_status"] = {
                    "present": bool(can_info.get("present")),
                    "operstate": str(can_info.get("operstate") or ""),
                    "carrier": str(can_info.get("carrier") or ""),
                    "rx_packets": int(can_info.get("rx_packets") or 0),
                    "tx_packets": int(can_info.get("tx_packets") or 0),
                    "rx_errors": int(can_info.get("rx_errors") or 0),
                    "tx_errors": int(can_info.get("tx_errors") or 0),
                }
        except Exception:
            # best-effort only; do not break heartbeat on parsing errors
            pass
    payload["services_status"] = _get_services_status()
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)

    headers = {
        "X-API-KEY": cfg["api_key"],
        "Content-Type": "application/json",
    }

    try:
        # Debug log for remote support
        print(f"[HEARTBEAT] Sending payload to {cfg['url']}: {json.dumps(payload, ensure_ascii=False)}")
        
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
