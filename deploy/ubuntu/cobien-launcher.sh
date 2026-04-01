#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKSPACE_ROOT_DEFAULT="${HOME}/cobien"
FRONTEND_REPO_NAME_DEFAULT="cobien_FrontEnd"
MQTT_REPO_NAME_DEFAULT="cobien_MQTT_Dictionnary"
BRANCH_NAME_DEFAULT="development_fix"
CRON_SCHEDULE_DEFAULT="0 1 * * *"
POLL_INTERVAL_DEFAULT="60"
CAN_LOG_ENABLE_DEFAULT="1"
LOG_RETENTION_DAYS_DEFAULT="365"

MODE="run"
WORKSPACE_ROOT="${COBIEN_WORKSPACE_ROOT:-$WORKSPACE_ROOT_DEFAULT}"
FRONTEND_REPO_NAME="${COBIEN_FRONTEND_REPO_NAME:-$FRONTEND_REPO_NAME_DEFAULT}"
MQTT_REPO_NAME="${COBIEN_MQTT_REPO_NAME:-$MQTT_REPO_NAME_DEFAULT}"
BRANCH_NAME="${COBIEN_UPDATE_BRANCH:-$BRANCH_NAME_DEFAULT}"
RUN_UPDATE_ONCE="${COBIEN_RUN_UPDATE_ONCE:-0}"
INSTALL_SYSTEM_DEPS="${COBIEN_INSTALL_SYSTEM_DEPS:-1}"
RECREATE_VENV="${COBIEN_RECREATE_VENV:-0}"
ENABLE_WATCH="${COBIEN_ENABLE_WATCH:-1}"
INSTALL_CRON="${COBIEN_INSTALL_CRON:-0}"
INSTALL_SYSTEMD_USER="${COBIEN_INSTALL_SYSTEMD_USER:-0}"
CRON_SCHEDULE="${COBIEN_CRON_SCHEDULE:-$CRON_SCHEDULE_DEFAULT}"
NON_INTERACTIVE="${COBIEN_NON_INTERACTIVE:-0}"
AUTO_CONFIRM="${COBIEN_AUTO_CONFIRM:-0}"
REMOTE_NAME="${COBIEN_UPDATE_REMOTE:-origin}"
POLL_INTERVAL_SEC="${COBIEN_UPDATE_INTERVAL_SEC:-$POLL_INTERVAL_DEFAULT}"
CAN_LOG_ENABLE="${COBIEN_CAN_LOG_ENABLE:-$CAN_LOG_ENABLE_DEFAULT}"
LOG_RETENTION_DAYS="${COBIEN_LOG_RETENTION_DAYS:-$LOG_RETENTION_DAYS_DEFAULT}"
RELAUNCH_AFTER_UPDATE="${COBIEN_RELAUNCH_AFTER_UPDATE:-0}"
FORCE_RESTART="${COBIEN_FORCE_RESTART:-0}"
DEVICE_ID="${COBIEN_DEVICE_ID:-}"
VIDEOCALL_ROOM="${COBIEN_VIDEOCALL_ROOM:-}"
DEVICE_LOCATION="${COBIEN_DEVICE_LOCATION:-}"
TTS_ENGINE="${COBIEN_TTS_ENGINE:-pyttsx3}"
TTS_PIPER_BIN="${COBIEN_TTS_PIPER_BIN:-}"
TTS_PIPER_MODEL_ES="${COBIEN_TTS_PIPER_MODEL_ES:-}"
TTS_PIPER_MODEL_FR="${COBIEN_TTS_PIPER_MODEL_FR:-}"
PYTHON_BIN="${COBIEN_BOOTSTRAP_PYTHON_BIN:-}"
UV_BIN="${COBIEN_BOOTSTRAP_UV_BIN:-}"
PYTHON_REQUEST="${COBIEN_BOOTSTRAP_PYTHON_VERSION:-3.11}"
ARGS_PROVIDED="0"
GLOBAL_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cobien"
LAST_RUN_CONFIG_FILE="$GLOBAL_CONFIG_DIR/launcher-last.env"
LOCK_FILE="${COBIEN_LAUNCHER_LOCK_FILE:-/tmp/cobien-launcher.lock}"
LOCK_FD=99

usage() {
  cat <<EOF
Usage:
  $(basename "$0")
  $(basename "$0") --workspace "$HOME/cobien"
  $(basename "$0") --mode setup --workspace "$HOME/cobien"
  $(basename "$0") --mode update-once
  $(basename "$0") --mode watch
  $(basename "$0") --mode launch
  $(basename "$0") --mode dry-run

Modes:
  run           Full interactive or unattended flow
  setup         Prepare dependencies, uv, Python and .venv only
  update-once   Check for changes and relaunch if updated
  watch         Check for changes every minute
  launch        Launch the furniture runtime
  dry-run       Print resolved configuration

Options:
  --workspace PATH
  --frontend-name NAME
  --mqtt-name NAME
  --branch NAME
  --run-update-once
  --enable-watch
  --install-cron
  --install-systemd-user
  --cron-schedule "0 1 * * *"
  --device-id NAME
  --videocall-room NAME
  --device-location LOCATION
  --tts-engine ENGINE
  --tts-piper-bin PATH
  --tts-piper-model-es PATH
  --tts-piper-model-fr PATH
  --recreate-venv
  --force-restart
  --skip-system-deps
  --non-interactive
  --yes
  -h, --help
EOF
}

log() {
  echo "[COBIEN] $*"
}

read_lock_pid() {
  if [[ -f "$LOCK_FILE" ]]; then
    head -n1 "$LOCK_FILE" 2>/dev/null | tr -dc '0-9'
  fi
}

discover_running_launcher_pid() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -n "$candidate" && "$candidate" != "$$" && "$candidate" != "$PPID" ]]; then
      echo "$candidate"
      return 0
    fi
  done < <(pgrep -f "cobien-launcher.sh" 2>/dev/null || true)
  return 1
}

discover_running_launcher_pids() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -n "$candidate" && "$candidate" != "$$" && "$candidate" != "$PPID" ]]; then
      echo "$candidate"
    fi
  done < <(pgrep -f "cobien-launcher.sh" 2>/dev/null || true)
}

stop_existing_launcher_instance() {
  local lock_pid
  lock_pid="$(read_lock_pid)"

  if [[ -z "${lock_pid:-}" ]]; then
    lock_pid="$(discover_running_launcher_pid || true)"
    if [[ -z "${lock_pid:-}" ]]; then
      log "Could not determine running launcher PID from lock file or process list."
      return 1
    fi
    log "Lock file PID unavailable, discovered running launcher PID=$lock_pid"
  fi

  if [[ "$lock_pid" == "$$" ]]; then
    log "Lock file points to current PID; refusing to stop self."
    return 1
  fi

  if ! kill -0 "$lock_pid" >/dev/null 2>&1; then
    log "Stale lock detected (PID $lock_pid not running). Trying process-list fallback."
    lock_pid="$(discover_running_launcher_pid || true)"
    if [[ -z "${lock_pid:-}" ]]; then
      return 0
    fi
    log "Fallback launcher PID discovered: $lock_pid"
  fi

  log "Stopping existing launcher instance PID=$lock_pid"
  kill -TERM "$lock_pid" >/dev/null 2>&1 || true

  local i
  for i in {1..10}; do
    if ! kill -0 "$lock_pid" >/dev/null 2>&1; then
      log "Existing launcher stopped."
      return 0
    fi
    sleep 1
  done

  log "Existing launcher did not stop in time; forcing kill."
  kill -KILL "$lock_pid" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "$lock_pid" >/dev/null 2>&1; then
    log "Failed to terminate existing launcher PID=$lock_pid"
    return 1
  fi

  local remaining_pid
  while IFS= read -r remaining_pid; do
    [[ -z "$remaining_pid" ]] && continue
    if kill -0 "$remaining_pid" >/dev/null 2>&1; then
      log "Stopping extra launcher instance PID=$remaining_pid"
      kill -TERM "$remaining_pid" >/dev/null 2>&1 || true
      sleep 1
      kill -KILL "$remaining_pid" >/dev/null 2>&1 || true
    fi
  done < <(discover_running_launcher_pids)

  return 0
}

acquire_single_instance_lock() {
  if ! command -v flock >/dev/null 2>&1; then
    log "flock not available; single-instance protection disabled"
    return 0
  fi

  mkdir -p "$(dirname "$LOCK_FILE")"

  eval "exec ${LOCK_FD}>\"$LOCK_FILE\""
  if ! flock -n "$LOCK_FD"; then
    local lock_pid
    lock_pid="$(read_lock_pid)"
    log "Another cobien-launcher instance is already running (PID=${lock_pid:-unknown})."

    if [[ "$FORCE_RESTART" == "1" ]]; then
      if stop_existing_launcher_instance; then
        sleep 1
        if ! flock -n "$LOCK_FD"; then
          log "Unable to acquire lock after stopping previous instance."
          exit 1
        fi
      else
        log "Unable to stop existing launcher instance."
        exit 1
      fi
    elif [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to stop the previous launcher instance and continue" "y"; then
      if stop_existing_launcher_instance; then
        sleep 1
        if ! flock -n "$LOCK_FD"; then
          log "Unable to acquire lock after stopping previous instance."
          exit 1
        fi
      else
        log "Unable to stop existing launcher instance."
        exit 1
      fi
    else
      log "Exiting without changes. Use --force-restart to stop the existing instance automatically."
      exit 0
    fi
  fi

  printf '%s\n' "$$" 1>&"$LOCK_FD" || true
  log "Single-instance lock acquired: $LOCK_FILE"
}

save_last_run_config() {
  mkdir -p "$GLOBAL_CONFIG_DIR"
  cat > "$LAST_RUN_CONFIG_FILE" <<EOF
COBIEN_WORKSPACE_ROOT=$WORKSPACE_ROOT
COBIEN_FRONTEND_REPO_NAME=$FRONTEND_REPO_NAME
COBIEN_MQTT_REPO_NAME=$MQTT_REPO_NAME
COBIEN_UPDATE_BRANCH=$BRANCH_NAME
COBIEN_UPDATE_REMOTE=$REMOTE_NAME
COBIEN_UPDATE_INTERVAL_SEC=$POLL_INTERVAL_SEC
COBIEN_DEVICE_ID=$DEVICE_ID
COBIEN_VIDEOCALL_ROOM=$VIDEOCALL_ROOM
COBIEN_DEVICE_LOCATION=$DEVICE_LOCATION
COBIEN_TTS_ENGINE=$TTS_ENGINE
COBIEN_TTS_PIPER_BIN=$TTS_PIPER_BIN
COBIEN_TTS_PIPER_MODEL_ES=$TTS_PIPER_MODEL_ES
COBIEN_TTS_PIPER_MODEL_FR=$TTS_PIPER_MODEL_FR
COBIEN_CRON_SCHEDULE=$CRON_SCHEDULE
COBIEN_BOOTSTRAP_PYTHON_VERSION=$PYTHON_REQUEST
EOF
  log "Last run configuration saved to: $LAST_RUN_CONFIG_FILE"
}

load_last_run_config() {
  if [[ ! -f "$LAST_RUN_CONFIG_FILE" ]]; then
    return 1
  fi
  set -a
  source "$LAST_RUN_CONFIG_FILE"
  set +a

  WORKSPACE_ROOT="${COBIEN_WORKSPACE_ROOT:-$WORKSPACE_ROOT}"
  FRONTEND_REPO_NAME="${COBIEN_FRONTEND_REPO_NAME:-$FRONTEND_REPO_NAME}"
  MQTT_REPO_NAME="${COBIEN_MQTT_REPO_NAME:-$MQTT_REPO_NAME}"
  BRANCH_NAME="${COBIEN_UPDATE_BRANCH:-$BRANCH_NAME}"
  REMOTE_NAME="${COBIEN_UPDATE_REMOTE:-$REMOTE_NAME}"
  POLL_INTERVAL_SEC="${COBIEN_UPDATE_INTERVAL_SEC:-$POLL_INTERVAL_SEC}"
  DEVICE_ID="${COBIEN_DEVICE_ID:-$DEVICE_ID}"
  VIDEOCALL_ROOM="${COBIEN_VIDEOCALL_ROOM:-$VIDEOCALL_ROOM}"
  DEVICE_LOCATION="${COBIEN_DEVICE_LOCATION:-$DEVICE_LOCATION}"
  TTS_ENGINE="${COBIEN_TTS_ENGINE:-$TTS_ENGINE}"
  TTS_PIPER_BIN="${COBIEN_TTS_PIPER_BIN:-$TTS_PIPER_BIN}"
  TTS_PIPER_MODEL_ES="${COBIEN_TTS_PIPER_MODEL_ES:-$TTS_PIPER_MODEL_ES}"
  TTS_PIPER_MODEL_FR="${COBIEN_TTS_PIPER_MODEL_FR:-$TTS_PIPER_MODEL_FR}"
  CRON_SCHEDULE="${COBIEN_CRON_SCHEDULE:-$CRON_SCHEDULE}"
  PYTHON_REQUEST="${COBIEN_BOOTSTRAP_PYTHON_VERSION:-$PYTHON_REQUEST}"
  return 0
}

print_last_run_config_summary() {
  echo
  echo "Previous configuration found:"
  echo "  Workspace:        $WORKSPACE_ROOT"
  echo "  Frontend repo:    $FRONTEND_REPO_NAME"
  echo "  MQTT repo:        $MQTT_REPO_NAME"
  echo "  Branch:           $BRANCH_NAME"
  echo "  Device ID:        $DEVICE_ID"
  echo "  Videocall room:   $VIDEOCALL_ROOM"
  echo "  Device location:  $DEVICE_LOCATION"
  echo "  TTS engine:       $TTS_ENGINE"
  echo "  Cron schedule:    $CRON_SCHEDULE"
  echo "  Python request:   $PYTHON_REQUEST"
  echo
}

resolve_paths() {
  FRONTEND_REPO="$WORKSPACE_ROOT/$FRONTEND_REPO_NAME"
  MQTT_REPO="$WORKSPACE_ROOT/$MQTT_REPO_NAME"
  FRONTEND_APP_DIR="$FRONTEND_REPO/app"
  VENV_DIR="$FRONTEND_REPO/.venv"
  ENV_FILE="$FRONTEND_REPO/deploy/ubuntu/cobien-update.env"
  BRIDGE_DIR="$MQTT_REPO/Interface_MQTT_CAN_c"
  CAN_CONFIG="$BRIDGE_DIR/conversion.json"
  SELF_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-launcher.sh"
  FRONTEND_REPO_ROOT="$FRONTEND_REPO"
  LOG_DIR="${COBIEN_LOG_DIR:-$FRONTEND_REPO_ROOT/logs}"
  RUNTIME_STATE_DIR="$FRONTEND_APP_DIR/runtime_state"
  UPDATE_MARKER_FILE="$RUNTIME_STATE_DIR/system_updated.json"
}

derive_default_device_id() {
  local hostname_value
  hostname_value="$(hostname 2>/dev/null || echo "")"
  if [[ -n "$hostname_value" && "$hostname_value" =~ ([0-9]+)$ ]]; then
    echo "CoBien${BASH_REMATCH[1]}"
  else
    echo "CoBien1"
  fi
}

normalize_device_identity() {
  if [[ -z "$DEVICE_ID" ]]; then
    DEVICE_ID="$(derive_default_device_id)"
  fi
  if [[ -z "$VIDEOCALL_ROOM" ]]; then
    VIDEOCALL_ROOM="$DEVICE_ID"
  fi
  if [[ -z "$DEVICE_LOCATION" ]]; then
    DEVICE_LOCATION="Bilbao"
  fi
}

setup_can_bus() {
  echo "[CAN] Initializing the CAN bus"
  sudo -n /sbin/ip link set can0 down
  sudo -n /sbin/ip link set can0 type can bitrate "${COBIEN_CAN_BITRATE:-500000}"
  sudo -n /sbin/ip link set can0 up
}

start_can_logger_background() {
  if [[ "$CAN_LOG_ENABLE" != "1" ]]; then
    echo "[CAN] Logging disabled (COBIEN_CAN_LOG_ENABLE=$CAN_LOG_ENABLE)"
    return 0
  fi

  if ! command -v candump >/dev/null 2>&1; then
    echo "[CAN] candump not available; skipping CAN logging"
    return 0
  fi

  cleanup_old_logs "can-bus"
  local can_log_file
  can_log_file="$(build_dated_log_path "can-bus")"
  printf '[%s] [CAN] Starting candump on can0\n' "$(date '+%Y-%m-%d %H:%M:%S')" >>"$can_log_file"
  pkill -f "candump can0" >/dev/null 2>&1 || true
  nohup candump can0 2>&1 | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), $0; fflush(); }' >>"$can_log_file" &
  echo "[CAN] Logging CAN traffic to: $can_log_file"
}

runtime_bridge_command() {
  cat <<EOF
echo '[BRIDGE] Build and launch'
cd "$BRIDGE_DIR" || exit
make clean
make -j
./cobien_bridge "$CAN_CONFIG"
EOF
}

runtime_app_command() {
  cat <<EOF
echo '[APP] Launching frontend with uv'
cd "$FRONTEND_APP_DIR" || exit
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
if command -v "$UV_BIN" >/dev/null 2>&1; then
  "$UV_BIN" run --python "$PYTHON_REQUEST" --project "$FRONTEND_APP_DIR" mainApp.py
else
  echo '[APP] uv not found, using fallback Python'
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  fi
  "$PYTHON_BIN" mainApp.py
fi
EOF
}

runtime_can_open_terminals() {
  [[ -n "${DISPLAY:-}" ]] && command -v gnome-terminal >/dev/null 2>&1
}

runtime_launch_named_terminal() {
  local title="$1"
  local command_text="$2"
  if runtime_can_open_terminals; then
    gnome-terminal --title="$title" -- bash -lc "$command_text" || return 1
    return 0
  fi
  return 1
}

runtime_launch_background() {
  local name="$1"
  local command_text="$2"
  local log_file
  log_file="$(build_dated_log_path "$name")"
  cleanup_old_logs "$name"
  echo "[FALLBACK] Launching $name in background. Log: $log_file"
  printf '[%s] [%s] Starting background command\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$name" >>"$log_file"
  nohup bash -lc "$command_text" 2>&1 | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), $0; fflush(); }' >>"$log_file" &
}

build_dated_log_path() {
  local name="$1"
  local stamp
  stamp="$(date +%Y%m%d)"
  echo "$LOG_DIR/${name}-${stamp}.log"
}

cleanup_old_logs() {
  local name="$1"
  if [[ -d "$LOG_DIR" ]]; then
    find "$LOG_DIR" -maxdepth 1 -type f -name "${name}-*.log" -mtime +"$LOG_RETENTION_DAYS" -delete >/dev/null 2>&1 || true
  fi
}

close_runtime_windows() {
  if ! command -v wmctrl >/dev/null 2>&1; then
    return 0
  fi
  for title in "MQTT-CAN BRIDGE" "COBIEN APP"; do
    while IFS= read -r window_id; do
      [[ -n "${window_id:-}" ]] || continue
      wmctrl -ic "$window_id" >/dev/null 2>&1 || true
    done < <(wmctrl -l 2>/dev/null | awk -v title="$title" '$0 ~ title {print $1}')
  done
}

stop_runtime_processes() {
  pkill -f "candump can0" >/dev/null 2>&1 || true
  pkill -f "/cobien_bridge" >/dev/null 2>&1 || true
  pkill -f "mainApp.py" >/dev/null 2>&1 || true
  pkill -f "uv run --python .* mainApp.py" >/dev/null 2>&1 || true
  pkill -f "\\[APP\\] Launching frontend with uv" >/dev/null 2>&1 || true
  pkill -f "\\[BRIDGE\\] Build and launch" >/dev/null 2>&1 || true
  pkill -f "\\[CAN\\] Initializing the CAN bus" >/dev/null 2>&1 || true
}

count_running_runtime_processes() {
  local matches
  matches="$(pgrep -af "candump can0|/cobien_bridge|mainApp.py|\\[APP\\] Launching frontend with uv|\\[BRIDGE\\] Build and launch|\\[CAN\\] Initializing the CAN bus" || true)"
  if [[ -z "${matches//[[:space:]]/}" ]]; then
    echo 0
    return
  fi
  printf '%s\n' "$matches" | wc -l
}

perform_preflight_runtime_cleanup() {
  local running_count
  running_count="$(count_running_runtime_processes | tr -d '[:space:]')"
  if [[ "${running_count:-0}" -gt 0 ]]; then
    echo "[CLEAN] Preflight detected ${running_count} existing runtime process(es). Cleaning before relaunch..."
  else
    echo "[CLEAN] Preflight detected no previous runtime processes."
  fi
  close_runtime_windows
  stop_runtime_processes
  sleep 1
}

launch_runtime() {
  local relaunch_after_update="${1:-0}"
  check_paths
  normalize_device_identity
  ensure_device_identity_config
  ensure_runtime_dependencies
  configure_tts_runtime
  configure_audio_input_defaults
  resolve_python_bin
  resolve_uv_bin
  mkdir -p "$LOG_DIR"
  ensure_mosquitto_running

  echo "=== Launching CoBien System ==="
  echo "[PATHS] FRONTEND_REPO_ROOT=$FRONTEND_REPO_ROOT"
  echo "[PATHS] MQTT_REPO=$MQTT_REPO"
  echo "[PATHS] BRIDGE_DIR=$BRIDGE_DIR"
  echo "[PATHS] UV_BIN=$UV_BIN"
  echo "[PATHS] FRONTEND_APP_DIR=$FRONTEND_APP_DIR"
  echo "[PATHS] LOG_DIR=$LOG_DIR"
  if runtime_can_open_terminals; then
    echo "[TERM] gnome-terminal available on DISPLAY=${DISPLAY:-}"
  else
    echo "[TERM] No graphical terminal available, using fallback mode"
  fi

  if [[ "$relaunch_after_update" == "1" ]]; then
    echo "[CLEAN] Update relaunch detected."
  else
    echo "[CLEAN] Standard launch detected."
  fi
  perform_preflight_runtime_cleanup

  setup_can_bus
  start_can_logger_background

  sleep 2

  runtime_launch_background "mqtt-can-bridge" "$(runtime_bridge_command)"

  sleep 2

  runtime_launch_background "cobien-app" "$(runtime_app_command)"
}

ask() {
  local prompt="$1"
  local default_value="${2:-}"
  local answer
  if [[ "$NON_INTERACTIVE" == "1" ]]; then
    echo "$default_value"
    return
  fi
  if [[ -n "$default_value" ]]; then
    read -r -p "$prompt [$default_value]: " answer
    echo "${answer:-$default_value}"
  else
    read -r -p "$prompt: " answer
    echo "$answer"
  fi
}

ask_yes_no() {
  local prompt="$1"
  local default_value="${2:-y}"
  local suffix="[S/n]"
  local answer

  if [[ "$default_value" == "n" ]]; then
    suffix="[y/N]"
  else
    suffix="[Y/n]"
  fi

  if [[ "$NON_INTERACTIVE" == "1" ]]; then
    [[ "$default_value" != "n" ]]
    return
  fi

  while true; do
    read -r -p "$prompt $suffix: " answer
    answer="${answer:-$default_value}"
    case "${answer,,}" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
    esac
  done
}

detect_python311() {
  command -v python3.11 >/dev/null 2>&1
}

check_paths() {
  resolve_paths
  [[ -d "$FRONTEND_REPO/.git" ]] || { log "Frontend repository not found: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { log "MQTT repository not found: $MQTT_REPO"; exit 1; }
  [[ -d "$FRONTEND_APP_DIR" ]] || { log "Frontend app directory not found: $FRONTEND_APP_DIR"; exit 1; }
  [[ -d "$BRIDGE_DIR" ]] || { log "Bridge directory not found: $BRIDGE_DIR"; exit 1; }
}

checkout_branch() {
  local repo="$1"
  git -C "$repo" checkout "$BRANCH_NAME"
}

install_system_deps_fn() {
  if [[ "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    log "Skipping system dependencies"
    return
  fi

  sudo apt update
  sudo apt install -y \
    git curl wget build-essential cmake pkg-config \
    python3 python3-venv python3-pip \
    wmctrl gnome-terminal can-utils iproute2 \
    pulseaudio-utils pipewire-pulse wireplumber pavucontrol \
    mosquitto mosquitto-clients \
    libasound2-dev portaudio19-dev \
    libgl1 libegl1 libglib2.0-0 \
    libgstreamer1.0-0 gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-libav \
    libpulse0 libmosquitto-dev libcjson-dev \
    libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 \
    libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 \
    libxcomposite1 libxdamage1 libxrandr2 libnss3 \
    libatk-bridge2.0-0 libgtk-3-0

  if apt-cache show python3.11 >/dev/null 2>&1; then
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
  fi
}

ensure_runtime_dependencies() {
  local missing_packages=()
  local apt_updated="0"

  command -v git >/dev/null 2>&1 || missing_packages+=("git")
  command -v curl >/dev/null 2>&1 || missing_packages+=("curl")
  command -v wget >/dev/null 2>&1 || missing_packages+=("wget")
  command -v make >/dev/null 2>&1 || missing_packages+=("build-essential")
  command -v gcc >/dev/null 2>&1 || missing_packages+=("build-essential")
  command -v cmake >/dev/null 2>&1 || missing_packages+=("cmake")
  command -v candump >/dev/null 2>&1 || missing_packages+=("can-utils")
  command -v ip >/dev/null 2>&1 || missing_packages+=("iproute2")
  command -v pactl >/dev/null 2>&1 || missing_packages+=("pulseaudio-utils")
  dpkg -s pipewire-pulse >/dev/null 2>&1 || missing_packages+=("pipewire-pulse")
  dpkg -s wireplumber >/dev/null 2>&1 || missing_packages+=("wireplumber")
  command -v mosquitto >/dev/null 2>&1 || missing_packages+=("mosquitto" "mosquitto-clients")

  if [[ "${#missing_packages[@]}" -gt 0 ]]; then
    log "Missing runtime dependencies detected: ${missing_packages[*]}"
    log "Installing missing runtime dependencies (sudo may ask for password)..."
    sudo apt update
    apt_updated="1"
    sudo apt install -y "${missing_packages[@]}"
  fi

  if ! command -v python3.11 >/dev/null 2>&1 && apt-cache show python3.11 >/dev/null 2>&1; then
    log "Python 3.11 not found. Installing runtime Python dependencies..."
    if [[ "$apt_updated" != "1" ]]; then
      sudo apt update
      apt_updated="1"
    fi
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
  fi
}

configure_tts_runtime() {
  if [[ "$TTS_ENGINE" != "piper" ]]; then
    return 0
  fi

  if command -v piper >/dev/null 2>&1; then
    [[ -z "$TTS_PIPER_BIN" ]] && TTS_PIPER_BIN="$(command -v piper)"
    return 0
  fi

  log "Piper TTS selected but binary not found. Trying apt install..."
  sudo apt update || true
  sudo apt install -y piper-tts || true

  if command -v piper >/dev/null 2>&1; then
    [[ -z "$TTS_PIPER_BIN" ]] && TTS_PIPER_BIN="$(command -v piper)"
    log "Piper installed successfully: $TTS_PIPER_BIN"
  else
    log "Piper could not be installed automatically. Runtime will fallback to pyttsx3."
  fi
}

ensure_device_identity_config() {
  local unified_config_file
  unified_config_file="$FRONTEND_APP_DIR/config/config.json"
  mkdir -p "$(dirname "$unified_config_file")"

  if ! command -v python3 >/dev/null 2>&1; then
    log "Device identity: python3 unavailable, skipping settings.json identity sync"
    return
  fi

  python3 - "$unified_config_file" "$DEVICE_ID" "$VIDEOCALL_ROOM" "$DEVICE_LOCATION" "$TTS_ENGINE" "$TTS_PIPER_BIN" "$TTS_PIPER_MODEL_ES" "$TTS_PIPER_MODEL_FR" <<'PY'
import json
import os
import sys

config_file, device_id, videocall_room, device_location, tts_engine, tts_piper_bin, tts_piper_model_es, tts_piper_model_fr = sys.argv[1:9]
data = {}
if os.path.exists(config_file):
    try:
        with open(config_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}

if not isinstance(data, dict):
    data = {}

settings = data.get("settings")
if not isinstance(settings, dict):
    settings = {}
data["settings"] = settings

settings["device_id"] = device_id
settings["videocall_room"] = videocall_room
settings["device_location"] = device_location

services = data.get("services")
if not isinstance(services, dict):
    services = {}
data["services"] = services
services["tts_engine"] = tts_engine or "pyttsx3"
services["tts_piper_bin"] = tts_piper_bin
services["tts_piper_model_es"] = tts_piper_model_es
services["tts_piper_model_fr"] = tts_piper_model_fr

with open(config_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=4, ensure_ascii=False)
PY

  log "Device identity synced: device_id='$DEVICE_ID', videocall_room='$VIDEOCALL_ROOM', location='$DEVICE_LOCATION', tts_engine='$TTS_ENGINE'"
}

configure_audio_input_defaults() {
  local unified_config_file
  unified_config_file="$FRONTEND_APP_DIR/config/config.json"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user restart pipewire pipewire-pulse wireplumber >/dev/null 2>&1 || true
    sleep 1
  fi

  if ! command -v pactl >/dev/null 2>&1; then
    log "Audio: pactl not available, skipping audio routing setup"
    return
  fi

  local usb_card hda_source fallback_source
  usb_card="$(pactl list short cards 2>/dev/null | awk 'tolower($0) ~ /usb/ {print $2; exit}')"
  hda_source="$(pactl list short sources 2>/dev/null | awk 'tolower($0) ~ /hda|pci/ && tolower($0) ~ /input/ {print $2; exit}')"
  fallback_source="$(pactl list short sources 2>/dev/null | awk 'tolower($0) ~ /input/ && tolower($0) !~ /usb/ {print $2; exit}')"

  if [[ -n "$usb_card" ]]; then
    if pactl set-card-profile "$usb_card" output:analog-stereo >/dev/null 2>&1; then
      log "Audio: set USB card '$usb_card' profile to output:analog-stereo"
    else
      log "Audio: could not set USB profile on '$usb_card'"
    fi
  else
    log "Audio: no USB card found for profile override"
  fi

  if [[ -n "$hda_source" ]]; then
    if pactl set-default-source "$hda_source" >/dev/null 2>&1; then
      log "Audio: default input source set to '$hda_source'"
    else
      log "Audio: could not set default source '$hda_source'"
    fi
  elif [[ -n "$fallback_source" ]]; then
    if pactl set-default-source "$fallback_source" >/dev/null 2>&1; then
      log "Audio: default input source set to fallback '$fallback_source'"
    else
      log "Audio: could not set fallback source '$fallback_source'"
    fi
  else
    log "Audio: no HDA/PCH input source found"
  fi

  if [[ -f "$unified_config_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$unified_config_file" <<'PY'
import json
import sys
from pathlib import Path

config_file = Path(sys.argv[1])
try:
    data = json.loads(config_file.read_text(encoding="utf-8"))
except Exception:
    data = {}

if not isinstance(data, dict):
    data = {}

settings = data.get("settings")
if not isinstance(settings, dict):
    settings = {}
    data["settings"] = settings

settings["microphone_device"] = ""
config_file.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
PY
    log "Audio: reset microphone_device in unified config to use system default source"
  fi
}

ensure_mosquitto_running() {
  if pgrep -x mosquitto >/dev/null 2>&1; then
    log "Mosquitto already running (process detected)"
    return
  fi

  if ! command -v mosquitto >/dev/null 2>&1; then
    log "Mosquitto binary not found. Installing it now (sudo may ask for password)..."
    sudo apt update
    sudo apt install -y mosquitto mosquitto-clients
    if ! command -v mosquitto >/dev/null 2>&1; then
      log "Mosquitto installation failed or binary still unavailable."
      return
    fi
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if sudo systemctl list-unit-files --no-legend 2>/dev/null | grep -q "^mosquitto.service"; then
      if sudo systemctl is-active --quiet mosquitto; then
        log "Mosquitto already running (systemd service)"
        return
      fi

      log "Starting Mosquitto service"
      if sudo systemctl enable --now mosquitto && sudo systemctl is-active --quiet mosquitto; then
        log "Mosquitto started successfully via systemd"
        return
      fi

      log "Could not start Mosquitto via systemd, trying local process fallback"
    else
      log "mosquitto.service not found, using local process fallback"
    fi
  else
    log "systemctl not available, using local process fallback"
  fi

  local mosq_log_dir="${LOG_DIR:-/tmp}"
  local mosq_log_file="$mosq_log_dir/mosquitto-local.log"
  mkdir -p "$mosq_log_dir"
  nohup mosquitto -p 1883 >"$mosq_log_file" 2>&1 &
  sleep 1

  if pgrep -x mosquitto >/dev/null 2>&1; then
    log "Mosquitto started as local background process (log: $mosq_log_file)"
  else
    log "Failed to start Mosquitto local process. Check log: $mosq_log_file"
  fi
}

install_can_sudoers_rule() {
  local current_user sudoers_file
  current_user="$(id -un)"
  sudoers_file="/etc/sudoers.d/cobien-can"

  log "Installing passwordless CAN setup rule for user: $current_user"
  sudo /bin/sh -c "cat > '$sudoers_file' <<EOF
$current_user ALL=(root) NOPASSWD: /sbin/ip link set can0 down
$current_user ALL=(root) NOPASSWD: /sbin/ip link set can0 up
$current_user ALL=(root) NOPASSWD: /sbin/ip link set can0 type can bitrate *
EOF"
  sudo chmod 440 "$sudoers_file"
  sudo visudo -cf "$sudoers_file" >/dev/null
}

resolve_python_bin() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return
  fi

  if command -v "python${PYTHON_REQUEST}" >/dev/null 2>&1; then
    PYTHON_BIN="python${PYTHON_REQUEST}"
  elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
}

resolve_uv_bin() {
  if [[ -n "$UV_BIN" ]]; then
    return
  fi

  if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
    return
  fi

  if [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
    return
  fi

  log "Installing uv with the official Astral installer"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh

  if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
  else
    log "Could not locate uv after installation"
    exit 1
  fi
}

prepare_venv() {
  resolve_python_bin
  resolve_uv_bin

  log "Ensuring Python with uv: $PYTHON_REQUEST"
  "$UV_BIN" python install "$PYTHON_REQUEST"

  if [[ "$RECREATE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    log "Removing previous virtual environment: $VENV_DIR"
    rm -rf "$VENV_DIR"
  fi

  if [[ -d "$VENV_DIR" ]]; then
    "$UV_BIN" venv --clear --python "$PYTHON_REQUEST" "$VENV_DIR"
  else
    "$UV_BIN" venv --python "$PYTHON_REQUEST" "$VENV_DIR"
  fi
  "$UV_BIN" sync --python "$PYTHON_REQUEST" --project "$FRONTEND_APP_DIR"
}

write_env_file() {
  local settings_pin_line=""
  if [[ -n "${COBIEN_SETTINGS_PIN:-}" ]]; then
    settings_pin_line="COBIEN_SETTINGS_PIN=${COBIEN_SETTINGS_PIN}"
  fi

  cat > "$ENV_FILE" <<EOF
COBIEN_FRONTEND_REPO=$FRONTEND_REPO
COBIEN_MQTT_REPO=$MQTT_REPO
COBIEN_WORKSPACE_ROOT=$WORKSPACE_ROOT
COBIEN_UPDATE_REMOTE=$REMOTE_NAME
COBIEN_UPDATE_BRANCH=$BRANCH_NAME
COBIEN_UPDATE_INTERVAL_SEC=$POLL_INTERVAL_SEC
COBIEN_DEVICE_ID=$DEVICE_ID
COBIEN_VIDEOCALL_ROOM=$VIDEOCALL_ROOM
COBIEN_DEVICE_LOCATION=$DEVICE_LOCATION
COBIEN_TTS_ENGINE=$TTS_ENGINE
COBIEN_TTS_PIPER_BIN=$TTS_PIPER_BIN
COBIEN_TTS_PIPER_MODEL_ES=$TTS_PIPER_MODEL_ES
COBIEN_TTS_PIPER_MODEL_FR=$TTS_PIPER_MODEL_FR
COBIEN_VENV_ACTIVATE=$VENV_DIR/bin/activate
COBIEN_PYTHON_BIN=$PYTHON_BIN
COBIEN_UV_BIN=$UV_BIN
COBIEN_UV_PYTHON=$PYTHON_REQUEST
COBIEN_FRONTEND_APP_DIR=$FRONTEND_APP_DIR
COBIEN_BRIDGE_DIR=$BRIDGE_DIR
COBIEN_CAN_CONFIG=$CAN_CONFIG
$settings_pin_line
EOF
  log "Environment file generated: $ENV_FILE"
}

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
  fi
}

mark_update_applied() {
  mkdir -p "$RUNTIME_STATE_DIR"
  cat > "$UPDATE_MARKER_FILE" <<EOF
{"updated_at":"$(date -Iseconds)","message":"The system has been updated."}
EOF
  log "Update marker written: $UPDATE_MARKER_FILE"
}

is_existing_installation_ready() {
  [[ -f "$ENV_FILE" && -d "$VENV_DIR" ]]
}

setup_environment() {
  check_paths
  install_system_deps_fn
  install_can_sudoers_rule
  checkout_branch "$FRONTEND_REPO"
  checkout_branch "$MQTT_REPO"
  prepare_venv
  write_env_file
}

check_repo() {
  local repo="$1"
  [[ -d "$repo/.git" ]]
}

repo_updates_launcher() {
  local repo="$1"
  local from_sha="$2"
  local to_sha="$3"
  [[ "$repo" == "$FRONTEND_REPO" ]] || return 1
  git -C "$repo" diff --name-only "$from_sha" "$to_sha" | grep -Fxq "deploy/ubuntu/cobien-launcher.sh"
}

handoff_to_updated_launcher() {
  local next_mode="$1"

  log "Launcher script changed; re-executing updated launcher in current terminal"
  exec /bin/bash "$SELF_SCRIPT" \
    --non-interactive \
    --yes \
    --relaunch-after-update \
    --mode "$next_mode" \
    --workspace "$WORKSPACE_ROOT" \
    --frontend-name "$FRONTEND_REPO_NAME" \
    --mqtt-name "$MQTT_REPO_NAME" \
    --device-id "$DEVICE_ID" \
    --videocall-room "$VIDEOCALL_ROOM" \
    --device-location "$DEVICE_LOCATION" \
    --tts-engine "$TTS_ENGINE" \
    --tts-piper-bin "$TTS_PIPER_BIN" \
    --tts-piper-model-es "$TTS_PIPER_MODEL_ES" \
    --tts-piper-model-fr "$TTS_PIPER_MODEL_FR"
}

update_repo_if_needed() {
  local repo="$1"
  local handoff_mode="${2:-launch}"

  if ! check_repo "$repo"; then
    log "Invalid repository: $repo"
    return 2
  fi

  local current_branch local_sha remote_sha
  current_branch="$(git -C "$repo" branch --show-current)"
  if [[ "$current_branch" != "$BRANCH_NAME" ]]; then
    log "Skipping $repo: current branch '$current_branch', expected '$BRANCH_NAME'"
    return 2
  fi

  log "Checking changes in $repo"
  git -C "$repo" fetch "$REMOTE_NAME" "$BRANCH_NAME" --quiet
  local_sha="$(git -C "$repo" rev-parse HEAD)"
  remote_sha="$(git -C "$repo" rev-parse FETCH_HEAD)"

  if [[ "$local_sha" == "$remote_sha" ]]; then
    log "No changes in $repo"
    return 1
  fi

  local launcher_changed="0"
  if repo_updates_launcher "$repo" "$local_sha" "$remote_sha"; then
    launcher_changed="1"
  fi

  log "Updating $repo"
  git -C "$repo" pull --ff-only "$REMOTE_NAME" "$BRANCH_NAME"

  if [[ "$launcher_changed" == "1" ]]; then
    mark_update_applied
    handoff_to_updated_launcher "$handoff_mode"
  fi

  return 0
}

dedupe_existing_update_cron_entries() {
  local current_cron filtered seen_update
  current_cron="$(crontab -l 2>/dev/null || true)"
  seen_update="0"

  filtered="$(
    while IFS= read -r line; do
      if [[ "$line" == *"$SELF_SCRIPT --mode update-once"* ]]; then
        if [[ "$seen_update" == "0" ]]; then
          seen_update="1"
          printf "%s\n" "$line"
        fi
      else
        printf "%s\n" "$line"
      fi
    done <<<"$current_cron"
  )"

  if [[ "$filtered" != "$current_cron" ]]; then
    printf "%s\n" "$filtered" | sed '/^[[:space:]]*$/d' | crontab -
    log "Deduplicated existing update cron entries."
  fi
}

restart_software() {
  local relaunch_after_update="${1:-0}"
  log "Relaunching furniture software"
  if [[ "$relaunch_after_update" == "1" ]]; then
    exec /bin/bash "$SELF_SCRIPT" \
      --non-interactive \
      --yes \
      --relaunch-after-update \
      --mode launch \
      --workspace "$WORKSPACE_ROOT" \
      --frontend-name "$FRONTEND_REPO_NAME" \
      --mqtt-name "$MQTT_REPO_NAME" \
      --device-id "$DEVICE_ID" \
      --videocall-room "$VIDEOCALL_ROOM" \
      --device-location "$DEVICE_LOCATION" \
      --tts-engine "$TTS_ENGINE" \
      --tts-piper-bin "$TTS_PIPER_BIN" \
      --tts-piper-model-es "$TTS_PIPER_MODEL_ES" \
      --tts-piper-model-fr "$TTS_PIPER_MODEL_FR" \
      --branch "$BRANCH_NAME"
  fi
  launch_runtime 0
}

run_update_once() {
  local handoff_mode="${1:-launch}"
  local updated=0

  check_paths
  load_env_file

  if update_repo_if_needed "$FRONTEND_REPO" "$handoff_mode"; then
    updated=1
  fi

  if update_repo_if_needed "$MQTT_REPO" "$handoff_mode"; then
    updated=1
  fi

  if [[ "$updated" -eq 1 ]]; then
    mark_update_applied
    restart_software 1
  else
    log "No changes to deploy"
  fi
}

run_watch_loop() {
  check_paths
  load_env_file
  normalize_device_identity
  log "Watch mode enabled; interval ${POLL_INTERVAL_SEC}s"
  while true; do
    if ! run_update_once watch; then
      log "Execution failed; retrying in ${POLL_INTERVAL_SEC}s"
    fi
    sleep "$POLL_INTERVAL_SEC"
  done
}

install_cron_job() {
  local cron_line current_cron cron_log_file
  cron_log_file="${HOME}/cobien-update.log"
  cron_line="$CRON_SCHEDULE /bin/bash \"$SELF_SCRIPT\" --mode update-once --workspace \"$WORKSPACE_ROOT\" --frontend-name \"$FRONTEND_REPO_NAME\" --mqtt-name \"$MQTT_REPO_NAME\" >> \"$cron_log_file\" 2>&1"
  current_cron="$(crontab -l 2>/dev/null || true)"
  current_cron="$(printf '%s\n' "$current_cron" | awk -v script="$SELF_SCRIPT" 'index($0, script " --mode update-once")==0')"

  {
    printf "%s\n" "$current_cron" | sed '/^[[:space:]]*$/d'
    printf "%s\n" "$cron_line"
  } | crontab -

  log "Cron job installed (deduplicated):"
  log "  $cron_line"
}

install_systemd_user_services() {
  local installer_script="$FRONTEND_REPO/deploy/ubuntu/install-systemd-user.sh"
  if [[ ! -x "$installer_script" ]]; then
    if [[ -f "$installer_script" ]]; then
      chmod +x "$installer_script" || true
    fi
  fi

  if [[ ! -x "$installer_script" ]]; then
    log "systemd installer not found or not executable: $installer_script"
    return 1
  fi

  log "Installing/updating systemd user services..."
  /bin/bash "$installer_script"
}

has_systemd_user_launcher_service() {
  local service_file="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/cobien-launcher.service"
  [[ -f "$service_file" ]]
}

verify_systemd_user_services() {
  if ! command -v systemctl >/dev/null 2>&1; then
    log "Verification skipped: systemctl not available"
    return 1
  fi

  log "Running systemd user verification..."
  systemctl --user daemon-reload
  systemctl --user enable --now cobien-launcher.service cobien-update.timer
  systemctl --user restart cobien-launcher.service

  if systemctl --user is-active --quiet cobien-launcher.service; then
    log "Verification OK: cobien-launcher.service is active"
  else
    log "Verification FAILED: cobien-launcher.service is not active"
    return 1
  fi

  if systemctl --user is-enabled --quiet cobien-update.timer; then
    log "Verification OK: cobien-update.timer is enabled"
  else
    log "Verification FAILED: cobien-update.timer is not enabled"
    return 1
  fi
}

print_dry_run() {
  check_paths
  load_env_file
  normalize_device_identity
  log "MODE=$MODE"
  log "WORKSPACE_ROOT=$WORKSPACE_ROOT"
  log "FRONTEND_REPO=$FRONTEND_REPO"
  log "MQTT_REPO=$MQTT_REPO"
  log "FRONTEND_APP_DIR=$FRONTEND_APP_DIR"
  log "BRANCH_NAME=$BRANCH_NAME"
  log "REMOTE_NAME=$REMOTE_NAME"
  log "POLL_INTERVAL_SEC=$POLL_INTERVAL_SEC"
  log "DEVICE_ID=$DEVICE_ID"
  log "VIDEOCALL_ROOM=$VIDEOCALL_ROOM"
  log "DEVICE_LOCATION=$DEVICE_LOCATION"
  log "TTS_ENGINE=$TTS_ENGINE"
  log "TTS_PIPER_BIN=${TTS_PIPER_BIN:-auto}"
  log "TTS_PIPER_MODEL_ES=${TTS_PIPER_MODEL_ES:-unset}"
  log "TTS_PIPER_MODEL_FR=${TTS_PIPER_MODEL_FR:-unset}"
  log "ENV_FILE=$ENV_FILE"
  log "UV_BIN=${UV_BIN:-unresolved}"
  log "PYTHON_REQUEST=$PYTHON_REQUEST"
}

run_full_flow() {
  local reuse_existing_installation="0"
  local use_last_config="0"
  local first_run_without_systemd="0"
  if [[ "$NON_INTERACTIVE" != "1" ]]; then
    echo "========================================"
    echo "CoBien Ubuntu setup assistant"
    echo "========================================"
    echo
    if [[ "$ARGS_PROVIDED" == "0" ]]; then
      if ask_yes_no "Do you want to run in unattended mode with default values" "n"; then
        NON_INTERACTIVE="1"
        AUTO_CONFIRM="1"
      fi
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && load_last_run_config; then
    normalize_device_identity
    print_last_run_config_summary
    if ask_yes_no "Do you want to reuse this previous configuration and run a full reinstall" "y"; then
      use_last_config="1"
      INSTALL_SYSTEM_DEPS="1"
      RECREATE_VENV="1"
      reuse_existing_installation="0"
    fi
  fi

  if [[ "$use_last_config" != "1" ]]; then
    WORKSPACE_ROOT="$(ask "Directory containing both projects" "$WORKSPACE_ROOT")"
    FRONTEND_REPO_NAME="$(ask "Frontend repository directory name" "$FRONTEND_REPO_NAME")"
    MQTT_REPO_NAME="$(ask "MQTT repository directory name" "$MQTT_REPO_NAME")"
    normalize_device_identity
    DEVICE_ID="$(ask "Device ID (per furniture)" "$DEVICE_ID")"
    VIDEOCALL_ROOM="$(ask "Videocall room" "${VIDEOCALL_ROOM:-$DEVICE_ID}")"
    DEVICE_LOCATION="$(ask "Device location" "$DEVICE_LOCATION")"
    TTS_ENGINE="$(ask "TTS engine (pyttsx3/piper)" "$TTS_ENGINE")"
    if [[ "$TTS_ENGINE" == "piper" ]]; then
      TTS_PIPER_BIN="$(ask "Piper binary path (empty=auto detect)" "$TTS_PIPER_BIN")"
      TTS_PIPER_MODEL_ES="$(ask "Piper Spanish model path (.onnx)" "$TTS_PIPER_MODEL_ES")"
      TTS_PIPER_MODEL_FR="$(ask "Piper French model path (.onnx)" "$TTS_PIPER_MODEL_FR")"
    fi
  fi
  resolve_paths
  if ! has_systemd_user_launcher_service; then
    first_run_without_systemd="1"
    INSTALL_SYSTEMD_USER="1"
    log "First run detected: systemd user service missing, auto-install enabled."
  fi

  echo
  echo "Detected paths:"
  echo "  Frontend: $FRONTEND_REPO"
  echo "  MQTT:     $MQTT_REPO"
  echo

  [[ -d "$FRONTEND_REPO/.git" ]] || { echo "Frontend repository not found at: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { echo "MQTT repository not found at: $MQTT_REPO"; exit 1; }

  if [[ "$use_last_config" != "1" ]] && is_existing_installation_ready && [[ "$RECREATE_VENV" != "1" ]]; then
    reuse_existing_installation="1"
    INSTALL_SYSTEM_DEPS="0"
  fi

  if detect_python311; then
    echo "Python 3.11 detected: $(command -v python3.11)"
  else
    echo "Python 3.11 is not installed."
    if ask_yes_no "Should the script try to install Python 3.11 and system dependencies" "y"; then
      INSTALL_SYSTEM_DEPS="1"
    else
      echo "Cannot continue without Python 3.11."
      exit 1
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" && "$reuse_existing_installation" == "1" ]]; then
    if ask_yes_no "An existing installation was detected. Do you want to reuse it without running setup again" "y"; then
      reuse_existing_installation="1"
      INSTALL_SYSTEM_DEPS="0"
    else
      reuse_existing_installation="0"
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" && "$INSTALL_SYSTEM_DEPS" != "1" && "$reuse_existing_installation" != "1" ]]; then
    if ask_yes_no "Do you want to reinstall or verify system dependencies anyway" "y"; then
      INSTALL_SYSTEM_DEPS="1"
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" && -d "$VENV_DIR" ]]; then
    if ask_yes_no "A previous .venv was found. Do you want to remove and recreate it" "y"; then
      RECREATE_VENV="1"
    fi
  elif [[ "$NON_INTERACTIVE" != "1" ]]; then
    echo "No previous .venv found. A new one will be created."
  fi

  if [[ "$use_last_config" == "1" ]]; then
    INSTALL_SYSTEM_DEPS="1"
    RECREATE_VENV="1"
    reuse_existing_installation="0"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to run an update check before launch" "n"; then
    RUN_UPDATE_ONCE="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to keep a watcher that checks for changes every minute" "y"; then
    ENABLE_WATCH="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to install a cron job to update at specific times" "n"; then
    INSTALL_CRON="1"
    CRON_SCHEDULE="$(ask "Cron expression for updates" "$CRON_SCHEDULE")"
  fi

  if [[ "$NON_INTERACTIVE" != "1" && "$first_run_without_systemd" != "1" ]] && ask_yes_no "Do you want to install/update systemd user services for auto-start" "y"; then
    INSTALL_SYSTEMD_USER="1"
  fi

  echo
  echo "Summary:"
  echo "  Workspace:        $WORKSPACE_ROOT"
  echo "  Reuse install:    $reuse_existing_installation"
  echo "  Install deps:     $INSTALL_SYSTEM_DEPS"
  echo "  Recreate .venv:   $RECREATE_VENV"
  echo "  One-shot update:  $RUN_UPDATE_ONCE"
  echo "  Watch mode:       $ENABLE_WATCH"
  echo "  Device ID:        $DEVICE_ID"
  echo "  Videocall room:   $VIDEOCALL_ROOM"
  echo "  Device location:  $DEVICE_LOCATION"
  echo "  TTS engine:       $TTS_ENGINE"
  echo "  Install cron:     $INSTALL_CRON"
  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo "  Cron schedule:    $CRON_SCHEDULE"
  fi
  echo "  Install systemd:  $INSTALL_SYSTEMD_USER"
  echo

  if [[ "$AUTO_CONFIRM" != "1" ]] && ! ask_yes_no "Continue" "y"; then
    echo "Cancelled."
    exit 0
  fi

  echo
  if [[ "$reuse_existing_installation" == "1" ]]; then
    echo "[1/4] Reusing existing installation..."
  else
    echo "[1/4] Preparing environment..."
    setup_environment
  fi

  echo
  echo "[2/4] Loading configuration..."
  load_env_file

  echo
  echo "[3/4] Verifying configuration..."
  print_dry_run

  if [[ "$RUN_UPDATE_ONCE" == "1" ]]; then
    echo
    echo "[3b/4] Running one-shot update..."
    run_update_once
  fi

  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo
    echo "[3c/4] Installing cron job..."
    install_cron_job
  fi

  if [[ "$INSTALL_SYSTEMD_USER" == "1" ]]; then
    echo
    echo "[3d/4] Installing systemd user services..."
    install_systemd_user_services
    echo "[3e/4] Verifying systemd user services..."
    verify_systemd_user_services
  fi

  save_last_run_config

  echo
  echo "[4/4] Launching furniture system..."
  restart_software

  if [[ "$ENABLE_WATCH" == "1" ]]; then
    echo
    log "Starting watch mode..."
    run_watch_loop
  fi
}

parse_args() {
  if [[ $# -gt 0 ]]; then
    ARGS_PROVIDED="1"
  fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)
        MODE="$2"
        shift 2
        ;;
      --workspace)
        WORKSPACE_ROOT="$2"
        shift 2
        ;;
      --frontend-name)
        FRONTEND_REPO_NAME="$2"
        shift 2
        ;;
      --mqtt-name)
        MQTT_REPO_NAME="$2"
        shift 2
        ;;
      --branch)
        BRANCH_NAME="$2"
        shift 2
        ;;
      --run-update-once)
        RUN_UPDATE_ONCE="1"
        shift
        ;;
      --enable-watch)
        ENABLE_WATCH="1"
        shift
        ;;
      --install-cron)
        INSTALL_CRON="1"
        shift
        ;;
      --install-systemd-user)
        INSTALL_SYSTEMD_USER="1"
        shift
        ;;
      --cron-schedule)
        CRON_SCHEDULE="$2"
        shift 2
        ;;
      --device-id)
        DEVICE_ID="$2"
        shift 2
        ;;
      --videocall-room)
        VIDEOCALL_ROOM="$2"
        shift 2
        ;;
      --device-location)
        DEVICE_LOCATION="$2"
        shift 2
        ;;
      --tts-engine)
        TTS_ENGINE="$2"
        shift 2
        ;;
      --tts-piper-bin)
        TTS_PIPER_BIN="$2"
        shift 2
        ;;
      --tts-piper-model-es)
        TTS_PIPER_MODEL_ES="$2"
        shift 2
        ;;
      --tts-piper-model-fr)
        TTS_PIPER_MODEL_FR="$2"
        shift 2
        ;;
      --recreate-venv)
        RECREATE_VENV="1"
        shift
        ;;
      --skip-system-deps)
        INSTALL_SYSTEM_DEPS="0"
        shift
        ;;
      --non-interactive)
        NON_INTERACTIVE="1"
        shift
        ;;
      --relaunch-after-update)
        RELAUNCH_AFTER_UPDATE="1"
        shift
        ;;
      --force-restart)
        FORCE_RESTART="1"
        shift
        ;;
      --yes)
        AUTO_CONFIRM="1"
        NON_INTERACTIVE="1"
        shift
        ;;
      --once)
        MODE="update-once"
        shift
        ;;
      --watch)
        MODE="watch"
        shift
        ;;
      --dry-run)
        MODE="dry-run"
        shift
        ;;
      --launch)
        MODE="launch"
        shift
        ;;
      --setup)
        MODE="setup"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        usage
        exit 1
        ;;
    esac
  done
}

main() {
  parse_args "$@"
  acquire_single_instance_lock
  resolve_paths
  normalize_device_identity
  dedupe_existing_update_cron_entries

  case "$MODE" in
    run)
      run_full_flow
      ;;
    setup)
      setup_environment
      ;;
    update-once)
      run_update_once launch
      ;;
    watch)
      run_watch_loop
      ;;
    launch)
      check_paths
      load_env_file
      normalize_device_identity
      launch_runtime "$RELAUNCH_AFTER_UPDATE"
      log "Launch mode keeps watcher active by default."
      run_watch_loop
      ;;
    dry-run)
      print_dry_run
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
