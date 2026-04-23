"""HTTP utilities for outbound video-call request notifications."""

from typing import Dict, Optional

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


def _build_result(ok: bool, code: str, detail: str = "", response: Optional[requests.Response] = None) -> Dict[str, object]:
    return {
        "ok": ok,
        "code": code,
        "detail": detail,
        "response": response,
    }

def send_pizarra_notification(
    to_user: str,
    message: str = "Call now?",
) -> Dict[str, object]:
    """Send call-ready notification to remote pizarra backend.

    Args:
        to_user (str): Target contact identifier.
        api_key (str): API key used in ``X-API-KEY`` header.
        message (str): Human-readable notification message.
        from_device (str): Device identifier sending the request.

    Returns:
        Dict[str, object]: Structured result with ``ok``, ``code``, ``detail``
        and optional ``response`` keys.

    Raises:
        No exception is propagated. Network and request errors are handled and
        converted to ``None`` responses.

    Examples:
        >>> response = send_pizarra_notification("jules")
        >>> response["ok"] in (True, False)
        True
    """
    runtime_cfg = _load_runtime_notify_config()
    api_key = runtime_cfg["api_key"]
    from_device = runtime_cfg["from_device"]
    url = runtime_cfg["url"]
    timeout = runtime_cfg["timeout"]

    if not to_user.strip():
        print("[VIDEOCALL] Missing to_user for outbound notification.")
        return _build_result(False, "VC-USER", "Contacto de destino no válido")

    if not api_key:
        print("[VIDEOCALL] Missing notify_api_key; cannot send videocall notification.")
        return _build_result(False, "VC-CONFIG", "Falta notify_api_key en la configuración")

    if not from_device:
        print("[VIDEOCALL] Missing device_id; cannot identify calling device.")
        return _build_result(False, "VC-DEVICE", "Falta device_id en la configuración")

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
            return _build_result(False, f"VC-{r.status_code}", f"Backend devolvió HTTP {r.status_code}", r)
        return _build_result(True, "VC-200", "Solicitud enviada correctamente", r)
    except requests.exceptions.Timeout as e:
        print("Error sending notification:", e)
        return _build_result(False, "VC-TIMEOUT", "Tiempo de espera agotado")
    except requests.exceptions.ConnectionError as e:
        print("Error sending notification:", e)
        return _build_result(False, "VC-NET", "No se pudo conectar con el servidor")
    except requests.exceptions.RequestException as e:
        print("Error sending notification:", e)
        return _build_result(False, "VC-REQ", str(e))
    except Exception as e:
        print("Error sending notification:", e)
        return _build_result(False, "VC-UNK", str(e))
