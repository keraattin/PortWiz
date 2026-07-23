#!/usr/bin/env bash
#
# Deploy PortWiz with Docker (production stack). Interactive by default: it asks
# which optional pieces to include. Or pass flags (handy for automation):
#   ./deploy-docker.sh                 # interactive (asks about updater and AI)
#   ./deploy-docker.sh --core          # core only, no prompts
#   ./deploy-docker.sh --updater --ai  # core + updater + local AI
#   BUILD=0 ./deploy-docker.sh --updater   # use prebuilt registry images
#
# Core services: database, broker, API, worker, scheduler, web UI.
#
set -euo pipefail
cd "$(dirname "$0")"

WANT_UPDATER=0
WANT_AI=0
INTERACTIVE=1

for arg in "$@"; do
  case "$arg" in
    --updater) WANT_UPDATER=1; INTERACTIVE=0 ;;
    --ai)      WANT_AI=1;      INTERACTIVE=0 ;;
    --core)    INTERACTIVE=0 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

if [ ! -f .env.prod ]; then
  cp .env.prod.example .env.prod
  echo "Created .env.prod from the example."
  echo "Edit it (strong secrets, DB password, admin, SMTP), then run this again." >&2
  exit 1
fi

# Only prompt when interactive and attached to a terminal.
if [ "$INTERACTIVE" = "1" ] && [ -t 0 ]; then
  echo "PortWiz core: database, broker, API, worker, scheduler, and web UI."
  echo "Optional add-ons:"
  read -rp "  One-click updater (in-UI 'Update now')? [y/N]: " a1 || a1=n
  [[ "${a1:-n}" =~ ^[Yy] ]] && WANT_UPDATER=1
  read -rp "  Local AI (Ollama, needs extra RAM)? [y/N]: " a2 || a2=n
  [[ "${a2:-n}" =~ ^[Yy] ]] && WANT_AI=1
fi

PROFILES=""
[ "$WANT_UPDATER" = "1" ] && PROFILES="updater"
[ "$WANT_AI" = "1" ] && PROFILES="${PROFILES:+$PROFILES,}ai"

# Record the profiles so the systemd unit brings the same set back up.
export COMPOSE_PROFILES="$PROFILES"
echo "COMPOSE_PROFILES=$PROFILES" > .env.deploy

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
BUILD="${BUILD:-1}"

echo "Deploying with Docker (updater=$WANT_UPDATER, local AI=$WANT_AI, build=$BUILD)..."
if [ "$BUILD" = "1" ]; then
  "${COMPOSE[@]}" up -d --build --remove-orphans
else
  "${COMPOSE[@]}" pull
  "${COMPOSE[@]}" up -d --remove-orphans
fi

echo
echo "PortWiz is starting. Open the web UI on host port \${WEB_PORT:-8080}."
echo "Enroll at least one agent from the UI (Agents) so it can scan a network."
if [ "$WANT_UPDATER" = "1" ]; then
  echo
  echo "Updater: set PORTWIZ_UPDATE_APPLY_ENABLED=true and PORTWIZ_API_IMAGE /"
  echo "PORTWIZ_WEB_IMAGE (registry images) in .env.prod for in-UI updates to work."
fi
if [ "$WANT_AI" = "1" ]; then
  echo
  echo "Local AI: set PORTWIZ_AI_PROVIDER=ollama in .env.prod, then pull a model:"
  echo "  ${COMPOSE[*]} exec ollama ollama pull qwen2.5:3b"
fi
