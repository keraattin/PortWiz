#!/usr/bin/env bash
#
# PortWiz installer. Asks how you want to run it, then hands off to the Docker or
# native deploy script. You can also skip the prompt:
#   ./deploy.sh docker [--updater --ai]   # Docker, optionally with add-ons
#   ./deploy.sh native                     # without Docker
#
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-}"
[ -n "$MODE" ] && shift

if [ -z "$MODE" ]; then
  if [ ! -t 0 ]; then
    echo "Non-interactive: run '$0 docker' or '$0 native'." >&2
    exit 1
  fi
  echo "How do you want to run PortWiz?"
  echo "  1) Docker  (recommended, simplest)"
  echo "  2) Without Docker (native)"
  read -rp "Choose [1/2] (default 1): " ans || ans=1
  case "${ans:-1}" in
    1|docker) MODE=docker ;;
    2|native) MODE=native ;;
    *) echo "Invalid choice." >&2; exit 1 ;;
  esac
fi

case "$MODE" in
  docker) exec ./deploy-docker.sh "$@" ;;
  native) exec ./deploy-native.sh "$@" ;;
  *) echo "Usage: $0 [docker|native] [options]" >&2; exit 1 ;;
esac
