#!/bin/sh
# PortWiz updater sidecar (opt-in). Watches the app_settings.update_requested_at
# flag that the API sets when an admin clicks "Update now" in the UI, then pulls
# the new images and recreates the stack.
#
# This container holds the Docker socket on purpose: the API deliberately does
# NOT, so a compromised API can never touch Docker. One-click apply therefore
# requires deploying this sidecar (`--profile updater`) AND setting
# PORTWIZ_UPDATE_APPLY_ENABLED=true so the API offers the button.
#
# For the pull to actually fetch new code, deploy with registry images
# (PORTWIZ_API_IMAGE / PORTWIZ_WEB_IMAGE pointing at ghcr.io/<owner>/portwiz-*),
# not the local-build defaults. A build-based deployment has nothing to pull.
set -eu

INTERVAL="${PORTWIZ_UPDATER_INTERVAL:-30}"
COMPOSE_FILE="${PORTWIZ_COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${PORTWIZ_ENV_FILE:-.env.prod}"
DB_HOST="${PORTWIZ_DB_HOST:-db}"
FLAG_KEY="update_requested_at"

export PGPASSWORD="${POSTGRES_PASSWORD}"
PSQL="psql -h ${DB_HOST} -U ${POSTGRES_USER} -d ${POSTGRES_DB:-portwiz} -tAq"

# docker CLI + compose plugin ship in docker:cli; add psql once at startup.
if ! command -v psql >/dev/null 2>&1; then
  apk add --no-cache postgresql-client >/dev/null
fi

compose() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

log() { echo "[updater] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

log "watching for update requests (every ${INTERVAL}s)"
last=""
while true; do
  req="$(${PSQL} -c "SELECT value FROM app_settings WHERE key='${FLAG_KEY}'" 2>/dev/null || true)"
  if [ -n "${req}" ] && [ "${req}" != "${last}" ]; then
    last="${req}"
    log "update requested at ${req}; pulling images"
    if compose pull; then
      # Ack the request BEFORE recreating, so if `up -d` also recreates this
      # sidecar (rare: only if its own image changed) we do not reapply in a
      # loop. A failed pull leaves the flag set so the admin can retry.
      ${PSQL} -c "DELETE FROM app_settings WHERE key='${FLAG_KEY}'" >/dev/null 2>&1 || true
      if compose up -d; then
        log "update applied"
      else
        log "recreate failed; images pulled but stack unchanged (retry from the UI)"
      fi
    else
      log "pull failed; will retry on the next request"
    fi
  fi
  sleep "${INTERVAL}"
done
