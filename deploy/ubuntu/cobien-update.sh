#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="update-once"
case "${1:---once}" in
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
  -h|--help)
    exec /bin/bash "$SCRIPT_DIR/cobien-launcher.sh" --help
    ;;
esac

exec /bin/bash "$SCRIPT_DIR/cobien-launcher.sh" --mode "$MODE" "$@"
