# board/loadBoard.py
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from bson import ObjectId
import gridfs
import requests
from PIL import Image, ExifTags

# Import the client used in events
from events.loadEvents import get_mongo_client
from app_config import BACKEND_BASE_URL

# === Configuration ===
DB_NAME = "LabasAppDB"
BUCKET = "pizarra_fs"  # colecciones pizarra_fs.files / pizarra_fs.chunks
CACHE_DIR = os.path.join(os.path.dirname(__file__), "board_cache")
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "board_items.json")

# Ensure a local cache directory exists (if not writable, use a temp dir)
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except Exception as e:
    import tempfile
    CACHE_DIR = os.path.join(tempfile.gettempdir(), "board_cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"[BOARD] CACHE_DIR no escribible, usando temporal: {CACHE_DIR}")


def _cache_path(file_id: ObjectId, filename: Optional[str]) -> str:
    """Construye la ruta local donde cachear una imagen."""
    ext = ""
    if filename and "." in filename:
        ext = "." + filename.split(".")[-1].lower()
        if len(ext) > 6:
            ext = ""
    return os.path.join(CACHE_DIR, f"{str(file_id)}{ext or '.bin'}")

def _fix_image_orientation(image_path: str) -> None:
    """
    Corrige l'orientation d'une image selon ses métadonnées EXIF.
    Modifie le fichier directement.
    
    Args:
        image_path: Chemin vers l'image à corriger
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
            
            print(f"[BOARD] ✅ Image corrigée: {image_path}")
    
    except Exception as e:
        print(f"[BOARD] ⚠️ Erreur correction orientation: {e}")

def _fetch_image_to_cache(db, file_id: ObjectId) -> Optional[str]:
    """Descarga una imagen desde GridFS y la guarda en cache."""
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
        print(f"[BOARD][GridFS] No se pudo leer {file_id}: {e}")
        return None


def _serialize_board_items(items: List[Dict]) -> List[Dict]:
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
    try:
        payload = {
            "items": _serialize_board_items(items),
            "saved_at": datetime.utcnow().isoformat(),
        }
        tmp_path = CACHE_INDEX_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CACHE_INDEX_FILE)
        print(f"[BOARD] 💾 Cache guardada en {CACHE_INDEX_FILE}")
    except Exception as e:
        print(f"[BOARD] ⚠️ No se pudo guardar caché local: {e}")


def _load_board_cache() -> List[Dict]:
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

        print(f"[BOARD] 📦 {len(items)} mensajes cargados desde caché local")
        return items
    except Exception as e:
        print(f"[BOARD] ⚠️ No se pudo leer caché local: {e}")
        return []


def _fetch_image_from_url(image_url: str, item_id: str) -> Optional[str]:
    if not image_url:
        return None
    try:
        ext = os.path.splitext(image_url.split("?", 1)[0])[1].lower()
        if not ext or len(ext) > 6:
            ext = ".bin"
        target = os.path.join(CACHE_DIR, f"api_{item_id}{ext}")
        if not os.path.exists(target):
            response = requests.get(image_url, timeout=8)
            response.raise_for_status()
            with open(target, "wb") as out:
                out.write(response.content)
            _fix_image_orientation(target)
        return target
    except Exception as e:
        print(f"[BOARD][API] No se pudo cachear imagen {image_url}: {e}")
        return None


def _normalize_api_items(messages: List[Dict]) -> List[Dict]:
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
        image_path = _fetch_image_from_url(raw.get("image", ""), item_id) or ""
        items.append(
            {
                "id": raw.get("id", ""),
                "author": raw.get("author", "—"),
                "text": raw.get("text", ""),
                "image": image_path,
                "created_at": created,
            }
        )
    return items


def fetch_board_items_from_api(recipient_key: str, limit: int = 50) -> List[Dict]:
    url = os.getenv("COBIEN_PIZARRA_API_URL", f"{BACKEND_BASE_URL.rstrip('/')}/pizarra/api/messages/")
    headers = {}
    api_key = os.getenv("COBIEN_NOTIFY_API_KEY", "").strip()
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
    print(f"[BOARD][API] Mensajes descargados: {len(items)}")
    return items


def fetch_board_items_from_mongo(recipient_key: str = "CoBien1", limit: int = 50) -> List[Dict]:
    """
    Devuelve una lista de mensajes en formato:
    {
        'author': str,
        'text': str,
        'image': str (ruta local o ''),
        'created_at': datetime
    }
    """
    try:
        return fetch_board_items_from_api(recipient_key=recipient_key, limit=limit)
    except Exception as e:
        print(f"[BOARD][API] Fallback a Mongo/caché: {e}")

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
                    print(f"[BOARD] image_file_id inválido {file_id}: {e}")

            items.append(
                {
                    "id": str(doc.get("_id", "")),
                    "author": author,
                    "text": text,
                    "image": img_path,
                    "created_at": created,
                }
            )

        print(f"[BOARD] Mensajes descargados: {count}")
        _save_board_cache(items)
        cl.close()

    except Exception as e:
        print(f"[BOARD] Error al consultar Mongo: {e}")
        return _load_board_cache()

    return items


def delete_board_item(post_id: str) -> bool:
    if not post_id:
        return False

    url = os.getenv(
        "COBIEN_PIZARRA_DELETE_URL_TEMPLATE",
        f"{BACKEND_BASE_URL.rstrip('/')}/pizarra/api/messages/{{post_id}}/delete/",
    ).format(post_id=post_id)
    headers = {}
    api_key = os.getenv("COBIEN_NOTIFY_API_KEY", "").strip()
    if api_key:
        headers["X-API-KEY"] = api_key

    response = requests.post(url, headers=headers, timeout=8)
    response.raise_for_status()
    payload = response.json()
    return bool(payload.get("ok"))
