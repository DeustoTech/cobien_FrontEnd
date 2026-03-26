#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="/home/cobien/cobien"
FRONTEND_REPO_NAME="cobien_FrontEnd"
MQTT_REPO_NAME="cobien_MQTT_Dictionnary"
RUN_UPDATE_ONCE="0"

usage() {
  cat <<EOF
Uso:
  $(basename "$0") [--workspace /home/cobien/cobien] [--run-update-once]

Hace automaticamente:
  1. bootstrap del entorno Ubuntu
  2. carga de cobien-update.env
  3. dry-run del updater
  4. lanzamiento del sistema del mueble
  5. opcionalmente una pasada de updater --once
EOF
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
    --run-update-once)
      RUN_UPDATE_ONCE="1"
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
ENV_FILE="$FRONTEND_REPO/deploy/ubuntu/cobien-update.env"
BOOTSTRAP_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-bootstrap.sh"
UPDATE_SCRIPT="$FRONTEND_REPO/deploy/ubuntu/cobien-update.sh"
LAUNCH_SCRIPT="$FRONTEND_REPO/CoBienICAM-main/frontend-mueble/start_cobien.sh"

echo "[COBIEN-FIRST-RUN] Workspace: $WORKSPACE_ROOT"
echo "[COBIEN-FIRST-RUN] Frontend repo: $FRONTEND_REPO"

bash "$BOOTSTRAP_SCRIPT" \
  --workspace "$WORKSPACE_ROOT" \
  --frontend-name "$FRONTEND_REPO_NAME" \
  --mqtt-name "$MQTT_REPO_NAME"

set -a
source "$ENV_FILE"
set +a

echo "[COBIEN-FIRST-RUN] Verificando configuracion updater"
bash "$UPDATE_SCRIPT" --dry-run

if [[ "$RUN_UPDATE_ONCE" == "1" ]]; then
  echo "[COBIEN-FIRST-RUN] Ejecutando updater puntual"
  bash "$UPDATE_SCRIPT" --once
fi

echo "[COBIEN-FIRST-RUN] Lanzando sistema del mueble"
bash "$LAUNCH_SCRIPT"
