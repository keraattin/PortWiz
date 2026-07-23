#!/usr/bin/env bash
#
# Fill placeholder secrets in .env.prod (or a file you pass as $1) with strong
# random values. Only values that still look like placeholders (change-me,
# dev-insecure, portwiz:portwiz@) are touched, so it is safe to re-run.
#
#   ./gen-secrets.sh              # edits .env.prod (creates it from the example if missing)
#   ./gen-secrets.sh .env.prod
#
set -euo pipefail
cd "$(dirname "$0")"

FILE="${1:-.env.prod}"
if [ ! -f "$FILE" ]; then
  cp .env.prod.example "$FILE"
  echo "Created $FILE from the example."
fi
cp "$FILE" "$FILE.bak"
echo "Backed up to $FILE.bak"

gen_hex()    { openssl rand -hex "$1"; }
gen_fernet() { openssl rand -base64 32 | tr '+/' '-_'; }   # urlsafe base64 = valid Fernet key

_value() { grep -E "^$1=" "$FILE" | head -1 | cut -d= -f2-; }

is_placeholder() {
  local cur; cur="$(_value "$1")"
  [ -z "$cur" ] && return 0
  echo "$cur" | grep -qiE "change-me|dev-insecure|portwiz:portwiz@"
}

set_var() {  # KEY VALUE  (| delimiter; generated values never contain |, & or /)
  if grep -qE "^$1=" "$FILE"; then
    sed -i "s|^$1=.*|$1=$2|" "$FILE"
  else
    printf '%s=%s\n' "$1" "$2" >> "$FILE"
  fi
}

CHANGED=()

if is_placeholder PORTWIZ_SECRET_KEY; then
  set_var PORTWIZ_SECRET_KEY "$(gen_hex 32)"; CHANGED+=(PORTWIZ_SECRET_KEY)
fi
if is_placeholder PORTWIZ_ENCRYPTION_KEY; then
  set_var PORTWIZ_ENCRYPTION_KEY "$(gen_fernet)"; CHANGED+=(PORTWIZ_ENCRYPTION_KEY)
fi

# The DB password lives in two places and must match, so regenerate both together.
if is_placeholder POSTGRES_PASSWORD || is_placeholder PORTWIZ_DATABASE_URL; then
  DBPASS="$(gen_hex 24)"
  DBUSER="$(_value POSTGRES_USER)"; DBUSER="${DBUSER:-portwiz}"
  DBNAME="$(_value POSTGRES_DB)";   DBNAME="${DBNAME:-portwiz}"
  set_var POSTGRES_PASSWORD "$DBPASS"
  set_var PORTWIZ_DATABASE_URL "postgresql+asyncpg://${DBUSER}:${DBPASS}@db:5432/${DBNAME}"
  CHANGED+=(POSTGRES_PASSWORD PORTWIZ_DATABASE_URL)
fi

ADMIN_PW=""
if is_placeholder PORTWIZ_FIRST_ADMIN_PASSWORD; then
  ADMIN_PW="$(gen_hex 12)"
  set_var PORTWIZ_FIRST_ADMIN_PASSWORD "$ADMIN_PW"; CHANGED+=(PORTWIZ_FIRST_ADMIN_PASSWORD)
fi

echo
echo "Updated: ${CHANGED[*]:-nothing (no placeholders found)}"
if [ -n "$ADMIN_PW" ]; then
  ADMIN_EMAIL="$(_value PORTWIZ_FIRST_ADMIN_EMAIL)"
  echo
  echo "  Admin login (also saved in $FILE, write it down now):"
  echo "    email:    ${ADMIN_EMAIL:-admin@portwiz.local}"
  echo "    password: $ADMIN_PW"
fi

echo
# Only inspect real KEY=value lines, so prose in comments does not false-alarm.
REMAINING="$(grep -nE '^[[:space:]]*[A-Za-z_]+=' "$FILE" \
  | grep -iE "change-me|dev-insecure|portwiz:portwiz@" || true)"
if [ -n "$REMAINING" ]; then
  echo "WARNING: placeholders still remain (review these):"
  echo "$REMAINING"
else
  echo "No placeholders remain."
fi

echo
echo "Next: if the database was already started once with the old password, reset"
echo "its volume (safe on a fresh install), then deploy:"
echo "  docker compose -f docker-compose.prod.yml --env-file $FILE down -v"
echo "  bash deploy.sh docker"
