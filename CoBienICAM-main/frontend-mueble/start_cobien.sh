#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAUNCHER_SCRIPT="$FRONTEND_REPO_ROOT/deploy/ubuntu/cobien-launcher.sh"

if [[ ! -x "$LAUNCHER_SCRIPT" ]]; then
  echo "[COMPAT] Launcher script not found or not executable: $LAUNCHER_SCRIPT" >&2
  exit 1
fi

exec /bin/bash "$LAUNCHER_SCRIPT" --mode launch "$@"
