# CoBien FrontEnd

Python-based frontend/runtime for the CoBien furniture system.

This repository contains:

- The Kivy application (`app/`)
- Ubuntu deployment and runtime orchestration scripts (`deploy/ubuntu/`)
- Systemd user units for auto-start and scheduled updates

---

## 1. Architecture Overview

The production runtime is orchestrated by a single entrypoint:

- `deploy/ubuntu/cobien-launcher.sh`

The launcher handles:

- Environment bootstrap with UV + Python 3.11
- Dependency sync (`uv sync`)
- Device identity + runtime config persistence
- CAN setup (real hardware mode) and CAN bridge launch
- Frontend launch (`uv run --project app mainApp.py`)
- Update checks and clean relaunch behavior
- Optional systemd user service/timer installation

Main app path:

- `app/mainApp.py`

---

## 2. Prerequisites

- Ubuntu (desktop session recommended for UI runtime)
- Two repositories under the same workspace root:
  - `cobien_FrontEnd`
  - `cobien_MQTT_Dictionnary`
- Internet access for first-time dependency/model download
- `sudo` access if system packages or CAN runtime setup are required

Default workspace:

- `$HOME/cobien`

---

## 3. First-Time Setup (Interactive)

From `cobien_FrontEnd` root:

```bash
bash deploy/ubuntu/cobien-launcher.sh
```

This interactive flow can:

- Reuse previous saved launcher configuration (if present)
- Install missing system/runtime packages
- Prepare UV and Python
- Create/sync virtual environment for `app/`
- Ask device identity and runtime options
- Install/enable systemd user units (if selected/required)
- Launch runtime

---

## 4. Non-Interactive Deployment Commands

Run full unattended flow:

```bash
bash deploy/ubuntu/cobien-launcher.sh \
  --non-interactive --yes \
  --workspace "$HOME/cobien" \
  --frontend-name cobien_FrontEnd \
  --mqtt-name cobien_MQTT_Dictionnary \
  --branch development_fix \
  --device-id CoBien1 \
  --videocall-room CoBien1 \
  --device-location Logroño
```

Only setup dependencies/venv/config:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode setup --non-interactive --yes
```

Launch runtime:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode launch --non-interactive --yes
```

One-shot update check:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode update-once --non-interactive --yes
```

Watch loop update mode:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode watch --non-interactive --yes
```

Dry-run resolved config:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode dry-run
```

---

## 5. Dependency Management (UV-Only)

The project is UV-based.

Dependency source:

- `app/pyproject.toml`

Standard commands:

```bash
uv sync --project app --python 3.11
uv run --project app mainApp.py
```

There is no `requirements.txt` runtime workflow anymore.

---

## 6. Runtime Modes

`--hardware-mode` controls CAN behavior:

- `real`: configure CAN + run bridge/logger
- `mock`: skip hardware CAN stack
- `auto` (default): enable hardware only if detected

Useful for VM/testing:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode launch --hardware-mode mock
```

---

## 7. Systemd User Services (Recommended)

Install/update services:

```bash
bash deploy/ubuntu/install-systemd-user.sh
```

Installed units:

- `cobien-launcher.service` (main runtime)
- `cobien-update.service` (one-shot update task)
- `cobien-update.timer` (daily scheduled update, default 01:00)

Service operations:

```bash
systemctl --user daemon-reload
systemctl --user enable --now cobien-launcher.service cobien-update.timer
systemctl --user restart cobien-launcher.service
systemctl --user status cobien-launcher.service
systemctl --user list-timers | grep cobien-update
```

Force manual update:

```bash
systemctl --user start cobien-update.service
```

---

## 8. Logs and Diagnostics

Runtime logs directory:

- `cobien_FrontEnd/logs/`

Typical files:

- `cobien-app-YYYYMMDD.log`
- `mqtt-can-bridge-YYYYMMDD.log`
- `can-bus-YYYYMMDD.log`

Launcher journal:

```bash
journalctl --user -u cobien-launcher.service -f
```

Quick process check:

```bash
pgrep -af "cobien-launcher.sh|mainApp.py|cobien_bridge|candump"
```

---

## 9. Configuration Files

Primary launcher environment file:

- `deploy/ubuntu/cobien-update.env`

Template:

- `deploy/ubuntu/cobien-update.env.example`

Unified app runtime config:

- `app/config/config.json` (generated/updated from defaults + launcher sync)

Defaults:

- `app/config/config.default.json`

---

## 10. TTS Engine Selection

Supported:

- `pyttsx3` (default)
- `piper` (optional)

When `piper` is selected, launcher attempts:

1. Existing binary
2. `apt` package
3. `uv tool install piper-tts`
4. Fallback to `pyttsx3` if unavailable

---

## 11. Common Operational Flows

### Update an existing device

```bash
cd ~/cobien/cobien_FrontEnd
git pull --ff-only origin development_fix
systemctl --user restart cobien-launcher.service
```

### Deploy from scratch on a new device

```bash
mkdir -p ~/cobien
cd ~/cobien
git clone <FRONTEND_REPO_URL> cobien_FrontEnd
git clone <MQTT_REPO_URL> cobien_MQTT_Dictionnary
cd cobien_FrontEnd
bash deploy/ubuntu/cobien-launcher.sh
```

---

## 12. Important Notes

- Use `cobien-launcher.sh` as the single operational entrypoint.
- Do not run legacy startup mechanisms in parallel (`~/.config/autostart` old entries, duplicated cron jobs, old scripts).
- Keep `development_fix` and remote config aligned with deployed branch.
