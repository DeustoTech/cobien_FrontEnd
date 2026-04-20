import os
import json
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests

from app_config import BACKEND_BASE_URL
from config_store import load_section


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_DIR = os.path.join(BASE_DIR, "contacts")
CONTACTS_FILE = os.path.join(CONTACTS_DIR, "list_contacts.txt")
SUPPORTED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


def _normalize_name(name):
    base = "".join(
        c for c in unicodedata.normalize("NFD", str(name or ""))
        if unicodedata.category(c) != "Mn"
    )
    normalized = re.sub(r"[^a-z0-9]", "", base.lower())
    return normalized or "contact"


def _safe_write_text(path, content):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp_path, path)


def _build_headers():
    headers = {}
    services_cfg = load_section("services", {})
    api_key = (services_cfg.get("notify_api_key", "") or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key
    return headers


def _resolve_contacts_endpoint(device_id, payload):
    payload_url = (payload or {}).get("contacts_url")
    if payload_url:
        return payload_url, {}

    services_cfg = load_section("services", {})
    endpoint_tpl = services_cfg.get(
        "contacts_api_url",
        f"{BACKEND_BASE_URL.rstrip('/')}/pizarra/api/contacts/",
    ).strip()

    if "{device_id}" in endpoint_tpl:
        return endpoint_tpl.format(device_id=device_id), {}

    return endpoint_tpl, {"device_id": device_id}


def _extract_contacts(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        contacts = payload.get("contacts")
        if isinstance(contacts, list):
            return contacts
    return []


def _map_contact_entry(raw):
    if not isinstance(raw, dict):
        return None

    display_name = (
        raw.get("display_name")
        or raw.get("name")
        or raw.get("display")
        or raw.get("contact_name")
        or ""
    ).strip()
    user_name = (
        raw.get("user_name")
        or raw.get("username")
        or raw.get("user")
        or raw.get("contact_user")
        or ""
    ).strip()
    image_url = (
        raw.get("image_url")
        or raw.get("image")
        or raw.get("avatar")
        or raw.get("photo")
        or ""
    ).strip()

    if not display_name or not user_name:
        return None

    return {
        "display_name": display_name,
        "user_name": user_name,
        "image_url": image_url,
    }


def _guess_extension(image_url, response):
    path_ext = os.path.splitext(urlparse(image_url).path)[1].lower()
    if path_ext in SUPPORTED_IMAGE_EXTS:
        return path_ext

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "png" in content_type:
        return ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    if "bmp" in content_type:
        return ".bmp"
    return ".jpg"


def _cleanup_previous_images(base_name):
    for ext in SUPPORTED_IMAGE_EXTS:
        image_path = os.path.join(CONTACTS_DIR, f"{base_name}{ext}")
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass


def _download_contact_image(image_url, base_name):
    if not image_url:
        return False, ""

    if str(image_url).startswith("/"):
        services_cfg = load_section("services", {})
        backend_base_url = str(services_cfg.get("backend_base_url", "") or "").strip()
        if backend_base_url:
            image_url = urljoin(f"{backend_base_url.rstrip('/')}/", image_url.lstrip("/"))

    response = requests.get(
        image_url,
        headers=_build_headers(),
        timeout=10,
        stream=True,
    )
    response.raise_for_status()
    ext = _guess_extension(image_url, response)
    image_path = os.path.join(CONTACTS_DIR, f"{base_name}{ext}")
    tmp_path = f"{image_path}.tmp"

    with open(tmp_path, "wb") as fh:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)

    _cleanup_previous_images(base_name)
    os.replace(tmp_path, image_path)
    return True, image_url


def _write_contacts_file(contacts):
    lines = [f"{item['display_name']}={item['user_name']}" for item in contacts]
    content = ("\n".join(lines) + "\n") if lines else ""
    _safe_write_text(CONTACTS_FILE, content)


def _fetch_contacts_payload(device_id, payload):
    explicit = _extract_contacts(payload)
    if explicit:
        return explicit

    endpoint, params = _resolve_contacts_endpoint(device_id, payload)
    response = requests.get(
        endpoint,
        params=params,
        headers=_build_headers(),
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    contacts = _extract_contacts(body)
    if contacts:
        return contacts
    if isinstance(body, list):
        return body
    raise ValueError("Contacts payload has no valid 'contacts' list")


def sync_contacts_for_device(device_id, payload=None):
    os.makedirs(CONTACTS_DIR, exist_ok=True)
    raw_contacts = _fetch_contacts_payload(device_id=device_id, payload=payload or {})

    mapped = []
    for raw in raw_contacts:
        item = _map_contact_entry(raw)
        if item:
            mapped.append(item)

    if not mapped:
        raise ValueError("No valid contacts found after normalization")

    _write_contacts_file(mapped)

    downloaded_images = 0
    image_results = []
    for item in mapped:
        base_name = _normalize_name(item["display_name"])
        image_url = item["image_url"]
        if not image_url:
            image_results.append(
                {
                    "display_name": item["display_name"],
                    "status": "missing_url",
                    "image_url": "",
                }
            )
            continue
        try:
            downloaded, resolved_url = _download_contact_image(image_url, base_name)
            if downloaded:
                downloaded_images += 1
                image_results.append(
                    {
                        "display_name": item["display_name"],
                        "status": "downloaded",
                        "image_url": resolved_url,
                    }
                )
        except Exception as exc:
            print(f"[CONTACTS_SYNC] Image download failed for '{item['display_name']}': {exc}")
            image_results.append(
                {
                    "display_name": item["display_name"],
                    "status": "failed",
                    "image_url": image_url,
                    "error": str(exc),
                }
            )

    return {
        "count": len(mapped),
        "images_downloaded": downloaded_images,
        "contacts_file": CONTACTS_FILE,
        "image_results": image_results,
    }
