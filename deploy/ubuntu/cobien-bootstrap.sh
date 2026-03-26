#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_FRONTEND_REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_WORKSPACE_ROOT="$(cd "$DEFAULT_FRONTEND_REPO/.." && pwd)"

WORKSPACE_ROOT="$DEFAULT_WORKSPACE_ROOT"
FRONTEND_REPO_NAME="cobien_FrontEnd"
MQTT_REPO_NAME="cobien_MQTT_Dictionnary"
BRANCH_NAME="development_fix"
INSTALL_SYSTEM_DEPS="1"
RECREATE_VENV="0"

usage() {
  cat <<EOF
Uso:
  $(basename "$0") --workspace /home/cobien/cobien

Opciones:
  --workspace PATH            Carpeta que contiene ambos repositorios
  --frontend-name NAME        Nombre carpeta repo frontend (default: cobien_FrontEnd)
  --mqtt-name NAME            Nombre carpeta repo mqtt (default: cobien_MQTT_Dictionnary)
  --branch NAME               Rama objetivo (default: development_fix)
  --skip-system-deps          No instala paquetes apt
  --recreate-venv             Borra y recrea .venv
  -h, --help                  Muestra esta ayuda
EOF
}

log() {
  echo "[COBIEN-BOOTSTRAP] $*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --skip-system-deps)
      INSTALL_SYSTEM_DEPS="0"
      shift
      ;;
    --recreate-venv)
      RECREATE_VENV="1"
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

FRONTEND_REPO="$WORKSPACE_ROOT/$FRONTEND_REPO_NAME"
MQTT_REPO="$WORKSPACE_ROOT/$MQTT_REPO_NAME"
FRONTEND_APP_DIR="$FRONTEND_REPO/CoBienICAM-main/frontend-mueble"
VENV_DIR="$FRONTEND_REPO/.venv"
ENV_FILE="$FRONTEND_REPO/deploy/ubuntu/cobien-update.env"
BRIDGE_DIR="$MQTT_REPO/Interface_MQTT_CAN_c"
CAN_CONFIG="$BRIDGE_DIR/config/conversion.json"
PYTHON_BIN="${COBIEN_BOOTSTRAP_PYTHON_BIN:-}"
UV_BIN="${COBIEN_BOOTSTRAP_UV_BIN:-}"

check_paths() {
  [[ -d "$FRONTEND_REPO/.git" ]] || { log "No existe repo frontend: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { log "No existe repo mqtt: $MQTT_REPO"; exit 1; }
  [[ -d "$FRONTEND_APP_DIR" ]] || { log "No existe app frontend: $FRONTEND_APP_DIR"; exit 1; }
  [[ -d "$BRIDGE_DIR" ]] || { log "No existe bridge dir: $BRIDGE_DIR"; exit 1; }
}

checkout_branch() {
  local repo="$1"
  git -C "$repo" checkout "$BRANCH_NAME"
}

install_system_deps() {
  if [[ "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    log "Saltando dependencias del sistema"
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

resolve_python_bin() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return
  fi

  if command -v python3.11 >/dev/null 2>&1; then
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

  resolve_python_bin
  log "Instalando uv para $PYTHON_BIN"
  "$PYTHON_BIN" -m pip install --user --upgrade uv

  if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
  else
    log "No se pudo localizar uv tras la instalacion"
    exit 1
  fi
}

prepare_venv() {
  resolve_python_bin
  resolve_uv_bin

  if "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] <= (3, 11) else 1)'; then
    :
  else
    log "Python seleccionado: $PYTHON_BIN"
    log "Este proyecto no esta estabilizado sobre Python 3.12+. Instala python3.11 o exporta COBIEN_BOOTSTRAP_PYTHON_BIN=python3.11"
    exit 1
  fi

  if [[ "$RECREATE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    log "Eliminando entorno virtual previo: $VENV_DIR"
    rm -rf "$VENV_DIR"
  fi

  "$UV_BIN" venv --python "$PYTHON_BIN" "$VENV_DIR"
  "$UV_BIN" sync --python "$PYTHON_BIN" --project "$FRONTEND_APP_DIR"
}

write_env_file() {
  cat > "$ENV_FILE" <<EOF
COBIEN_FRONTEND_REPO=$FRONTEND_REPO
COBIEN_MQTT_REPO=$MQTT_REPO
COBIEN_WORKSPACE_ROOT=$WORKSPACE_ROOT
COBIEN_LAUNCH_SCRIPT=$FRONTEND_APP_DIR/start_cobien.sh
COBIEN_UPDATE_REMOTE=origin
COBIEN_UPDATE_BRANCH=$BRANCH_NAME
COBIEN_UPDATE_INTERVAL_SEC=60
COBIEN_VENV_ACTIVATE=$VENV_DIR/bin/activate
COBIEN_PYTHON_BIN=$PYTHON_BIN
COBIEN_UV_BIN=$UV_BIN
COBIEN_BRIDGE_DIR=$BRIDGE_DIR
COBIEN_CAN_CONFIG=$CAN_CONFIG
EOF
  log "Fichero de entorno generado: $ENV_FILE"
}

main() {
  check_paths
  install_system_deps
  checkout_branch "$FRONTEND_REPO"
  checkout_branch "$MQTT_REPO"
  prepare_venv
  write_env_file

  log "Preparacion completada"
  log "Workspace: $WORKSPACE_ROOT"
  log "Frontend:  $FRONTEND_REPO"
  log "MQTT:      $MQTT_REPO"
  log "Env file:  $ENV_FILE"
  log "Python:    $PYTHON_BIN"
  log "uv:        $UV_BIN"
  log "Lanzar sistema:"
  log "  bash \"$FRONTEND_APP_DIR/start_cobien.sh\""
  log "Lanzar updater una vez:"
  log "  set -a && source \"$ENV_FILE\" && set +a && bash \"$FRONTEND_REPO/deploy/ubuntu/cobien-update.sh\" --once"
  log "Lanzar updater watch:"
  log "  set -a && source \"$ENV_FILE\" && set +a && bash \"$FRONTEND_REPO/deploy/ubuntu/cobien-update.sh\" --watch"
}

main
