#!/usr/bin/env bash
#
# PortWiz production deployment helper. Brings the stack up at one of three
# tiers so you can match the deployment to the host and your needs:
#
#   min    Core control plane only: db, valkey, api, worker, beat, web.
#          Lowest resources. Use a cloud AI provider or no AI; update manually.
#   med    Core + the one-click updater (in-UI "Update now").
#   full   Everything: core + updater + local AI (Ollama). Self-contained,
#          no external AI dependency. Needs extra RAM for the model.
#
# Usage:
#   ./deploy.sh [min|med|full]      # default: min
#   BUILD=0 ./deploy.sh full        # use prebuilt registry images instead of building
#
set -euo pipefail
cd "$(dirname "$0")"

TIER="${1:-min}"
BUILD="${BUILD:-1}"

case "$TIER" in
  min)  PROFILES="" ;;
  med)  PROFILES="updater" ;;
  full) PROFILES="updater,ai" ;;
  *) echo "Unknown tier '$TIER'. Use one of: min | med | full" >&2; exit 1 ;;
esac

if [ ! -f .env.prod ]; then
  cp .env.prod.example .env.prod
  echo "Created .env.prod from the example." >&2
  echo "Edit it (strong secrets, DB password, admin, SMTP), then run this script again." >&2
  exit 1
fi

# Record the active profiles so the systemd unit brings the same tier back up.
export COMPOSE_PROFILES="$PROFILES"
echo "COMPOSE_PROFILES=$PROFILES" > .env.deploy

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)

echo "Deploying PortWiz (tier: $TIER, build: $BUILD)..."
if [ "$BUILD" = "1" ]; then
  "${COMPOSE[@]}" up -d --build --remove-orphans
else
  "${COMPOSE[@]}" pull
  "${COMPOSE[@]}" up -d --remove-orphans
fi

echo
echo "PortWiz is starting. Open the web UI on host port \${WEB_PORT:-8080}."
echo "Enroll at least one agent from the UI (Agents) so the app can scan a network."

if [ "$TIER" = "med" ] || [ "$TIER" = "full" ]; then
  echo
  echo "Updater enabled. For in-UI updates, set in .env.prod:"
  echo "  PORTWIZ_UPDATE_APPLY_ENABLED=true"
  echo "  PORTWIZ_API_IMAGE / PORTWIZ_WEB_IMAGE pointing at your registry images"
  echo "(the updater pulls new images; with local builds, update via 'git pull' + re-run)."
fi

if [ "$TIER" = "full" ]; then
  echo
  echo "Local AI (Ollama) enabled. Set PORTWIZ_AI_PROVIDER=ollama in .env.prod, then"
  echo "pull a model, e.g.:"
  echo "  docker compose -f docker-compose.prod.yml --env-file .env.prod exec ollama ollama pull qwen2.5:3b"
fi
