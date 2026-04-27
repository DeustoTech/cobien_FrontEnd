"""Audio device enumeration, test playback, and real-time VU meter.

Provides a unified abstraction used by the Kivy audio-settings screen and
the Qt videocall launcher:

- list_output_devices() / list_input_devices()  — PortAudio device catalogue
- play_test_beep()                              — non-blocking sine-tone test
- VUMeter                                       — real-time RMS level meter
- apply_system_audio_devices()                  — set PulseAudio defaults via pactl
- pa_list_sinks() / pa_list_sources()           — PulseAudio sink/source names
"""

import queue
import subprocess
import threading
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    _NUMPY_OK = False

try:
    import sounddevice as sd
    _SD_OK = True
except ImportError:
    _SD_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# PulseAudio helpers
# ─────────────────────────────────────────────────────────────────────────────

def pa_list_sinks() -> List[Dict[str, str]]:
    """Return PulseAudio output sinks as [{index, name, description}].

    Falls back to an empty list when pactl is unavailable.
    """
    return _pa_list_items("sinks")


def pa_list_sources() -> List[Dict[str, str]]:
    """Return PulseAudio input sources as [{index, name, description}].

    Monitor sources (*.monitor) are excluded to surface only real microphones.
    """
    items = _pa_list_items("sources")
    return [s for s in items if not s["name"].endswith(".monitor")]


def _pa_list_items(kind: str) -> List[Dict[str, str]]:
    try:
        result = subprocess.run(
            ["pactl", "list", "short", kind],
            capture_output=True, text=True, timeout=3,
        )
        items = []
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                items.append({"index": parts[0].strip(), "name": parts[1].strip(),
                               "description": parts[1].strip()})
        return items
    except Exception:
        return []


def pa_set_default_sink(sink_name: str) -> bool:
    """Set the PulseAudio default output sink. Returns True on success."""
    if not sink_name:
        return False
    try:
        r = subprocess.run(
            ["pactl", "set-default-sink", sink_name],
            capture_output=True, timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def pa_set_default_source(source_name: str) -> bool:
    """Set the PulseAudio default input source. Returns True on success."""
    if not source_name:
        return False
    try:
        r = subprocess.run(
            ["pactl", "set-default-source", source_name],
            capture_output=True, timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def pa_get_default_sink() -> str:
    """Return the name of the current PulseAudio default sink."""
    try:
        r = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def pa_get_default_source() -> str:
    """Return the name of the current PulseAudio default source."""
    try:
        r = subprocess.run(
            ["pactl", "get-default-source"],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def pa_adjust_volume(step_percent: int = 5) -> None:
    """Raise or lower the default sink volume by step_percent.

    Positive values raise the volume; negative values lower it.
    Runs non-blocking so it never stalls the UI thread.
    """
    sign = "+" if step_percent >= 0 else ""
    delta = f"{sign}{step_percent}%"
    try:
        subprocess.Popen(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", delta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        print(f"[AUDIO] pa_adjust_volume failed: {exc}")


def apply_system_audio_devices(output_device: str = "", input_device: str = "") -> None:
    """Apply stored audio device preferences to PulseAudio and sounddevice.

    Called at app startup and when the user saves new settings.

    Args:
        output_device: PA sink name or sounddevice device name for output.
        input_device:  PA source name or sounddevice device name for input.
    """
    if output_device:
        ok = pa_set_default_sink(output_device)
        if not ok:
            # Try to find a matching sink by substring
            for sink in pa_list_sinks():
                if output_device.lower() in sink["name"].lower():
                    pa_set_default_sink(sink["name"])
                    break
        print(f"[AUDIO] Output sink set to: {output_device!r}")

    if input_device:
        ok = pa_set_default_source(input_device)
        if not ok:
            for src in pa_list_sources():
                if input_device.lower() in src["name"].lower():
                    pa_set_default_source(src["name"])
                    break
        print(f"[AUDIO] Input source set to: {input_device!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Sounddevice device catalogue (for Python-level mic access)
# ─────────────────────────────────────────────────────────────────────────────

def list_output_devices() -> List[Dict[str, Any]]:
    """Return PortAudio output devices visible to sounddevice.

    Returns:
        List of dicts: {index, name, is_default}.  Empty when sounddevice
        is unavailable.
    """
    if not _SD_OK:
        return []
    try:
        default_out = sd.default.device[1]
    except Exception:
        default_out = -1
    result = []
    try:
        for i, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_output_channels", 0)) > 0:
                result.append({
                    "index": i,
                    "name": str(dev["name"]),
                    "is_default": (i == default_out),
                })
    except Exception as exc:
        print(f"[AUDIO] list_output_devices error: {exc}")
    return result


def list_input_devices() -> List[Dict[str, Any]]:
    """Return PortAudio input devices visible to sounddevice.

    Returns:
        List of dicts: {index, name, is_default}.  Empty when sounddevice
        is unavailable.
    """
    if not _SD_OK:
        return []
    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = -1
    result = []
    try:
        for i, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels", 0)) > 0:
                result.append({
                    "index": i,
                    "name": str(dev["name"]),
                    "is_default": (i == default_in),
                })
    except Exception as exc:
        print(f"[AUDIO] list_input_devices error: {exc}")
    return result


def find_input_device_index(name: str) -> Optional[int]:
    """Resolve sounddevice input device index from stored name.

    Uses exact match first, then case-insensitive substring.

    Args:
        name: Device name as stored in config.

    Returns:
        Device index or None.
    """
    if not name or not _SD_OK:
        return None
    name_lower = name.lower()
    try:
        for i, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels", 0)) > 0:
                dev_name = dev["name"].lower()
                if dev_name == name_lower or name_lower in dev_name or dev_name in name_lower:
                    return i
    except Exception:
        pass
    return None


def find_output_device_index(name: str) -> Optional[int]:
    """Resolve sounddevice output device index from stored name."""
    if not name or not _SD_OK:
        return None
    name_lower = name.lower()
    try:
        for i, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_output_channels", 0)) > 0:
                dev_name = dev["name"].lower()
                if dev_name == name_lower or name_lower in dev_name or dev_name in name_lower:
                    return i
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Test beep
# ─────────────────────────────────────────────────────────────────────────────

def play_test_beep(
    device_index: Optional[int] = None,
    freq: float = 880.0,
    duration: float = 0.6,
    samplerate: int = 44100,
) -> None:
    """Play a short anti-click sine-wave beep on the given output device.

    Runs in a daemon thread — never blocks the calling code.

    Args:
        device_index: sounddevice device index, or None for system default.
        freq:         Tone frequency in Hz (default 880 Hz — A5).
        duration:     Beep duration in seconds.
        samplerate:   PCM sample rate.
    """
    if not _SD_OK or not _NUMPY_OK:
        # Fallback: bell character
        print("\a", end="", flush=True)
        return

    def _play() -> None:
        try:
            t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
            wave = (0.35 * np.sin(2 * np.pi * freq * t)).astype("float32")
            # 10 ms fade-in / fade-out to avoid click artefacts
            fade = int(samplerate * 0.01)
            wave[:fade] *= np.linspace(0.0, 1.0, fade, dtype="float32")
            wave[-fade:] *= np.linspace(1.0, 0.0, fade, dtype="float32")
            sd.play(wave, samplerate=samplerate, device=device_index, blocking=True)
        except Exception as exc:
            print(f"[AUDIO] Test beep error: {exc}")

    threading.Thread(target=_play, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# VU meter
# ─────────────────────────────────────────────────────────────────────────────

class VUMeter:
    """Real-time RMS input-level meter driven by a sounddevice InputStream.

    Designed to be polled from a Kivy Clock callback:

        meter = VUMeter(device_index=2)
        meter.start()
        Clock.schedule_interval(lambda dt: update_bar(meter.get_level()), 0.05)
        # ...
        meter.stop()

    The ``get_level()`` method returns a value in [0.0, 1.0] with built-in
    smoothing and natural decay so a simple progress bar looks good.
    """

    _SAMPLERATE = 44100
    _BLOCKSIZE  = 1024
    # Empirical gain: typical speech peaks around 0.05 RMS → maps to ~0.4 on bar
    _SCALE = 12.0

    def __init__(self, device_index: Optional[int] = None) -> None:
        self._device_index = device_index
        self._queue: queue.Queue = queue.Queue(maxsize=8)
        self._stream: Optional[Any] = None
        self._level: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Open the input stream. Returns True when the stream starts."""
        if not _SD_OK or not _NUMPY_OK:
            print("[VU] sounddevice or numpy unavailable — VU meter disabled")
            return False
        if self._stream is not None:
            return True
        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                channels=1,
                samplerate=self._SAMPLERATE,
                blocksize=self._BLOCKSIZE,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            return True
        except Exception as exc:
            print(f"[VU] Cannot start input stream: {exc}")
            self._stream = None
            return False

    def _callback(
        self, indata: Any, frames: int, time: Any, status: Any
    ) -> None:
        if status:
            pass  # ignore overflow warnings silently
        rms = float(np.sqrt(np.mean(indata ** 2)))
        level = min(rms * self._SCALE, 1.0)
        try:
            self._queue.put_nowait(level)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(level)
            except Exception:
                pass

    def get_level(self) -> float:
        """Return the latest smoothed RMS level in [0.0, 1.0].

        Call from a Kivy Clock or any polling loop.  Thread-safe.
        """
        try:
            raw = self._queue.get_nowait()
            # 70 % new sample + 30 % previous for smoothing
            self._level = 0.7 * raw + 0.3 * self._level
        except queue.Empty:
            # Natural decay when silent
            self._level = max(0.0, self._level - 0.04)
        return self._level

    def change_device(self, device_index: Optional[int]) -> bool:
        """Restart the stream on a different device without recreating the meter."""
        self.stop()
        self._device_index = device_index
        self._level = 0.0
        return self.start()

    def stop(self) -> None:
        """Stop capturing and release all resources."""
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                print(f"[VU] Error stopping stream: {exc}")
        self._level = 0.0
        # Drain the queue
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
