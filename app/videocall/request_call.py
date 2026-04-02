"""HTTP utilities for outbound video-call request notifications.

This module encapsulates the API call used to notify remote contacts that a
call has been requested from the device UI.
"""

import os
from typing import Optional

import requests
from app_config import AppConfig
from config_store import load_section


_cfg = AppConfig()
_services_cfg = load_section("services", {})
DEFAULT_API_KEY = (_services_cfg.get("notify_api_key", "test_jules") or "").strip()
DEFAULT_FROM_DEVICE = _cfg.get_device_id()
DEFAULT_PIZARRA_NOTIFY_URL = _services_cfg.get(
    "pizarra_notify_url",
    "http://portal.co-bien.eu/pizarra/api/notify/",
)

def send_pizarra_notification(
    to_user: str,
    api_key: str = DEFAULT_API_KEY,
    message: str = "Call now?",
    from_device: str = DEFAULT_FROM_DEVICE,
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
    url = DEFAULT_PIZARRA_NOTIFY_URL

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
        r = requests.post(url, json=data, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text)
        return r
    except Exception as e:
        print("Erreur en envoyant la notification :", e)
        return None
