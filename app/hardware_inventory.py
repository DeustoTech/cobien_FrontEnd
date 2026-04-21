"""Hardware inventory collection for furniture devices.

The inventory is gathered on-device using best-effort Linux commands and
lightweight sysfs/procfs reads. It is cached locally and attached to the first
heartbeat after deployment/runtime changes so the backend can expose a hardware
summary in the web administration.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_STATE_DIR = os.path.join(BASE_DIR, "runtime_state")
INVENTORY_CACHE_PATH = os.path.join(RUNTIME_STATE_DIR, "hardware_inventory_cache.json")
INVENTORY_SENT_STATE_PATH = os.path.join(RUNTIME_STATE_DIR, "hardware_inventory_sent_state.json")
VERSION_PATH = os.path.join(BASE_DIR, "VERSION")


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _run_command(args: List[str], timeout: int = 6) -> str:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return ""
    output = (proc.stdout or "").strip()
    if output:
        return output
    return (proc.stderr or "").strip()


def _command_available(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _read_version() -> str:
    return _read_text(VERSION_PATH) or "unknown"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_lscpu() -> Dict[str, str]:
    raw = _run_command(["lscpu"])
    data: Dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _parse_lspci_blocks() -> List[Dict[str, Any]]:
    raw = _run_command(["lspci", "-nnk"], timeout=10)
    if not raw:
        return []
    blocks: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    for line in raw.splitlines():
        if line and not line.startswith(("\t", " ")):
            if current:
                blocks.append(current)
            current = {"header": line.strip(), "details": []}
        elif current is not None:
            current["details"].append(line.strip())
    if current:
        blocks.append(current)
    return blocks


def _filter_lspci_devices(keywords: List[str]) -> List[Dict[str, str]]:
    keywords_cf = [kw.casefold() for kw in keywords]
    devices: List[Dict[str, str]] = []
    for block in _parse_lspci_blocks():
        header = str(block.get("header", "")).strip()
        if not header:
            continue
        if not any(keyword in header.casefold() for keyword in keywords_cf):
            continue
        driver = ""
        modules = ""
        for detail in block.get("details", []):
            lower = detail.casefold()
            if lower.startswith("kernel driver in use:"):
                driver = detail.split(":", 1)[1].strip()
            elif lower.startswith("kernel modules:"):
                modules = detail.split(":", 1)[1].strip()
        devices.append({"hardware": header, "driver": driver, "modules": modules})
    return devices


def _collect_cpu_info() -> Dict[str, Any]:
    lscpu = _parse_lscpu()
    return {
        "model": lscpu.get("Model name") or platform.processor() or _read_text("/proc/cpuinfo").splitlines()[4:5],
        "architecture": lscpu.get("Architecture") or platform.machine(),
        "logical_cpus": lscpu.get("CPU(s)") or str(os.cpu_count() or ""),
        "cores_per_socket": lscpu.get("Core(s) per socket", ""),
        "sockets": lscpu.get("Socket(s)", ""),
        "threads_per_core": lscpu.get("Thread(s) per core", ""),
        "max_mhz": lscpu.get("CPU max MHz", ""),
        "vendor": lscpu.get("Vendor ID", ""),
    }


def _collect_system_info() -> Dict[str, Any]:
    os_release: Dict[str, str] = {}
    for line in _read_text("/etc/os-release").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os_release[key.strip()] = value.strip().strip('"')

    return {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "platform": platform.platform(),
        "os_name": os_release.get("PRETTY_NAME") or os_release.get("NAME") or "",
        "boot_id": _read_text("/proc/sys/kernel/random/boot_id"),
        "product_name": _read_text("/sys/devices/virtual/dmi/id/product_name"),
        "product_version": _read_text("/sys/devices/virtual/dmi/id/product_version"),
        "sys_vendor": _read_text("/sys/devices/virtual/dmi/id/sys_vendor"),
        "board_name": _read_text("/sys/devices/virtual/dmi/id/board_name"),
        "board_vendor": _read_text("/sys/devices/virtual/dmi/id/board_vendor"),
    }


def _collect_audio_info() -> Dict[str, Any]:
    return {
        "playback_devices_raw": _run_command(["aplay", "-l"]) if _command_available("aplay") else "",
        "capture_devices_raw": _run_command(["arecord", "-l"]) if _command_available("arecord") else "",
        "pulse_info_raw": _run_command(["pactl", "info"]) if _command_available("pactl") else "",
        "controllers": _filter_lspci_devices(["audio", "multimedia audio"]),
    }


def _collect_camera_info() -> Dict[str, Any]:
    video_nodes = sorted(glob.glob("/dev/video*"))
    cameras = []
    if _command_available("v4l2-ctl"):
        raw = _run_command(["v4l2-ctl", "--list-devices"], timeout=8)
        current = None
        for line in raw.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            if not line.startswith(("\t", " ")):
                if current:
                    cameras.append(current)
                current = {"hardware": stripped.rstrip(":"), "nodes": []}
            elif current is not None:
                current["nodes"].append(stripped)
        if current:
            cameras.append(current)
    return {
        "video_nodes": video_nodes,
        "devices": cameras,
        "usb_matches": [line for line in _run_command(["lsusb"]).splitlines() if "camera" in line.casefold() or "webcam" in line.casefold()] if _command_available("lsusb") else [],
    }


def _collect_display_info() -> Dict[str, Any]:
    drm_connectors = []
    for status_path in sorted(glob.glob("/sys/class/drm/*/status")):
        status = _read_text(status_path)
        if not status:
            continue
        connector = os.path.basename(os.path.dirname(status_path))
        drm_connectors.append({"connector": connector, "status": status})
    xrandr_raw = ""
    display_env = (os.getenv("DISPLAY") or "").strip()
    if display_env and _command_available("xrandr"):
        xrandr_raw = _run_command(["xrandr", "--query"], timeout=8)
    return {
        "display_env": display_env,
        "xrandr_raw": xrandr_raw,
        "drm_connectors": drm_connectors,
    }


def _collect_graphics_info() -> Dict[str, Any]:
    return {
        "controllers": _filter_lspci_devices(["vga compatible controller", "3d controller", "display controller"]),
        "glxinfo_renderer": _run_command(["glxinfo", "-B"], timeout=8) if _command_available("glxinfo") else "",
    }


def _short_line(value: str, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _build_summary_sections(payload: Dict[str, Any]) -> Dict[str, Any]:
    cpu = payload.get("cpu", {}) or {}
    audio = payload.get("audio", {}) or {}
    camera = payload.get("camera", {}) or {}
    display = payload.get("display", {}) or {}
    graphics = payload.get("graphics", {}) or {}
    system = payload.get("system", {}) or {}

    audio_hw = ", ".join(item.get("hardware", "") for item in (audio.get("controllers") or []) if item.get("hardware")) or _short_line(audio.get("capture_devices_raw", "") or audio.get("playback_devices_raw", ""))
    audio_drivers = ", ".join(item.get("driver", "") for item in (audio.get("controllers") or []) if item.get("driver"))
    graphics_hw = ", ".join(item.get("hardware", "") for item in (graphics.get("controllers") or []) if item.get("hardware")) or _short_line(graphics.get("glxinfo_renderer", ""))
    graphics_drivers = ", ".join(item.get("driver", "") for item in (graphics.get("controllers") or []) if item.get("driver"))
    camera_hw = ", ".join(item.get("hardware", "") for item in (camera.get("devices") or []) if item.get("hardware")) or ", ".join(camera.get("video_nodes") or [])
    display_hw = ", ".join(f"{item.get('connector')}: {item.get('status')}" for item in (display.get("drm_connectors") or [])) or _short_line(display.get("xrandr_raw", ""))
    cpu_summary = " · ".join(part for part in [str(cpu.get("model", "")).strip(), f"{cpu.get('logical_cpus', '')} hilos".strip() if cpu.get("logical_cpus") else "", str(cpu.get("architecture", "")).strip()] if part)

    return {
        "system": {
            "hardware": " · ".join(part for part in [system.get("sys_vendor", ""), system.get("product_name", ""), system.get("product_version", "")] if str(part).strip()),
            "driver": system.get("kernel", ""),
        },
        "cpu": {
            "hardware": cpu_summary,
            "driver": cpu.get("vendor", ""),
        },
        "graphics": {
            "hardware": graphics_hw,
            "driver": graphics_drivers,
        },
        "audio": {
            "hardware": audio_hw,
            "driver": audio_drivers,
        },
        "camera": {
            "hardware": camera_hw,
            "driver": "",
        },
        "display": {
            "hardware": display_hw,
            "driver": "",
        },
    }


def collect_hardware_inventory() -> Dict[str, Any]:
    payload = {
        "captured_at": _utc_now_iso(),
        "app_version": _read_version(),
        "system": _collect_system_info(),
        "cpu": _collect_cpu_info(),
        "graphics": _collect_graphics_info(),
        "audio": _collect_audio_info(),
        "camera": _collect_camera_info(),
        "display": _collect_display_info(),
    }
    payload["summary"] = _build_summary_sections(payload)
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def load_or_collect_hardware_inventory() -> Dict[str, Any]:
    cached = _load_json(INVENTORY_CACHE_PATH)
    if cached:
        return cached
    payload = collect_hardware_inventory()
    _save_json(INVENTORY_CACHE_PATH, payload)
    return payload


def get_heartbeat_hardware_payload() -> Dict[str, Any]:
    """Return a one-shot hardware payload when a fresh report should be sent."""
    inventory = load_or_collect_hardware_inventory()
    state = _load_json(INVENTORY_SENT_STATE_PATH)
    current_version = _read_version()
    current_boot_id = str((inventory.get("system") or {}).get("boot_id") or "").strip()
    current_fingerprint = str(inventory.get("fingerprint") or "").strip()

    if (
        state.get("last_sent_version") == current_version
        and state.get("last_sent_boot_id") == current_boot_id
        and state.get("last_sent_fingerprint") == current_fingerprint
    ):
        return {}

    state.update(
        {
            "last_sent_at": _utc_now_iso(),
            "last_sent_version": current_version,
            "last_sent_boot_id": current_boot_id,
            "last_sent_fingerprint": current_fingerprint,
        }
    )
    _save_json(INVENTORY_SENT_STATE_PATH, state)
    return {
        "hardware_summary": inventory.get("summary", {}),
        "hardware_inventory": inventory,
    }
