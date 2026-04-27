"""Board data access and cache management utilities.

This module implements the board retrieval pipeline used by the UI:

1. Fetch messages from the backend REST API.
2. If API retrieval fails, fallback to MongoDB + GridFS.
3. If MongoDB retrieval fails, fallback to the local on-disk cache.

It also normalizes payload fields, caches images locally, and applies EXIF-based
orientation correction for downloaded images.
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from bson import ObjectId
import gridfs
import requests
from PIL import Image, ExifTags

# Import the client used in events
from events.loadEvents import get_mongo_client
from app_config import BACKEND_BASE_URL as _BACKEND_BASE_URL_DEFAULT
from config_store import load_section


def _get_backend_base_url() -> str:
    """Return the current backend base URL, reading fresh from config on each call.

    Priority: services.backend_base_url (config.local.json)
    → COBIEN_BACKEND_BASE_URL env var
    → module-level default (https://portal.co-bien.eu).
    """
    services_cfg = load_section("services", {})
    url = (services_cfg.get("backend_base_url") or "").strip()
    return url if url else _BACKEND_BASE_URL_DEFAULT

# === Configuration ===
DB_NAME = "LabasAppDB"
BUCKET = "pizarra_fs"  # GridFS collections: pizarra_fs.files / pizarra_fs.chunks
CACHE_DIR = os.path.join(os.getenv("COBIEN_CACHE_DIR") or os.path.dirname(__file__), "board_cache")
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "board_items.json")

# Ensure a local cache directory exists (if not writable, use a temp dir)
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except Exception as e:
    import tempfile
    CACHE_DIR = os.path.join(tempfile.gettempdir(), "board_cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"[BOARD] CACHE_DIR not writable, using temp directory: {CACHE_DIR}")


def _cache_path(file_id: ObjectId, filename: Optional[str]) -> str:
    """Build the local cache path for a board image.

    Args:
        file_id: GridFS file identifier.
        filename: Original file name, used only to infer extension.

    Returns:
        Absolute path to the local cached image/binary file.

    Examples:
        >>> # _cache_path(ObjectId("..."), "photo.jpg")
        >>> # '/.../board_cache/<object_id>.jpg'
    """
    ext = ""
    if filename and "." in filename:
        ext = "." + filename.split(".")[-1].lower()
        if len(ext) > 6:
            ext = ""
    return os.path.join(CACHE_DIR, f"{str(file_id)}{ext or '.bin'}")

def _fix_image_orientation(image_path: str) -> None:
    """
    Correct an image orientation using EXIF metadata.

    The input file is modified in place.

    Args:
        image_path: Path to the image file.

    Raises:
        No exception is propagated. Any processing error is logged and ignored.

    Examples:
        >>> _fix_image_orientation("/tmp/board_cache/abc123.jpg")
    """
    try:
        img = Image.open(image_path)
        
        # Check if the image has EXIF data
        if not hasattr(img, '_getexif') or img._getexif() is None:
            return
        
        exif = img._getexif()
        if not exif:
            return
        
        # Find the "Orientation" key
        orientation_key = None
        for tag, value in ExifTags.TAGS.items():
            if value == 'Orientation':
                orientation_key = tag
                break
        
        if orientation_key is None or orientation_key not in exif:
            return
        
        orientation = exif[orientation_key]
        
        # Apply rotation according to orientation
        rotations = {
            3: 180,  # Upside down
            6: 270,  # Rotated 90° CCW
            8: 90,   # Rotated 90° CW
        }
        
        if orientation in rotations:
            angle = rotations[orientation]
            print(f"[BOARD] 🔄 Rotation image: {angle}° (EXIF orientation={orientation})")
            
            # Rotate the image
            img = img.rotate(angle, expand=True)
            
            # Save by overwriting the original
            img.save(image_path, quality=95, optimize=True)
            
            print(f"[BOARD] ✅ Image orientation corrected: {image_path}")
    
    except Exception as e:
        print(f"[BOARD] ⚠️ Failed to correct image orientation: {e}")

def _fetch_image_to_cache(db: Any, file_id: ObjectId) -> Optional[str]:
    """Download an image from GridFS and persist it in the local cache.

    Args:
        db: Active MongoDB database handle.
        file_id: GridFS object identifier.

    Returns:
        Local absolute file path if successful, otherwise ``None``.

    Raises:
        No exception is propagated. Any retrieval error is logged and ignored.

    Examples:
        >>> # path = _fetch_image_to_cache(db, ObjectId("..."))
        >>> # if path: print(path)
    """
    try:
        fs = gridfs.GridFS(db, collection=BUCKET)
        f = fs.get(file_id)
        target = _cache_path(file_id, getattr(f, "filename", None))
        
        if not os.path.exists(target):
            with open(target, "wb") as out:
                out.write(f.read())
            
            _fix_image_orientation(target)
        
        return target
    
    except Exception as e:
        print(f"[BOARD][GridFS] Could not read {file_id}: {e}")
        return None


def _serialize_board_items(items: List[Dict]) -> List[Dict]:
    """Serialize board items into JSON-friendly dictionaries.

    Args:
        items: Raw board items where ``created_at`` may be ``datetime``.

    Returns:
        A list of dictionaries with ISO-8601 strings for ``created_at``.

    Examples:
        >>> _serialize_board_items([{"id": "1", "created_at": datetime.utcnow()}])
    """
    serialized = []
    for item in items:
        created_at = item.get("created_at")
        serialized.append(
            {
                "id": item.get("id", ""),
                "author": item.get("author", "—"),
                "text": item.get("text", ""),
                "image": item.get("image", ""),
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else "",
            }
        )
    return serialized


def _save_board_cache(items: List[Dict]) -> None:
    """Persist normalized board items to the local cache index file.

    The write is performed atomically through a temporary file and ``os.replace``.

    Args:
        items: Board items to store.

    Raises:
        No exception is propagated. Any write error is logged and ignored.

    Examples:
        >>> _save_board_cache([{"id": "a1", "author": "Alice", "text": "Hi"}])
    """
    try:
        payload = {
            "items": _serialize_board_items(items),
            "saved_at": datetime.utcnow().isoformat(),
        }
        tmp_path = CACHE_INDEX_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CACHE_INDEX_FILE)
        print(f"[BOARD] 💾 Cache saved at {CACHE_INDEX_FILE}")
    except Exception as e:
        print(f"[BOARD] ⚠️ Could not save local cache: {e}")


def _load_board_cache() -> List[Dict]:
    """Load board items from the local cache index file.

    Returns:
        A list of normalized board item dictionaries. Returns an empty list when
        no cache exists or when cache parsing fails.

    Raises:
        No exception is propagated. Any read/parse error is logged and ignored.

    Examples:
        >>> cached_items = _load_board_cache()
    """
    if not os.path.exists(CACHE_INDEX_FILE):
        return []

    try:
        with open(CACHE_INDEX_FILE, "r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)

        items = []
        for raw in payload.get("items", []):
            created_at = raw.get("created_at")
            if created_at:
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    created_at = None
            else:
                created_at = None

            image_path = raw.get("image", "") or ""
            if image_path and not os.path.exists(image_path):
                image_path = ""

            items.append(
                {
                    "id": raw.get("id", ""),
                    "author": raw.get("author", "—"),
                    "text": raw.get("text", ""),
                    "image": image_path,
                    "created_at": created_at,
                }
            )

        print(f"[BOARD] 📦 {len(items)} messages loaded from local cache")
        return items
    except Exception as e:
        print(f"[BOARD] ⚠️ Could not read local cache: {e}")
        return []


def _fetch_image_from_url(image_url: str, item_id: str) -> Optional[str]:
    """Download and cache an image from a remote URL.

    Args:
        image_url: Remote image URL.
        item_id: Stable message identifier used in cache filename.

    Returns:
        Local cached image path, or ``None`` when download/cache fails.

    Raises:
        No exception is propagated. Any network or file error is logged.

    Examples:
        >>> path = _fetch_image_from_url("https://example.com/a.jpg", "msg-1")
    """
    if not image_url:
        return None
    try:
        ext = os.path.splitext(image_url.split("?", 1)[0])[1].lower()
        if not ext or len(ext) > 6:
            ext = ".bin"
        target = os.path.join(CACHE_DIR, f"api_{item_id}{ext}")
        if not os.path.exists(target):
            services_cfg = load_section("services", {})
            headers = {}
            api_key = (services_cfg.get("notify_api_key", "") or "").strip()
            if api_key:
                headers["X-API-KEY"] = api_key
            response = requests.get(image_url, headers=headers, timeout=8)
            response.raise_for_status()
            with open(target, "wb") as out:
                out.write(response.content)
            _fix_image_orientation(target)
        return target
    except Exception as e:
        print(f"[BOARD][API] Could not cache image {image_url}: {e}")
        return None


def _normalize_api_items(messages: List[Dict]) -> List[Dict]:
    """Normalize API message payloads to the board item schema.

    Args:
        messages: Raw API payload entries.

    Returns:
        A list of normalized board dictionaries with keys:
        ``id``, ``author``, ``text``, ``image``, ``created_at``.

    Examples:
        >>> items = _normalize_api_items([{"id": "1", "author": "Ana"}])
    """
    items = []
    for raw in messages:
        created = raw.get("created_at")
        if created:
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                created = None
        else:
            created = None

        item_id = raw.get("id", "message")
        image_path = _fetch_image_from_url(raw.get("image", "") or raw.get("image_url", ""), item_id) or ""
        avatar_path = _fetch_image_from_url(raw.get("author_avatar_url", ""), f"{item_id}_avatar") or ""
        items.append(
            {
                "id": raw.get("id", ""),
                "author": raw.get("author_name") or raw.get("author", "—"),
                "text": raw.get("text", ""),
                "image": image_path,
                "author_avatar": avatar_path,
                "created_at": created,
                "created_at_human": raw.get("created_at_human", ""),
                "read_by": [
                    entry.get("device_id", "")
                    for entry in (raw.get("read_by") or [])
                    if isinstance(entry, dict) and entry.get("device_id")
                ],
                "quick_replies": list(raw.get("quick_replies") or []),
                "quick_reply_selected": raw.get("quick_reply_selected"),
            }
        )
    return items


def fetch_board_items_from_api(recipient_key: str, limit: int = 50) -> List[Dict]:
    """Fetch board messages from the backend REST API.

    Args:
        recipient_key: Device identifier used as message recipient filter.
        limit: Maximum number of messages to return.

    Returns:
        A list of normalized board items.

    Raises:
        requests.RequestException: If the HTTP request fails or returns an error
            status code.
        ValueError: If the backend returns an invalid JSON payload.

    Examples:
        >>> items = fetch_board_items_from_api("CoBien1", limit=20)
    """
    services_cfg = load_section("services", {})
    url = services_cfg.get("pizarra_messages_url")
    if not url:
        url = f"{_get_backend_base_url().rstrip('/')}/pizarra/api/messages/"
    headers = {}
    api_key = (services_cfg.get("notify_api_key", "") or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key

    response = requests.get(
        url,
        params={"recipient": recipient_key},
        headers=headers,
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    items = _normalize_api_items(payload.get("messages", [])[:limit])
    if items:
        _save_board_cache(items)
    print(f"[BOARD][API] Downloaded messages: {len(items)}")
    return items


def fetch_board_items_from_mongo(recipient_key: str = "CoBien1", limit: int = 50) -> List[Dict]:
    """Fetch board messages with resilient source fallback.

    This method first attempts API retrieval, then falls back to MongoDB/GridFS,
    and finally to local cache if MongoDB is unavailable.

    Args:
        recipient_key: Device identifier used as recipient filter.
        limit: Maximum number of messages to return.

    Returns:
        A list of normalized board items with the keys:
        ``id``, ``author``, ``text``, ``image``, ``created_at``.

    Raises:
        No exception is propagated to callers. Internal failures are logged and
        degraded to the next fallback source.

    Examples:
        >>> items = fetch_board_items_from_mongo("CoBien2", limit=50)
    """
    try:
        return fetch_board_items_from_api(recipient_key=recipient_key, limit=limit)
    except Exception as e:
        print(f"[BOARD][API] Falling back to Mongo/cache: {e}")

    items: List[Dict] = []
    try:
        cl = get_mongo_client()
        db = cl[DB_NAME]
        col = db["pizarra_messages"]

        cursor = (
            col.find(
                {"recipient_key": recipient_key},
                projection={"author": 1, "content": 1, "image_file_id": 1, "created_at": 1},
            )
            .sort([("created_at", -1), ("_id", -1)])
            .limit(int(limit))
        )

        count = 0
        for doc in cursor:
            count += 1
            author = doc.get("author", "—")
            text = doc.get("content", "")
            created = doc.get("created_at")

            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    created = None

            img_path = ""
            file_id = doc.get("image_file_id")
            if file_id:
                try:
                    if not isinstance(file_id, ObjectId):
                        file_id = ObjectId(str(file_id))
                    cached = _fetch_image_to_cache(db, file_id)
                    if cached:
                        img_path = cached
                except Exception as e:
                    print(f"[BOARD] Invalid image_file_id {file_id}: {e}")

            items.append(
                {
                    "id": str(doc.get("_id", "")),
                    "author": author,
                    "text": text,
                    "image": img_path,
                    "created_at": created,
                }
            )

        print(f"[BOARD] Downloaded messages: {count}")
        _save_board_cache(items)
        cl.close()

    except Exception as e:
        print(f"[BOARD] Mongo query error: {e}")
        return _load_board_cache()

    return items


def delete_board_item(post_id: str, source: str = "device") -> bool:
    """Delete a board message through the backend API.

    Args:
        post_id: Unique backend message identifier.

    Returns:
        ``True`` if the backend confirms deletion, otherwise ``False``.

    Raises:
        requests.RequestException: If the delete request fails at HTTP level.
        ValueError: If the backend response is not valid JSON.

    Examples:
        >>> ok = delete_board_item("67f1a30e...")
        >>> if ok:
        ...     print("Deleted")
    """
    if not post_id:
        return False

    services_cfg = load_section("services", {})
    url = services_cfg.get(
        "pizarra_delete_url_template",
        f"{_get_backend_base_url().rstrip('/')}/pizarra/api/messages/{{post_id}}/delete/",
    ).format(post_id=post_id)
    headers = {}
    api_key = (services_cfg.get("notify_api_key", "") or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key

    payload = {}
    if source:
        payload["source"] = source
        headers["X-DELETE-SOURCE"] = source

    response = requests.post(url, headers=headers, data=payload, timeout=8)
    response.raise_for_status()
    payload = response.json()
    return bool(payload.get("ok"))


def submit_quick_reply(post_id: str, device_id: str, reply_text: str) -> bool:
    if not post_id or not device_id or not reply_text:
        return False
    services_cfg = load_section("services", {})
    base = _get_backend_base_url().rstrip("/")
    url = f"{base}/pizarra/api/messages/{post_id}/reply/"
    headers = {"Content-Type": "application/json"}
    api_key = (services_cfg.get("notify_api_key", "") or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key
    try:
        response = requests.post(
            url,
            json={"device_id": device_id, "reply_text": reply_text},
            headers=headers,
            timeout=6,
        )
        response.raise_for_status()
        return bool(response.json().get("ok"))
    except Exception as exc:
        print(f"[BOARD] submit_quick_reply failed for {post_id}: {exc}")
        return False


def mark_message_read(post_id: str, device_id: str) -> bool:
    if not post_id or not device_id:
        return False
    services_cfg = load_section("services", {})
    base = _get_backend_base_url().rstrip("/")
    url = f"{base}/pizarra/api/messages/{post_id}/read/"
    headers = {"Content-Type": "application/json"}
    api_key = (services_cfg.get("notify_api_key", "") or "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key
    try:
        response = requests.post(url, json={"device_id": device_id}, headers=headers, timeout=6)
        response.raise_for_status()
        return bool(response.json().get("ok"))
    except Exception as exc:
        print(f"[BOARD] mark_message_read failed for {post_id}: {exc}")
        return False
