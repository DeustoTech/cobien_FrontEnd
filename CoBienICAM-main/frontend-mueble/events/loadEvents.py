import os
import json
import math
from datetime import datetime

from events.event_bus import event_bus

from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import ObjectId

from app_config import AppConfig

# ------------------------
# CONFIGURACIÓN
# ------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOCAL_FILE = os.path.join(BASE_DIR, "events", "eventos_local.json")
_cfg = AppConfig()
DEVICE_NAME = _cfg.get_device_id()
LOCATION_NAME = _cfg.get_device_location()
print(f"[LOADEVENTS] device={DEVICE_NAME}, location={LOCATION_NAME}")

AUDIENCE_COLORS = {
    "all": "#1E90FF",     # Azul (públicos)
    "device": "#FF3B30"   # Rojo (personales)
}

# ------------------------
# CONEXIÓN A MONGODB
# ------------------------
def get_mongo_client():
    uri = os.getenv(
        "MONGO_URI",
        "mongodb+srv://usuarioCoBien:passwordCoBien@clustercobienevents."
        "j8ev5.mongodb.net/?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true",
    )
    return MongoClient(uri, serverSelectionTimeoutMS=3000)  # corta si no conecta en 3s

# ------------------------
# UTILIDADES
# ------------------------
def _normalize_audience(value):
    """Normaliza el campo 'audience'."""
    if not value:
        return "all"
    v = str(value).strip().lower()
    return "device" if v == "device" else "all"

def _audience_color(audience):
    return AUDIENCE_COLORS.get(audience, AUDIENCE_COLORS["all"])

def _safe_str(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, float) and math.isnan(value):
        return fallback
    return str(value)

def _formatea_fecha(fecha_raw):
    """Convierte datetime o str en formato dd-mm-YYYY."""
    try:
        if isinstance(fecha_raw, datetime):
            return fecha_raw.strftime("%d-%m-%Y")
        if isinstance(fecha_raw, str):
            return fecha_raw
    except:
        pass
    return ""

def limpiar_evento(evento):
    """Limpia valores NaN o None de un evento."""
    evento_limpio = {}
    for key, value in evento.items():
        if isinstance(value, float) and math.isnan(value):
            evento_limpio[key] = "Sin descripción disponible"
        elif value is None:
            evento_limpio[key] = "Sin descripción disponible"
        else:
            evento_limpio[key] = value
    return evento_limpio

def _match_location(loc: str) -> bool:
    """Compara location con LOCATION_NAME (match exacto, ignorando espacios)."""
    if loc is None:
        return False
    return loc.strip() == LOCATION_NAME

# ------------------------
# ARCHIVO LOCAL
# ------------------------
def guardar_eventos_localmente(eventos):
    eventos_limpios = [limpiar_evento(e) for e in eventos]
    os.makedirs(os.path.dirname(LOCAL_FILE), exist_ok=True)
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(eventos_limpios, f, ensure_ascii=False, indent=2)

def cargar_eventos_locales():
    """Carga los eventos desde el archivo local y aplica el filtro por location."""
    if not os.path.exists(LOCAL_FILE):
        print("No hay archivo local de eventos.")
        return []

    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        eventos = json.load(f)

    # Aplica filtro de ciudad
    eventos = [e for e in eventos if _match_location(e.get("location"))]

    print(f"{len(eventos)} eventos cargados desde archivo local (location='{LOCATION_NAME}').")
    return eventos

# ------------------------
# MONGO: FETCH
# ------------------------
def fetch_events_from_mongo(device_name=DEVICE_NAME):
    """
    Carga SOLO eventos con location == LOCATION_NAME:
      - Públicos (audience='all', location=LOCATION_NAME)
      - Personales del dispositivo indicado (audience='device', target_device=device_name, location=LOCATION_NAME)
    Los marca con colores (azul=publico, rojo=personal) e incluye 'id' para borrar.
    """
    try:
        client = get_mongo_client()
        client.server_info()

        db = client["LabasAppDB"]
        collection = db["eventos"]

        # Filtro por ciudad en ambos casos
        query = {
            "$or": [
                {"audience": "all", "location": LOCATION_NAME},
                {"audience": "device", "target_device": device_name, "location": LOCATION_NAME}
            ]
        }

        eventos_raw = list(collection.find(query))
        eventos = []
        print(f"{len(eventos_raw)} eventos cargados desde MongoDB (device='{device_name}', location='{LOCATION_NAME}').")

        for event in eventos_raw:
            fecha_str = _formatea_fecha(event.get("date") or event.get("fecha_inicio"))
            audience = _normalize_audience(event.get("audience"))
            color = _audience_color(audience)
            loc = _safe_str(event.get("location"), "Sin localización")

            # Seguridad extra por si algún documento se cuela sin location exacta
            if not _match_location(loc):
                continue

            eventos.append({
                "id": str(event.get("_id") or ""),  # necesario para borrar
                "date": fecha_str,
                "title": _safe_str(event.get("title") or event.get("titulo"), "Sin título"),
                "description": _safe_str(event.get("description") or event.get("descripcion"), "Sin descripción"),
                "location": loc,
                "audience": audience,
                "color": color,
                "target_device": event.get("target_device", ""),
                "created_by": event.get("created_by", ""),
            })

        guardar_eventos_localmente(eventos)
        return eventos

    except Exception as e:
        print(f"No se pudo conectar a MongoDB: {e}")
        # Carga desde local con el mismo criterio de ciudad
        return cargar_eventos_locales()

# ------------------------
# MONGO: DELETE
# ------------------------
def delete_event_mongo(event_id: str) -> bool:
    """
    Elimina un documento por _id en Mongo. Devuelve True si se ha borrado.
    Si borra con éxito, refresca la caché local con un fetch.
    """
    if not event_id:
        return False
    try:
        client = get_mongo_client()
        db = client["LabasAppDB"]
        collection = db["eventos"]
        res = collection.delete_one({"_id": ObjectId(event_id)})
        ok = res.deleted_count == 1
        if ok:
            try:
                eventos = fetch_events_from_mongo(device_name=DEVICE_NAME)
                guardar_eventos_localmente(eventos)
                event_bus.notify_events_changed()
            except Exception as e:
                print(f"[WARN] No se pudo refrescar cache local tras borrar: {e}")
        return ok
    except Exception as e:
        print(f"[DELETE] Error borrando {event_id}: {e}")
        return False
    
# ------------------------
# MONGO: AÑADIR
# ------------------------
def add_personal_event_mongo(day_date, title, description, location=None, device_name=None):
    """
    Inserta un evento personal (audience='device') para 'device_name' en 'location' y fecha 'day_date' (datetime.date).
    Devuelve el string del _id insertado o None si falla.
    """
    try:
        client = get_mongo_client()
        db = client["LabasAppDB"]
        collection = db["eventos"]
        target_location = location or LOCATION_NAME
        target_device = device_name or DEVICE_NAME

        # Guardamos la fecha con el mismo formato que estás usando en la app
        fecha_str = day_date.strftime("%d-%m-%Y")

        doc = {
            "date": fecha_str,
            "title": str(title).strip() if title else "Sin título",
            "description": str(description).strip() if description else "Sin descripción",
            "location": target_location,
            "audience": "device",
            "target_device": target_device,
            "color": AUDIENCE_COLORS["device"],
        }
        res = collection.insert_one(doc)
        try:
            eventos = fetch_events_from_mongo(device_name=target_device)
            guardar_eventos_localmente(eventos)
        except Exception as cache_error:
            print(f"[MONGO] No se pudo refrescar la caché local tras insertar: {cache_error}")
        event_bus.notify_events_changed()
        return str(res.inserted_id)
    except Exception as e:
        print(f"[MONGO] Error insertando evento personal: {e}")
        return None


# ------------------------
# API PARA LA APP
# ------------------------
def get_events(device_name=DEVICE_NAME):
    """Punto de entrada único para la app."""
    return fetch_events_from_mongo(device_name=device_name)

# ------------------------
# TEST MANUAL
# ------------------------
if __name__ == "__main__":
    eventos = get_events()
    print(f"Se han obtenido {len(eventos)} eventos (location='{LOCATION_NAME}').")
    for e in eventos:
        print(f"- {e['date']} | {e['title']} | {e['audience']} | {e['location']} ({e['color']})  id={e.get('id','')}")
