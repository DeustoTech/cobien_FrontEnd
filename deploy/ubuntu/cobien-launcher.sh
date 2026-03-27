#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKSPACE_ROOT_DEFAULT="/home/cobien/cobien"
FRONTEND_REPO_NAME_DEFAULT="cobien_FrontEnd"
MQTT_REPO_NAME_DEFAULT="cobien_MQTT_Dictionnary"
BRANCH_NAME_DEFAULT="development_fix"
CRON_SCHEDULE_DEFAULT="0 3,15 * * *"
POLL_INTERVAL_DEFAULT="60"

MODE="run"
WORKSPACE_ROOT="${COBIEN_WORKSPACE_ROOT:-$WORKSPACE_ROOT_DEFAULT}"
FRONTEND_REPO_NAME="${COBIEN_FRONTEND_REPO_NAME:-$FRONTEND_REPO_NAME_DEFAULT}"
MQTT_REPO_NAME="${COBIEN_MQTT_REPO_NAME:-$MQTT_REPO_NAME_DEFAULT}"
BRANCH_NAME="${COBIEN_UPDATE_BRANCH:-$BRANCH_NAME_DEFAULT}"
RUN_UPDATE_ONCE="${COBIEN_RUN_UPDATE_ONCE:-0}"
INSTALL_SYSTEM_DEPS="${COBIEN_INSTALL_SYSTEM_DEPS:-1}"
RECREATE_VENV="${COBIEN_RECREATE_VENV:-0}"
ENABLE_WATCH="${COBIEN_ENABLE_WATCH:-0}"
INSTALL_CRON="${COBIEN_INSTALL_CRON:-0}"
CRON_SCHEDULE="${COBIEN_CRON_SCHEDULE:-$CRON_SCHEDULE_DEFAULT}"
NON_INTERACTIVE="${COBIEN_NON_INTERACTIVE:-0}"
AUTO_CONFIRM="${COBIEN_AUTO_CONFIRM:-0}"
REMOTE_NAME="${COBIEN_UPDATE_REMOTE:-origin}"
POLL_INTERVAL_SEC="${COBIEN_UPDATE_INTERVAL_SEC:-$POLL_INTERVAL_DEFAULT}"
PYTHON_BIN="${COBIEN_BOOTSTRAP_PYTHON_BIN:-}"
UV_BIN="${COBIEN_BOOTSTRAP_UV_BIN:-}"
PYTHON_REQUEST="${COBIEN_BOOTSTRAP_PYTHON_VERSION:-3.11}"
ARGS_PROVIDED="0"

usage() {
  cat <<EOF
Usage:
  $(basename "$0")
  $(basename "$0") --workspace /home/cobien/cobien
  $(basename "$0") --mode setup --workspace /home/cobien/cobien
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
  --cron-schedule "0 3,15 * * *"
  --recreate-venv
  --skip-system-deps
  --non-interactive
  --yes
  -h, --help
EOF
}

log() {
  echo "[COBIEN] $*"
}

resolve_paths() {
  FRONTEND_REPO="$WORKSPACE_ROOT/$FRONTEND_REPO_NAME"
  MQTT_REPO="$WORKSPACE_ROOT/$MQTT_REPO_NAME"
  FRONTEND_APP_DIR="$FRONTEND_REPO/CoBienICAM-main/frontend-mueble"
  VENV_DIR="$FRONTEND_REPO/.venv"
  ENV_FILE="$FRONTEND_REPO/deploy/ubuntu/cobien-update.env"
  BRIDGE_DIR="$MQTT_REPO/Interface_MQTT_CAN_c"
  CAN_CONFIG="$BRIDGE_DIR/conversion.json"
  SELF_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-launcher.sh"
  FRONTEND_REPO_ROOT="$FRONTEND_REPO"
  LOG_DIR="${COBIEN_LOG_DIR:-$FRONTEND_REPO_ROOT/logs}"
}

runtime_can_command() {
  cat <<EOF
echo '[CAN] Initializing the CAN bus'
sudo -n /sbin/ip link set can0 down
sudo -n /sbin/ip link set can0 type can bitrate ${COBIEN_CAN_BITRATE:-500000}
sudo -n /sbin/ip link set can0 up
echo '[CAN] candump active'
candump can0
exec bash
EOF
}

runtime_bridge_command() {
  cat <<EOF
echo '[BRIDGE] Build and launch'
cd "$BRIDGE_DIR" || exit
make clean
make -j
./cobien_bridge "$CAN_CONFIG"
exec bash
EOF
}

runtime_app_command() {
  cat <<EOF
echo '[APP] Launching frontend with uv'
cd "$FRONTEND_APP_DIR" || exit
if command -v "$UV_BIN" >/dev/null 2>&1; then
  "$UV_BIN" run --python "$PYTHON_REQUEST" --project "$FRONTEND_APP_DIR" mainApp.py
else
  echo '[APP] uv not found, using fallback Python'
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  fi
  "$PYTHON_BIN" mainApp.py
fi
exec bash
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
  local log_file="$LOG_DIR/${name}.log"
  echo "[FALLBACK] Launching $name in background. Log: $log_file"
  nohup bash -lc "$command_text" >"$log_file" 2>&1 &
}

launch_runtime() {
  check_paths
  resolve_python_bin
  resolve_uv_bin
  mkdir -p "$LOG_DIR"

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

  echo "[CLEAN] Closing previous CoBien terminals..."
  for title in "CAN BUS" "MQTT-CAN BRIDGE" "COBIEN APP"; do
    window_id="$(wmctrl -l 2>/dev/null | awk -v title="$title" '$0 ~ title {print $1; exit}')"
    if [[ -n "${window_id:-}" ]]; then
      wmctrl -ic "$window_id" >/dev/null 2>&1 || true
    fi
  done
  pkill -f "candump can0" >/dev/null 2>&1 || true
  pkill -f "/cobien_bridge" >/dev/null 2>&1 || true
  pkill -f "mainApp.py" >/dev/null 2>&1 || true

  sleep 1

  if ! runtime_launch_named_terminal "CAN BUS" "$(runtime_can_command)"; then
    runtime_launch_background "can-bus" "$(runtime_can_command)"
  fi

  sleep 2

  if ! runtime_launch_named_terminal "MQTT-CAN BRIDGE" "$(runtime_bridge_command)"; then
    runtime_launch_background "mqtt-can-bridge" "$(runtime_bridge_command)"
  fi

  sleep 2

  if ! runtime_launch_named_terminal "COBIEN APP" "$(runtime_app_command)"; then
    echo "[APP] Launching in current shell"
    bash -lc "$(runtime_app_command)"
  fi
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

  "$UV_BIN" venv --python "$PYTHON_REQUEST" "$VENV_DIR"
  "$UV_BIN" sync --python "$PYTHON_REQUEST" --project "$FRONTEND_APP_DIR"
}

write_env_file() {
  cat > "$ENV_FILE" <<EOF
COBIEN_FRONTEND_REPO=$FRONTEND_REPO
COBIEN_MQTT_REPO=$MQTT_REPO
COBIEN_WORKSPACE_ROOT=$WORKSPACE_ROOT
COBIEN_UPDATE_REMOTE=$REMOTE_NAME
COBIEN_UPDATE_BRANCH=$BRANCH_NAME
COBIEN_UPDATE_INTERVAL_SEC=$POLL_INTERVAL_SEC
COBIEN_VENV_ACTIVATE=$VENV_DIR/bin/activate
COBIEN_PYTHON_BIN=$PYTHON_BIN
COBIEN_UV_BIN=$UV_BIN
COBIEN_UV_PYTHON=$PYTHON_REQUEST
COBIEN_FRONTEND_APP_DIR=$FRONTEND_APP_DIR
COBIEN_BRIDGE_DIR=$BRIDGE_DIR
COBIEN_CAN_CONFIG=$CAN_CONFIG
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

update_repo_if_needed() {
  local repo="$1"

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

  log "Updating $repo"
  git -C "$repo" pull --ff-only "$REMOTE_NAME" "$BRANCH_NAME"
  return 0
}

restart_software() {
  log "Relaunching furniture software"
  launch_runtime
}

run_update_once() {
  local updated=0

  check_paths
  load_env_file

  if update_repo_if_needed "$FRONTEND_REPO"; then
    updated=1
  fi

  if update_repo_if_needed "$MQTT_REPO"; then
    updated=1
  fi

  if [[ "$updated" -eq 1 ]]; then
    restart_software
  else
    log "No changes to deploy"
  fi
}

run_watch_loop() {
  check_paths
  load_env_file
  log "Watch mode enabled; interval ${POLL_INTERVAL_SEC}s"
  while true; do
    if ! run_update_once; then
      log "Execution failed; retrying in ${POLL_INTERVAL_SEC}s"
    fi
    sleep "$POLL_INTERVAL_SEC"
  done
}

install_cron_job() {
  local cron_line current_cron
  cron_line="$CRON_SCHEDULE /bin/bash \"$SELF_SCRIPT\" --mode update-once --workspace \"$WORKSPACE_ROOT\" --frontend-name \"$FRONTEND_REPO_NAME\" --mqtt-name \"$MQTT_REPO_NAME\" >> /home/cobien/cobien-update.log 2>&1"
  current_cron="$(crontab -l 2>/dev/null || true)"

  if grep -Fq "$SELF_SCRIPT --mode update-once" <<<"$current_cron"; then
    log "A cron job for updates already exists. Skipping duplicate."
    return
  fi

  {
    printf "%s\n" "$current_cron"
    printf "%s\n" "$cron_line"
  } | crontab -

  log "Cron job installed:"
  log "  $cron_line"
}

print_dry_run() {
  check_paths
  load_env_file
  log "MODE=$MODE"
  log "WORKSPACE_ROOT=$WORKSPACE_ROOT"
  log "FRONTEND_REPO=$FRONTEND_REPO"
  log "MQTT_REPO=$MQTT_REPO"
  log "FRONTEND_APP_DIR=$FRONTEND_APP_DIR"
  log "BRANCH_NAME=$BRANCH_NAME"
  log "REMOTE_NAME=$REMOTE_NAME"
  log "POLL_INTERVAL_SEC=$POLL_INTERVAL_SEC"
  log "ENV_FILE=$ENV_FILE"
  log "UV_BIN=${UV_BIN:-unresolved}"
  log "PYTHON_REQUEST=$PYTHON_REQUEST"
}

run_full_flow() {
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

  WORKSPACE_ROOT="$(ask "Directory containing both projects" "$WORKSPACE_ROOT")"
  FRONTEND_REPO_NAME="$(ask "Frontend repository directory name" "$FRONTEND_REPO_NAME")"
  MQTT_REPO_NAME="$(ask "MQTT repository directory name" "$MQTT_REPO_NAME")"
  resolve_paths

  echo
  echo "Detected paths:"
  echo "  Frontend: $FRONTEND_REPO"
  echo "  MQTT:     $MQTT_REPO"
  echo

  [[ -d "$FRONTEND_REPO/.git" ]] || { echo "Frontend repository not found at: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { echo "MQTT repository not found at: $MQTT_REPO"; exit 1; }

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

  if [[ "$NON_INTERACTIVE" != "1" && "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
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

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to run an update check before launch" "n"; then
    RUN_UPDATE_ONCE="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to keep a watcher that checks for changes every minute" "n"; then
    ENABLE_WATCH="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Do you want to install a cron job to update at specific times" "n"; then
    INSTALL_CRON="1"
    CRON_SCHEDULE="$(ask "Cron expression for updates" "$CRON_SCHEDULE")"
  fi

  echo
  echo "Summary:"
  echo "  Workspace:        $WORKSPACE_ROOT"
  echo "  Install deps:     $INSTALL_SYSTEM_DEPS"
  echo "  Recreate .venv:   $RECREATE_VENV"
  echo "  One-shot update:  $RUN_UPDATE_ONCE"
  echo "  Watch mode:       $ENABLE_WATCH"
  echo "  Install cron:     $INSTALL_CRON"
  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo "  Cron schedule:    $CRON_SCHEDULE"
  fi
  echo

  if [[ "$AUTO_CONFIRM" != "1" ]] && ! ask_yes_no "Continue" "y"; then
    echo "Cancelled."
    exit 0
  fi

  echo
  echo "[1/4] Preparing environment..."
  setup_environment

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
      --cron-schedule)
        CRON_SCHEDULE="$2"
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
  resolve_paths

  case "$MODE" in
    run)
      run_full_flow
      ;;
    setup)
      setup_environment
      ;;
    update-once)
      run_update_once
      ;;
    watch)
      run_watch_loop
      ;;
    launch)
      check_paths
      load_env_file
      restart_software
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
