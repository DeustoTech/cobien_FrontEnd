"""Runtime helpers for notification configuration and ringtone playback.

This module provides:

- Unified config read/write for notifications settings.
- Ringtone discovery from the local ringtones directory.
- Playback abstraction over available backends (`pygame` or `playsound`).
"""

import json
import os
import threading
from typing import Any, Callable, Dict, List, Optional
from config_store import load_section, save_section


NONE_RINGTONE = ""
RINGTONES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings", "ringtones")

DEFAULT_NOTIFICATION_CONFIG = {
    "videollamada": {"group": 1, "intensity": 255, "color": "#00FF00", "mode": "ON", "ringtone": NONE_RINGTONE},
    "nuevo_evento": {"group": 2, "intensity": 255, "color": "#FF0000", "mode": "ON", "ringtone": NONE_RINGTONE},
    "nueva_foto": {"group": 3, "intensity": 255, "color": "#0000FF", "mode": "BLINK", "ringtone": NONE_RINGTONE},
}

AUDIO_AVAILABLE = False
AUDIO_BACKEND = None
pygame = None
playsound = None
_active_audio_thread = None
_audio_stop_event = threading.Event()

try:
    import pygame as _pygame

    _pygame.mixer.init()
    pygame = _pygame
    AUDIO_AVAILABLE = True
    AUDIO_BACKEND = "pygame"
except Exception:
    try:
        from playsound import playsound as _playsound

        playsound = _playsound
        AUDIO_AVAILABLE = True
        AUDIO_BACKEND = "playsound"
    except Exception:
        AUDIO_AVAILABLE = False
        AUDIO_BACKEND = None


def normalize_ringtone_name(ringtone: Any) -> str:
    """Normalize ringtone names across legacy and localized values.

    Args:
        ringtone: Raw ringtone value from config/UI.

    Returns:
        str: Normalized ringtone file name or `NONE_RINGTONE`.

    Examples:
        >>> normalize_ringtone_name("Ninguna")
        ''
    """
    if ringtone is None:
        return NONE_RINGTONE

    ringtone_name = str(ringtone).strip()
    if not ringtone_name:
        return NONE_RINGTONE

    if ringtone_name in {"Ninguna", "Aucune"}:
        return NONE_RINGTONE

    return ringtone_name


def load_notification_config() -> Dict[str, Dict[str, Any]]:
    """Load and sanitize notification configuration from unified config.

    Returns:
        Dict[str, Dict[str, Any]]: Normalized notification config map.

    Raises:
        No exception is propagated. Failures return default configuration.
    """
    try:
        config = load_section("notifications", DEFAULT_NOTIFICATION_CONFIG)
    except Exception as exc:
        print(f"[NOTIF_CONFIG] Error reading unified config: {exc}")
        return json.loads(json.dumps(DEFAULT_NOTIFICATION_CONFIG))

    merged = json.loads(json.dumps(DEFAULT_NOTIFICATION_CONFIG))
    for key, value in config.items():
        if key in merged and isinstance(value, dict):
            merged[key].update(value)
            merged[key]["ringtone"] = normalize_ringtone_name(merged[key].get("ringtone"))
    return merged


def save_notification_config(config: Dict[str, Dict[str, Any]]) -> bool:
    """Persist notification configuration into unified config storage.

    Args:
        config: Notification config map to save.

    Returns:
        bool: `True` if save succeeds, `False` otherwise.

    Raises:
        No exception is propagated. Failures are logged and return `False`.
    """
    try:
        sanitized = json.loads(json.dumps(config))
        for value in sanitized.values():
            if isinstance(value, dict):
                value["ringtone"] = normalize_ringtone_name(value.get("ringtone"))
        save_section("notifications", sanitized)
        return True
    except Exception as exc:
        print(f"[NOTIF_CONFIG] Error saving unified config: {exc}")
        return False


def load_ringtones() -> List[str]:
    """Load available ringtone file names from local ringtones directory.

    Returns:
        List[str]: Available ringtone names, including `NONE_RINGTONE` entry.
    """
    ringtones = [NONE_RINGTONE]
    if not os.path.exists(RINGTONES_DIR):
        try:
            os.makedirs(RINGTONES_DIR)
        except Exception as exc:
            print(f"[RINGTONE] Error creating directory: {exc}")
        return ringtones

    supported_formats = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
    try:
        for file_name in os.listdir(RINGTONES_DIR):
            if file_name.lower().endswith(supported_formats):
                ringtones.append(file_name)
    except Exception as exc:
        print(f"[RINGTONE] Error loading ringtones: {exc}")
    return ringtones


def stop_ringtone() -> None:
    """Stop currently playing ringtone (if any)."""
    _audio_stop_event.set()
    if not AUDIO_AVAILABLE:
        return
    try:
        if AUDIO_BACKEND == "pygame" and pygame is not None:
            pygame.mixer.music.stop()
    except Exception as exc:
        print(f"[RINGTONE] Stop error: {exc}")


def play_ringtone_file(
    ringtone_name: Any,
    on_finish: Optional[Callable[[], None]] = None,
) -> bool:
    """Play one ringtone file asynchronously using available backend.

    Args:
        ringtone_name: Requested ringtone name.
        on_finish: Optional callback invoked after playback ends/stops.

    Returns:
        bool: `True` if playback thread was started, `False` otherwise.

    Raises:
        No exception is propagated. Playback errors are logged.

    Examples:
        >>> play_ringtone_file("ringtone.wav")
        True
    """
    global _active_audio_thread

    ringtone_name = normalize_ringtone_name(ringtone_name)
    if ringtone_name == NONE_RINGTONE or not AUDIO_AVAILABLE:
        return False

    ringtone_path = os.path.join(RINGTONES_DIR, ringtone_name)
    if not os.path.exists(ringtone_path):
        print(f"[RINGTONE] File not found: {ringtone_path}")
        return False

    stop_ringtone()
    _audio_stop_event.clear()

    def _finalize():
        if callable(on_finish):
            try:
                on_finish()
            except Exception:
                pass

    def _play_sound():
        try:
            if AUDIO_BACKEND == "pygame" and pygame is not None:
                pygame.mixer.music.load(ringtone_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if _audio_stop_event.is_set():
                        pygame.mixer.music.stop()
                        _finalize()
                        return
                    pygame.time.Clock().tick(10)
            elif AUDIO_BACKEND == "playsound" and playsound is not None:
                if not _audio_stop_event.is_set():
                    playsound(ringtone_path)
            _finalize()
        except Exception as exc:
            print(f"[RINGTONE] Playback error: {exc}")
            _finalize()

    _active_audio_thread = threading.Thread(target=_play_sound, daemon=True)
    _active_audio_thread.start()
    return True
