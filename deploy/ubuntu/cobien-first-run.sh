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

usage() {
  cat <<EOF
Uso:
  $(basename "$0")
  $(basename "$0") --workspace /home/cobien/cobien
  $(basename "$0") --mode setup --workspace /home/cobien/cobien
  $(basename "$0") --mode update-once
  $(basename "$0") --mode watch
  $(basename "$0") --mode launch
  $(basename "$0") --mode dry-run

Modos:
  run           Flujo completo interactivo o desatendido
  setup         Solo prepara dependencias, uv, Python y .venv
  update-once   Busca cambios y relanza si actualiza
  watch         Busca cambios cada minuto
  launch        Lanza el sistema del mueble
  dry-run       Muestra la configuracion resuelta

Opciones:
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
  CAN_CONFIG="$BRIDGE_DIR/config/conversion.json"
  LAUNCH_SCRIPT="$FRONTEND_APP_DIR/start_cobien.sh"
  SELF_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-first-run.sh"
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
  local default_value="${2:-s}"
  local suffix="[S/n]"
  local answer

  if [[ "$default_value" == "n" ]]; then
    suffix="[s/N]"
  fi

  if [[ "$NON_INTERACTIVE" == "1" ]]; then
    [[ "$default_value" != "n" ]]
    return
  fi

  while true; do
    read -r -p "$prompt $suffix: " answer
    answer="${answer:-$default_value}"
    case "${answer,,}" in
      s|si|sí|y|yes) return 0 ;;
      n|no) return 1 ;;
    esac
  done
}

detect_python311() {
  command -v python3.11 >/dev/null 2>&1
}

check_paths() {
  resolve_paths
  [[ -d "$FRONTEND_REPO/.git" ]] || { log "No existe repo frontend: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { log "No existe repo mqtt: $MQTT_REPO"; exit 1; }
  [[ -d "$FRONTEND_APP_DIR" ]] || { log "No existe app frontend: $FRONTEND_APP_DIR"; exit 1; }
  [[ -d "$BRIDGE_DIR" ]] || { log "No existe bridge dir: $BRIDGE_DIR"; exit 1; }
}

checkout_branch() {
  local repo="$1"
  git -C "$repo" checkout "$BRANCH_NAME"
}

install_system_deps_fn() {
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

  log "Instalando uv con el instalador oficial de Astral"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh

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

  log "Asegurando Python con uv: $PYTHON_REQUEST"
  "$UV_BIN" python install "$PYTHON_REQUEST"

  if [[ "$RECREATE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    log "Eliminando entorno virtual previo: $VENV_DIR"
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
COBIEN_LAUNCH_SCRIPT=$LAUNCH_SCRIPT
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
  log "Fichero de entorno generado: $ENV_FILE"
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
    log "Repo no valido: $repo"
    return 2
  fi

  local current_branch local_sha remote_sha
  current_branch="$(git -C "$repo" branch --show-current)"
  if [[ "$current_branch" != "$BRANCH_NAME" ]]; then
    log "Saltando $repo: rama actual '$current_branch', esperada '$BRANCH_NAME'"
    return 2
  fi

  log "Consultando cambios en $repo"
  git -C "$repo" fetch "$REMOTE_NAME" "$BRANCH_NAME" --quiet
  local_sha="$(git -C "$repo" rev-parse HEAD)"
  remote_sha="$(git -C "$repo" rev-parse FETCH_HEAD)"

  if [[ "$local_sha" == "$remote_sha" ]]; then
    log "Sin cambios en $repo"
    return 1
  fi

  log "Actualizando $repo"
  git -C "$repo" pull --ff-only "$REMOTE_NAME" "$BRANCH_NAME"
  return 0
}

restart_software() {
  if [[ ! -x "$LAUNCH_SCRIPT" ]]; then
    log "Launch script no ejecutable o no encontrado: $LAUNCH_SCRIPT"
    return 1
  fi

  log "Relanzando software del mueble"
  bash "$LAUNCH_SCRIPT"
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
    log "No hay cambios para desplegar"
  fi
}

run_watch_loop() {
  check_paths
  load_env_file
  log "Modo watch activo; intervalo ${POLL_INTERVAL_SEC}s"
  while true; do
    if ! run_update_once; then
      log "Ejecucion con error; reintentando en ${POLL_INTERVAL_SEC}s"
    fi
    sleep "$POLL_INTERVAL_SEC"
  done
}

install_cron_job() {
  local cron_line current_cron
  cron_line="$CRON_SCHEDULE /bin/bash \"$SELF_SCRIPT\" --mode update-once --workspace \"$WORKSPACE_ROOT\" --frontend-name \"$FRONTEND_REPO_NAME\" --mqtt-name \"$MQTT_REPO_NAME\" >> /home/cobien/cobien-update.log 2>&1"
  current_cron="$(crontab -l 2>/dev/null || true)"

  if grep -Fq "$SELF_SCRIPT --mode update-once" <<<"$current_cron"; then
    log "Ya existe una tarea cron para la actualizacion. No se duplica."
    return
  fi

  {
    printf "%s\n" "$current_cron"
    printf "%s\n" "$cron_line"
  } | crontab -

  log "Cron instalado:"
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
  log "LAUNCH_SCRIPT=$LAUNCH_SCRIPT"
  log "BRANCH_NAME=$BRANCH_NAME"
  log "REMOTE_NAME=$REMOTE_NAME"
  log "POLL_INTERVAL_SEC=$POLL_INTERVAL_SEC"
  log "ENV_FILE=$ENV_FILE"
  log "UV_BIN=${UV_BIN:-sin resolver}"
  log "PYTHON_REQUEST=$PYTHON_REQUEST"
}

run_full_flow() {
  if [[ "$NON_INTERACTIVE" != "1" ]]; then
    echo "========================================"
    echo "Asistente de instalacion CoBien Ubuntu"
    echo "========================================"
    echo
  fi

  WORKSPACE_ROOT="$(ask "Directorio donde estan los dos proyectos" "$WORKSPACE_ROOT")"
  FRONTEND_REPO_NAME="$(ask "Nombre de la carpeta del frontend" "$FRONTEND_REPO_NAME")"
  MQTT_REPO_NAME="$(ask "Nombre de la carpeta del repo MQTT" "$MQTT_REPO_NAME")"
  resolve_paths

  echo
  echo "Rutas detectadas:"
  echo "  Frontend: $FRONTEND_REPO"
  echo "  MQTT:     $MQTT_REPO"
  echo

  [[ -d "$FRONTEND_REPO/.git" ]] || { echo "No existe repo frontend en: $FRONTEND_REPO"; exit 1; }
  [[ -d "$MQTT_REPO/.git" ]] || { echo "No existe repo MQTT en: $MQTT_REPO"; exit 1; }

  if detect_python311; then
    echo "Python 3.11 detectado: $(command -v python3.11)"
  else
    echo "Python 3.11 no esta instalado."
    if ask_yes_no "Quieres que el script intente instalar Python 3.11 y dependencias del sistema" "s"; then
      INSTALL_SYSTEM_DEPS="1"
    else
      echo "No se puede continuar sin Python 3.11."
      exit 1
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" && "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    if ask_yes_no "Quieres reinstalar o verificar dependencias del sistema igualmente" "s"; then
      INSTALL_SYSTEM_DEPS="1"
    fi
  fi

  if [[ "$NON_INTERACTIVE" != "1" && -d "$VENV_DIR" ]]; then
    if ask_yes_no "Se ha encontrado un .venv previo. Quieres borrarlo y recrearlo" "s"; then
      RECREATE_VENV="1"
    fi
  elif [[ "$NON_INTERACTIVE" != "1" ]]; then
    echo "No existe .venv previo. Se creara uno nuevo."
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Quieres ejecutar una comprobacion de actualizacion antes de lanzar" "n"; then
    RUN_UPDATE_ONCE="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Quieres dejar un proceso de vigilancia que revise cambios cada minuto" "n"; then
    ENABLE_WATCH="1"
  fi

  if [[ "$NON_INTERACTIVE" != "1" ]] && ask_yes_no "Quieres instalar una tarea cron para actualizar a horas concretas" "n"; then
    INSTALL_CRON="1"
    CRON_SCHEDULE="$(ask "Expresion cron para la actualizacion" "$CRON_SCHEDULE")"
  fi

  echo
  echo "Resumen:"
  echo "  Workspace:        $WORKSPACE_ROOT"
  echo "  Instalar deps:    $INSTALL_SYSTEM_DEPS"
  echo "  Recrear .venv:    $RECREATE_VENV"
  echo "  Update puntual:   $RUN_UPDATE_ONCE"
  echo "  Watch cada min:   $ENABLE_WATCH"
  echo "  Instalar cron:    $INSTALL_CRON"
  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo "  Cron schedule:    $CRON_SCHEDULE"
  fi
  echo

  if [[ "$AUTO_CONFIRM" != "1" ]] && ! ask_yes_no "Continuar" "s"; then
    echo "Cancelado."
    exit 0
  fi

  echo
  echo "[1/4] Preparando entorno..."
  setup_environment

  echo
  echo "[2/4] Cargando configuracion..."
  load_env_file

  echo
  echo "[3/4] Verificando configuracion..."
  print_dry_run

  if [[ "$RUN_UPDATE_ONCE" == "1" ]]; then
    echo
    echo "[3b/4] Ejecutando update puntual..."
    run_update_once
  fi

  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo
    echo "[3c/4] Instalando cron..."
    install_cron_job
  fi

  echo
  echo "[4/4] Lanzando sistema del mueble..."
  restart_software

  if [[ "$ENABLE_WATCH" == "1" ]]; then
    echo
    log "Arrancando updater en modo watch..."
    run_watch_loop
  fi
}

parse_args() {
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
