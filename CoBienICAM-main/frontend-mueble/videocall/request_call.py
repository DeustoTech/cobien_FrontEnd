import os
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
    from_device: str = DEFAULT_FROM_DEVICE
):
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
