# board/loadBoard.py
import os
from typing import List, Dict, Optional
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
import gridfs
from PIL import Image, ExifTags

# Importa el cliente que ya usas en eventos
from events.loadEvents import get_mongo_client

# === Configuración ===
DB_NAME = "LabasAppDB"
BUCKET = "pizarra_fs"  # colecciones pizarra_fs.files / pizarra_fs.chunks
CACHE_DIR = os.path.join(os.path.dirname(__file__), "board_cache")

# Asegurar que existe un directorio cache local (si no, usar temporal)
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
        
        # Vérifier si l'image a des données EXIF
        if not hasattr(img, '_getexif') or img._getexif() is None:
            return
        
        exif = img._getexif()
        if not exif:
            return
        
        # Trouver la clé "Orientation"
        orientation_key = None
        for tag, value in ExifTags.TAGS.items():
            if value == 'Orientation':
                orientation_key = tag
                break
        
        if orientation_key is None or orientation_key not in exif:
            return
        
        orientation = exif[orientation_key]
        
        # Appliquer la rotation selon orientation
        rotations = {
            3: 180,  # Upside down
            6: 270,  # Rotated 90° CCW
            8: 90,   # Rotated 90° CW
        }
        
        if orientation in rotations:
            angle = rotations[orientation]
            print(f"[BOARD] 🔄 Rotation image: {angle}° (EXIF orientation={orientation})")
            
            # Pivoter l'image
            img = img.rotate(angle, expand=True)
            
            # Sauvegarder en écrasant l'original
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
                    "author": author,
                    "text": text,
                    "image": img_path,
                    "created_at": created,
                }
            )

        print(f"[BOARD] Mensajes descargados: {count}")
        cl.close()

    except Exception as e:
        print(f"[BOARD] Error al consultar Mongo: {e}")

    return items
