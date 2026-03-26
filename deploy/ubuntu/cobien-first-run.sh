#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKSPACE_ROOT_DEFAULT="/home/cobien/cobien"
FRONTEND_REPO_NAME_DEFAULT="cobien_FrontEnd"
MQTT_REPO_NAME_DEFAULT="cobien_MQTT_Dictionnary"

WORKSPACE_ROOT="$WORKSPACE_ROOT_DEFAULT"
FRONTEND_REPO_NAME="$FRONTEND_REPO_NAME_DEFAULT"
MQTT_REPO_NAME="$MQTT_REPO_NAME_DEFAULT"
RUN_UPDATE_ONCE="0"
INSTALL_SYSTEM_DEPS="1"
RECREATE_VENV="0"
ENABLE_WATCH="0"
INSTALL_CRON="0"
CRON_SCHEDULE="0 3,15 * * *"

usage() {
  cat <<EOF
Uso:
  $(basename "$0")
  $(basename "$0") --workspace /home/cobien/cobien

Asistente interactivo para:
  1. pedir la carpeta donde estan los dos proyectos
  2. comprobar Python 3.11
  3. preguntar si hay que reinstalar dependencias del sistema
  4. preguntar si hay que borrar el .venv anterior
  5. preparar el entorno
  6. permitir lanzar, actualizar, activar watch o instalar cron
EOF
}

ask() {
  local prompt="$1"
  local default_value="${2:-}"
  local answer
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
  if [[ "$default_value" == "n" ]]; then
    suffix="[s/N]"
  fi

  while true; do
    read -r -p "$prompt $suffix: " answer
    answer="${answer:-$default_value}"
    case "${answer,,}" in
      s|si|sí|y|yes)
        return 0
        ;;
      n|no)
        return 1
        ;;
    esac
  done
}

detect_python311() {
  command -v python3.11 >/dev/null 2>&1
}

install_cron_job() {
  local env_file="$1"
  local update_script="$2"
  local schedule="$3"
  local cron_line="$schedule . \"$env_file\" && /bin/bash \"$update_script\" --once >> /home/cobien/cobien-update.log 2>&1"
  local current_cron

  current_cron="$(crontab -l 2>/dev/null || true)"
  if grep -Fq "$update_script --once" <<<"$current_cron"; then
    echo "[COBIEN-FIRST-RUN] Ya existe una tarea cron para el updater. No se duplica."
    return
  fi

  {
    printf "%s\n" "$current_cron"
    printf "%s\n" "$cron_line"
  } | crontab -

  echo "[COBIEN-FIRST-RUN] Cron instalado:"
  echo "  $cron_line"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  echo "========================================"
  echo "Asistente de instalacion CoBien Ubuntu"
  echo "========================================"
  echo

  WORKSPACE_ROOT="$(ask "Directorio donde estan los dos proyectos" "$WORKSPACE_ROOT_DEFAULT")"
  FRONTEND_REPO_NAME="$(ask "Nombre de la carpeta del frontend" "$FRONTEND_REPO_NAME_DEFAULT")"
  MQTT_REPO_NAME="$(ask "Nombre de la carpeta del repo MQTT" "$MQTT_REPO_NAME_DEFAULT")"

  FRONTEND_REPO="$WORKSPACE_ROOT/$FRONTEND_REPO_NAME"
  MQTT_REPO="$WORKSPACE_ROOT/$MQTT_REPO_NAME"
  ENV_FILE="$FRONTEND_REPO/deploy/ubuntu/cobien-update.env"
  BOOTSTRAP_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-bootstrap.sh"
  UPDATE_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-update.sh"
  LAUNCH_SCRIPT="$FRONTEND_REPO/CoBienICAM-main/frontend-mueble/start_cobien.sh"
  VENV_DIR="$FRONTEND_REPO/.venv"

  echo
  echo "Rutas detectadas:"
  echo "  Frontend: $FRONTEND_REPO"
  echo "  MQTT:     $MQTT_REPO"
  echo

  if [[ ! -d "$FRONTEND_REPO/.git" ]]; then
    echo "No existe repo frontend en: $FRONTEND_REPO"
    exit 1
  fi

  if [[ ! -d "$MQTT_REPO/.git" ]]; then
    echo "No existe repo MQTT en: $MQTT_REPO"
    exit 1
  fi

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

  if [[ "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    if ask_yes_no "Quieres reinstalar o verificar dependencias del sistema igualmente" "s"; then
      INSTALL_SYSTEM_DEPS="1"
    else
      INSTALL_SYSTEM_DEPS="0"
    fi
  fi

  if [[ -d "$VENV_DIR" ]]; then
    if ask_yes_no "Se ha encontrado un .venv previo. Quieres borrarlo y recrearlo" "s"; then
      RECREATE_VENV="1"
    fi
  else
    echo "No existe .venv previo. Se creara uno nuevo."
  fi

  if ask_yes_no "Quieres ejecutar una comprobacion de actualizacion antes de lanzar" "n"; then
    RUN_UPDATE_ONCE="1"
  fi

  if ask_yes_no "Quieres dejar un proceso de vigilancia que revise cambios cada minuto" "n"; then
    ENABLE_WATCH="1"
  fi

  if ask_yes_no "Quieres instalar una tarea cron para actualizar a horas concretas" "n"; then
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

  if ! ask_yes_no "Continuar" "s"; then
    echo "Cancelado."
    exit 0
  fi

  echo
  echo "[1/4] Preparando entorno..."
  BOOTSTRAP_ARGS=(--workspace "$WORKSPACE_ROOT" --frontend-name "$FRONTEND_REPO_NAME" --mqtt-name "$MQTT_REPO_NAME")
  if [[ "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    BOOTSTRAP_ARGS+=(--skip-system-deps)
  fi
  if [[ "$RECREATE_VENV" == "1" ]]; then
    BOOTSTRAP_ARGS+=(--recreate-venv)
  fi
  bash "$BOOTSTRAP_SCRIPT" "${BOOTSTRAP_ARGS[@]}"

  echo
  echo "[2/4] Cargando configuracion..."
  set -a
  source "$ENV_FILE"
  set +a

  echo
  echo "[3/4] Verificando updater..."
  bash "$UPDATE_SCRIPT" --dry-run

  if [[ "$RUN_UPDATE_ONCE" == "1" ]]; then
    echo
    echo "[3b/4] Ejecutando update puntual..."
    bash "$UPDATE_SCRIPT" --once
  fi

  if [[ "$INSTALL_CRON" == "1" ]]; then
    echo
    echo "[3c/4] Instalando cron..."
    install_cron_job "$ENV_FILE" "$UPDATE_SCRIPT" "$CRON_SCHEDULE"
  fi

  echo
  echo "[4/4] Lanzando sistema del mueble..."
  bash "$LAUNCH_SCRIPT"

  if [[ "$ENABLE_WATCH" == "1" ]]; then
    echo
    echo "[COBIEN-FIRST-RUN] Arrancando updater en modo watch..."
    bash "$UPDATE_SCRIPT" --watch
  fi
}

main "$@"
