"""HTTP utilities for outbound video-call request notifications.

This module encapsulates the API call used to notify remote contacts that a
call has been requested from the device UI.
"""

from typing import Optional

import requests
from config_store import load_section


DEFAULT_PIZARRA_NOTIFY_URL = "http://portal.co-bien.eu/pizarra/api/notify/"
DEFAULT_HTTP_TIMEOUT_SEC = 8.0


def _load_runtime_notify_config():
    services_cfg = load_section("services", {}) or {}
    settings_cfg = load_section("settings", {}) or {}
    return {
        "api_key": (services_cfg.get("notify_api_key", "") or "").strip(),
        "from_device": (settings_cfg.get("device_id", "") or "").strip(),
        "url": (
            services_cfg.get("pizarra_notify_url", DEFAULT_PIZARRA_NOTIFY_URL)
            or DEFAULT_PIZARRA_NOTIFY_URL
        ).strip(),
        "timeout": float(
            services_cfg.get("http_timeout_sec", DEFAULT_HTTP_TIMEOUT_SEC)
            or DEFAULT_HTTP_TIMEOUT_SEC
        ),
    }

def send_pizarra_notification(
    to_user: str,
    message: str = "Call now?",
) -> Optional[requests.Response]:
    """Send call-ready notification to remote pizarra backend.

    Args:
        to_user (str): Target contact identifier.
        api_key (str): API key used in ``X-API-KEY`` header.
        message (str): Human-readable notification message.
        from_device (str): Device identifier sending the request.

    Returns:
        Optional[requests.Response]: HTTP response when request succeeds,
        otherwise ``None``.

    Raises:
        No exception is propagated. Network and request errors are handled and
        converted to ``None`` responses.

    Examples:
        >>> response = send_pizarra_notification("jules")
        >>> response is None or response.status_code in (200, 201, 202)
        True
    """
    runtime_cfg = _load_runtime_notify_config()
    api_key = runtime_cfg["api_key"]
    from_device = runtime_cfg["from_device"]
    url = runtime_cfg["url"]
    timeout = runtime_cfg["timeout"]

    if not to_user.strip():
        print("[VIDEOCALL] Missing to_user for outbound notification.")
        return None

    if not api_key:
        print("[VIDEOCALL] Missing notify_api_key; cannot send videocall notification.")
        return None

    data = {
        "to_user": to_user,
        "from_device": from_device,
        "kind": "call_ready",
        "message": message,
        "ttl_hours": 12
    }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, json=data, headers=headers, timeout=timeout)
        print("Status:", r.status_code)
        print("Response:", r.text)
        if not r.ok:
            print(f"[VIDEOCALL] Notification rejected by backend: HTTP {r.status_code}")
            return None
        return r
    except Exception as e:
        print("Erreur en envoyant la notification :", e)
        return None
