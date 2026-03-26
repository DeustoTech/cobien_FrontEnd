#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_REPO="${COBIEN_FRONTEND_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
WORKSPACE_ROOT="${COBIEN_WORKSPACE_ROOT:-$(cd "$FRONTEND_REPO/.." && pwd)}"
MQTT_REPO="${COBIEN_MQTT_REPO:-$WORKSPACE_ROOT/cobien_MQTT_Dictionnary}"
FRONTEND_APP_DIR="${COBIEN_FRONTEND_APP_DIR:-$FRONTEND_REPO/CoBienICAM-main/frontend-mueble}"
LAUNCH_SCRIPT="${COBIEN_LAUNCH_SCRIPT:-$FRONTEND_APP_DIR/start_cobien.sh}"
REMOTE_NAME="${COBIEN_UPDATE_REMOTE:-origin}"
BRANCH_NAME="${COBIEN_UPDATE_BRANCH:-development_fix}"
POLL_INTERVAL_SEC="${COBIEN_UPDATE_INTERVAL_SEC:-60}"
LOG_PREFIX="[COBIEN-UPDATER]"

usage() {
  cat <<EOF
Uso:
  $(basename "$0") --once
  $(basename "$0") --watch
  $(basename "$0") --dry-run

Variables opcionales:
  COBIEN_FRONTEND_REPO
  COBIEN_MQTT_REPO
  COBIEN_LAUNCH_SCRIPT
  COBIEN_UPDATE_REMOTE
  COBIEN_UPDATE_BRANCH
  COBIEN_UPDATE_INTERVAL_SEC
EOF
}

log() {
  echo "$LOG_PREFIX $*"
}

check_repo() {
  local repo="$1"
  if [[ ! -d "$repo/.git" ]]; then
    log "Repo no válido: $repo"
    return 1
  fi
}

update_repo_if_needed() {
  local repo="$1"
  check_repo "$repo"

  local current_branch
  current_branch="$(git -C "$repo" branch --show-current)"
  if [[ "$current_branch" != "$BRANCH_NAME" ]]; then
    log "Saltando $repo: rama actual '$current_branch', esperada '$BRANCH_NAME'"
    return 2
  fi

  log "Consultando cambios en $repo"
  git -C "$repo" fetch "$REMOTE_NAME" "$BRANCH_NAME" --quiet

  local local_sha remote_sha
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

run_once() {
  local updated=0

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

run_watch() {
  log "Modo watch activo; intervalo ${POLL_INTERVAL_SEC}s"
  while true; do
    if ! run_once; then
      log "Ejecución con error; reintentando en ${POLL_INTERVAL_SEC}s"
    fi
    sleep "$POLL_INTERVAL_SEC"
  done
}

main() {
  local mode="${1:---once}"
  case "$mode" in
    --once)
      run_once
      ;;
    --watch)
      run_watch
      ;;
    --dry-run)
      log "FRONTEND_REPO=$FRONTEND_REPO"
      log "MQTT_REPO=$MQTT_REPO"
      log "LAUNCH_SCRIPT=$LAUNCH_SCRIPT"
      log "REMOTE_NAME=$REMOTE_NAME"
      log "BRANCH_NAME=$BRANCH_NAME"
      log "POLL_INTERVAL_SEC=$POLL_INTERVAL_SEC"
      ;;
    -h|--help)
      usage
      ;;
    *)
      usage
      return 1
      ;;
  esac
}

main "$@"
