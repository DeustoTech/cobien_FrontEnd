"""Event data loading, persistence, and synchronization helpers.

This module centralizes event retrieval and mutation using a resilient strategy:

1. Primary source: MongoDB.
2. Fallback source: local JSON cache (`eventos_local.json`).

It applies device/location filtering, normalizes event payloads for UI
consumption, and broadcasts change notifications via `event_bus`.
"""

import os
import json
import math
import time
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from events.event_bus import event_bus

from pymongo import MongoClient
from bson import ObjectId

from app_config import AppConfig
from config_store import load_section

# ------------------------ CONFIGURATION ------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOCAL_FILE = os.path.join(os.getenv("COBIEN_DATA_DIR") or BASE_DIR, "events", "eventos_local.json")

# Cache for device event preferences (avoids a MongoDB round-trip on every load).
_PREFS_CACHE: Dict[str, Any] = {}
_PREFS_CACHE_EXPIRES: float = 0.0
_PREFS_CACHE_TTL: float = 300.0  # seconds

AUDIENCE_COLORS = {
    "all": "#1E90FF",     # Azul (públicos)
    "device": "#FF3B30"   # Rojo (personales)
}

def _runtime_cfg() -> AppConfig:
    return AppConfig()

def _current_device_name() -> str:
    return _runtime_cfg().get_device_id()

def _current_location_name() -> str:
    return _runtime_cfg().get_device_location()

def _normalize_location_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()

def get_mongo_client() -> MongoClient:
    """Build a MongoDB client using unified service configuration.

    Returns:
        MongoClient: Configured client instance with short connection timeout.

    Raises:
        RuntimeError: If `mongo_uri`/`MONGO_URI` is not configured.

    Examples:
        >>> client = get_mongo_client()
        >>> client.server_info()
    """
    services_cfg = load_section("services", {})
    uri = (services_cfg.get("mongo_uri", "") or os.getenv("MONGO_URI") or "").strip()
    if not uri:
        raise RuntimeError("MONGO_URI no configurado")
    return MongoClient(uri, serverSelectionTimeoutMS=3000)  # corta si no conecta en 3s

def _normalize_audience(value: Any) -> str:
    """Normalize event audience value.

    Args:
        value: Raw audience value from Mongo/local data.

    Returns:
        str: `"device"` or `"all"` (default).
    """
    if not value:
        return "all"
    v = str(value).strip().lower()
    return "device" if v == "device" else "all"

def _audience_color(audience: str) -> str:
    """Resolve UI color for an audience category.

    Args:
        audience: Normalized audience string.

    Returns:
        str: Hex color code used by the UI.
    """
    return AUDIENCE_COLORS.get(audience, AUDIENCE_COLORS["all"])

def _safe_str(value: Any, fallback: str) -> str:
    """Convert value to string while protecting against null-like values.

    Args:
        value: Raw value to normalize.
        fallback: Fallback value for `None`/`NaN`.

    Returns:
        str: Safe normalized string.
    """
    if value is None:
        return fallback
    if isinstance(value, float) and math.isnan(value):
        return fallback
    return str(value)

def _formatea_fecha(fecha_raw: Any) -> str:
    """Format raw date values to `dd-mm-YYYY` text.

    Args:
        fecha_raw: `datetime` or preformatted string date.

    Returns:
        str: Formatted date string or empty string when unsupported.
    """
    try:
        if isinstance(fecha_raw, datetime):
            return fecha_raw.strftime("%d-%m-%Y")
        if isinstance(fecha_raw, str):
            return fecha_raw
    except:
        pass
    return ""

def limpiar_evento(evento: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize event dictionary values.

    Replaces `None` and float `NaN` values with a descriptive placeholder.

    Args:
        evento: Raw event dictionary.

    Returns:
        Dict[str, Any]: Sanitized event dictionary.
    """
    evento_limpio: Dict[str, Any] = {}
    for key, value in evento.items():
        if isinstance(value, float) and math.isnan(value):
            evento_limpio[key] = "Sin descripción disponible"
        elif value is None:
            evento_limpio[key] = "Sin descripción disponible"
        else:
            evento_limpio[key] = value
    return evento_limpio

def _match_location(loc: Optional[str], location_name: Optional[str] = None) -> bool:
    """Check whether event location matches current configured location.

    Args:
        loc: Event location string.

    Returns:
        bool: `True` when location matches `LOCATION_NAME` after trimming.
    """
    if loc is None:
        return False
    target_location = location_name or _current_location_name()
    return _normalize_location_text(loc) == _normalize_location_text(target_location)


def _is_locationless(value: Optional[str]) -> bool:
    """Return True when an event location is missing or blank."""
    return not str(value or "").strip()


def _device_event_preferences(device_name: str, fallback_location: str) -> Dict[str, Any]:
    global _PREFS_CACHE_EXPIRES
    cache_key = f"{device_name}:{fallback_location}"
    now = time.time()
    if cache_key in _PREFS_CACHE and now < _PREFS_CACHE_EXPIRES:
        return _PREFS_CACHE[cache_key]

    scope = "all"
    regions: List[str] = []
    try:
        client = get_mongo_client()
        db = client["LabasAppDB"]
        doc = db["devices"].find_one(
            {"device_id": device_name},
            {"event_visibility_scope": 1, "event_regions": 1},
        ) or {}
        raw_scope = str(doc.get("event_visibility_scope") or "all").strip().lower()
        if raw_scope == "region":
            scope = "region"
        raw_regions = doc.get("event_regions") or []
        if isinstance(raw_regions, str):
            raw_regions = raw_regions.splitlines()
        for item in raw_regions:
            value = str(item or "").strip()
            if value:
                regions.append(value)
    except Exception:
        pass

    if scope == "region" and not regions and fallback_location:
        regions = [fallback_location]
    result: Dict[str, Any] = {"scope": scope, "regions": regions}
    _PREFS_CACHE[cache_key] = result
    _PREFS_CACHE_EXPIRES = now + _PREFS_CACHE_TTL
    return result


def _public_event_matches_preferences(raw_location: Optional[str], preferences: Dict[str, Any], fallback_location: str) -> bool:
    if _is_locationless(raw_location):
        return True

    scope = preferences.get("scope", "all")
    if scope != "region":
        return True

    allowed_regions = preferences.get("regions") or [fallback_location]
    normalized_allowed = {_normalize_location_text(item) for item in allowed_regions if str(item or "").strip()}
    return _normalize_location_text(raw_location) in normalized_allowed

def guardar_eventos_localmente(eventos: List[Dict[str, Any]]) -> None:
    """Persist sanitized event list in local JSON cache.

    Args:
        eventos: Event dictionaries to persist.

    Returns:
        None.
    """
    eventos_limpios = [limpiar_evento(e) for e in eventos]
    os.makedirs(os.path.dirname(LOCAL_FILE), exist_ok=True)
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(eventos_limpios, f, ensure_ascii=False, indent=2)

def cargar_eventos_locales(location_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load events from local cache and apply location filter.

    Returns:
        List[Dict[str, Any]]: Cached events for current location.

    Raises:
        json.JSONDecodeError: If local file exists but contains invalid JSON.
        OSError: If cache file cannot be read.
    """
    if not os.path.exists(LOCAL_FILE):
        print("No hay archivo local de eventos.")
        return []

    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        eventos = json.load(f)

    # Aplica filtro de ciudad
    target_location = location_name or _current_location_name()
    target_device = _current_device_name()
    # Use cached prefs; if not cached, default to "all" to avoid a MongoDB call
    # during the local-cache fallback path (when MongoDB is likely unreachable).
    cache_key = f"{target_device}:{target_location}"
    event_preferences = _PREFS_CACHE.get(cache_key, {"scope": "all", "regions": []})
    filtered_events: List[Dict[str, Any]] = []
    for event in eventos:
        audience = _normalize_audience(event.get("audience"))
        loc = event.get("location")
        if audience == "all" and _public_event_matches_preferences(loc, event_preferences, target_location):
            event = dict(event)
            if _is_locationless(loc):
                event["location"] = target_location
            filtered_events.append(event)
            continue
        if _match_location(loc, target_location):
            filtered_events.append(event)
            continue

    eventos = filtered_events

    print(f"{len(eventos)} eventos cargados desde archivo local (location='{target_location}').")
    return eventos


def _append_personal_event_local(
    day_date: Any,
    title: str,
    description: str,
    location: Optional[str] = None,
    device_name: Optional[str] = None,
) -> str:
    """Append a personal event directly to local cache as Mongo fallback.

    Args:
        day_date: Date-like object with `strftime`.
        title: Event title.
        description: Event description.
        location: Optional event location override.
        device_name: Optional target device override.

    Returns:
        str: Generated local event id (`local-...`).
    """
    target_location = location or _current_location_name()
    target_device = device_name or _current_device_name()
    fecha_str = day_date.strftime("%d-%m-%Y")
    local_id = f"local-{int(time.time() * 1000)}"

    local_events = cargar_eventos_locales(target_location) or []
    local_events.append({
        "id": local_id,
        "date": fecha_str,
        "title": str(title).strip() if title else "Sin título",
        "description": str(description).strip() if description else "Sin descripción",
        "location": target_location,
        "audience": "device",
        "target_device": target_device,
        "color": AUDIENCE_COLORS["device"],
        "created_by": "local_fallback",
    })
    guardar_eventos_localmente(local_events)
    event_bus.notify_events_changed()
    return local_id

def fetch_events_from_mongo(device_name: Optional[str] = None, location_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch events from MongoDB with location and device filtering.

    Included event subsets:
    - Public events (`audience='all'`) for current location.
    - Personal events (`audience='device'`) for current location and device.

    Args:
        device_name: Target device identifier for personal events.

    Returns:
        List[Dict[str, Any]]: Normalized events for UI consumption.

    Raises:
        No exception is propagated. On failure, local cache is returned.

    Examples:
        >>> events = fetch_events_from_mongo(device_name="CoBien1")
    """
    try:
        target_device = device_name or _current_device_name()
        target_location = location_name or _current_location_name()
        event_preferences = _device_event_preferences(target_device, target_location)
        client = get_mongo_client()

        db = client["LabasAppDB"]
        collection = db["eventos"]

        # Filtro por ciudad en ambos casos
        query = {
            "$or": [
                {
                    "$and": [
                        {
                            "$or": [
                                {"audience": "all"},
                                {"audience": {"$exists": False}},
                                {"audience": None},
                            ]
                        },
                        {
                            "$or": [
                                {"location": target_location},
                                {"location": {"$exists": False}},
                                {"location": ""},
                                {"location": None},
                            ]
                        },
                    ],
                },
                {
                    "audience": "device",
                    "location": target_location,
                    "$or": [
                        {"target_device": target_device},
                        {"target_devices": target_device},
                    ],
                },
            ]
        }

        eventos_raw = list(collection.find(query))
        eventos = []
        print(f"{len(eventos_raw)} eventos cargados desde MongoDB (device='{target_device}', location='{target_location}').")

        for event in eventos_raw:
            fecha_str = _formatea_fecha(event.get("date") or event.get("fecha_inicio"))
            audience = _normalize_audience(event.get("audience"))
            color = _audience_color(audience)
            raw_loc = event.get("location")
            loc = _safe_str(raw_loc, target_location if audience == "all" else "Sin localización")

            # Permite eventos generales sin localización explícita como fallback global.
            if audience == "all" and _is_locationless(raw_loc):
                loc = target_location
            elif audience == "all":
                if not _public_event_matches_preferences(raw_loc, event_preferences, target_location):
                    continue
            elif not _match_location(loc, target_location):
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
        return cargar_eventos_locales(location_name)

# ------------------------
# MONGO: DELETE
# ------------------------
def delete_event_mongo(event_id: str) -> bool:
    """Delete an event from MongoDB or local fallback cache.

    Args:
        event_id: Event identifier (`ObjectId` string or `local-*` id).

    Returns:
        bool: `True` when deletion succeeds, otherwise `False`.

    Raises:
        No exception is propagated. Errors are logged and `False` is returned.
    """
    if not event_id:
        return False
    if str(event_id).startswith("local-"):
        try:
            local_events = cargar_eventos_locales() or []
            new_events = [e for e in local_events if str(e.get("id") or "") != str(event_id)]
            if len(new_events) == len(local_events):
                return False
            guardar_eventos_localmente(new_events)
            event_bus.notify_events_changed()
            return True
        except Exception as e:
            print(f"[DELETE] Error borrando evento local {event_id}: {e}")
            return False
    try:
        client = get_mongo_client()
        db = client["LabasAppDB"]
        collection = db["eventos"]
        res = collection.delete_one({"_id": ObjectId(event_id)})
        ok = res.deleted_count == 1
        if ok:
            try:
                eventos = fetch_events_from_mongo(device_name=_current_device_name(), location_name=_current_location_name())
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
def add_personal_event_mongo(
    day_date: Any,
    title: str,
    description: str,
    location: Optional[str] = None,
    device_name: Optional[str] = None,
) -> Optional[str]:
    """Insert a personal event in MongoDB with local fallback on failure.

    Args:
        day_date: Date-like object with `strftime`.
        title: Event title.
        description: Event description.
        location: Optional location override.
        device_name: Optional target device override.

    Returns:
        Optional[str]: Inserted Mongo id string, fallback local id, or `None`.

    Raises:
        No exception is propagated. Failures are logged and fallback is attempted.
    """
    try:
        client = get_mongo_client()
        db = client["LabasAppDB"]
        collection = db["eventos"]
        target_location = location or _current_location_name()
        target_device = device_name or _current_device_name()

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
            print(f"[MONGO] Could not refresh local cache after insert: {cache_error}")
        event_bus.notify_events_changed()
        return str(res.inserted_id)
    except Exception as e:
        print(f"[MONGO] Error insertando evento personal: {e}")
        try:
            fallback_id = _append_personal_event_local(
                day_date=day_date,
                title=title,
                description=description,
                location=location,
                device_name=device_name,
            )
            print(f"[MONGO] Evento personal guardado en cache local como fallback: {fallback_id}")
            return fallback_id
        except Exception as local_error:
            print(f"[LOCAL] Error guardando fallback local del evento personal: {local_error}")
            return None


# ------------------------
# API PARA LA APP
# ------------------------
def get_events(device_name: Optional[str] = None, location_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Single entrypoint for app-level event retrieval.

    Args:
        device_name: Device identifier used for personal events filtering.

    Returns:
        List[Dict[str, Any]]: Retrieved event list.

    Examples:
        >>> current_events = get_events()
    """
    return fetch_events_from_mongo(device_name=device_name, location_name=location_name)

# ------------------------
# TEST MANUAL
# ------------------------
if __name__ == "__main__":
    eventos = get_events()
    print(f"Se han obtenido {len(eventos)} eventos (location='{_current_location_name()}').")
    for e in eventos:
        print(f"- {e['date']} | {e['title']} | {e['audience']} | {e['location']} ({e['color']})  id={e.get('id','')}")
