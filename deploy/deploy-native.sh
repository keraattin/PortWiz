#!/usr/bin/env bash
#
# Deploy PortWiz without Docker (native). Guided: checks prerequisites, sets up
# the API (virtualenv, dependencies, database migrations), optionally builds the
# web UI and scan agent, and writes systemd units for the app processes.
#
# The database (PostgreSQL with the TimescaleDB extension) and the broker
# (Valkey/Redis) are prerequisites. The simplest way to provide them is to run
# just those two with Docker (from deploy/: docker compose up -d db valkey), or
# install them natively. Point the URLs in apps/api/.env at them.
#
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
WEB_DIR="$REPO_ROOT/apps/web"
AGENT_DIR="$REPO_ROOT/apps/agent"

say()  { printf '\n== %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

say "Checking prerequisites"
MISSING=0
if have python3; then echo "  python3: $(python3 --version)"; else echo "  python3: MISSING (need 3.11+)"; MISSING=1; fi
have node   && echo "  node: $(node --version)"  || echo "  node: not found (needed only to build the web UI)"
have go     && echo "  go: $(go version)"        || echo "  go: not found (needed only to build the scan agent)"
have docker && echo "  docker: available (can host the database + broker)" \
            || echo "  docker: not found (provide PostgreSQL+TimescaleDB and Valkey yourself)"
[ "$MISSING" = "1" ] && { echo "Install the missing prerequisites and re-run." >&2; exit 1; }

say "Setting up the API (apps/api)"
cd "$API_DIR"
if [ ! -f .env ]; then
  echo "No apps/api/.env found. Create one with at least:"
  cat <<'EOF'
  PORTWIZ_DATABASE_URL=postgresql+asyncpg://portwiz:portwiz@localhost:5432/portwiz
  PORTWIZ_CELERY_BROKER_URL=redis://localhost:6379/0
  PORTWIZ_CELERY_RESULT_BACKEND=redis://localhost:6379/1
  PORTWIZ_SECRET_KEY=change-me            # openssl rand -hex 32
  PORTWIZ_FIRST_ADMIN_EMAIL=admin@example.com
  PORTWIZ_FIRST_ADMIN_PASSWORD=choose-a-strong-password
EOF
  echo "Then re-run this script."
  exit 1
fi
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e .
echo "Applying database migrations..."
alembic upgrade head

if have node; then
  say "Building the web UI (apps/web)"
  cd "$WEB_DIR"
  npm ci
  VITE_API_BASE_URL="" npm run build
  echo "Built apps/web/dist. Serve it with your web server, proxying /api and /health to the API."
else
  echo "Skipping web build (node not found)."
fi

if have go; then
  say "Building the scan agent (apps/agent)"
  cd "$AGENT_DIR"
  go build -trimpath -o portwiz-agent ./cmd/agent
  echo "Built apps/agent/portwiz-agent. Enroll an agent in the UI, then run it with the token."
else
  echo "Skipping agent build (go not found)."
fi

say "Writing systemd units to deploy/systemd/"
UNIT_DIR="$REPO_ROOT/deploy/systemd"
mkdir -p "$UNIT_DIR"
USER_NAME="$(id -un)"
VENV="$API_DIR/.venv/bin"

_unit() {  # name  description  execstart
  cat > "$UNIT_DIR/$1" <<EOF
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$API_DIR
EnvironmentFile=$API_DIR/.env
ExecStart=$3
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

_unit portwiz-api.service "PortWiz API" \
  "$VENV/uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000"
_unit portwiz-worker.service "PortWiz Celery worker" \
  "$VENV/celery -A portwiz_api.workers.celery_app.celery_app worker --loglevel=info"
_unit portwiz-beat.service "PortWiz Celery beat scheduler" \
  "$VENV/celery -A portwiz_api.workers.celery_app.celery_app beat --loglevel=info --schedule=$API_DIR/celerybeat-schedule"

say "Done"
cat <<EOF
Native app components are ready. To run them as services:
  sudo cp $UNIT_DIR/portwiz-*.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now portwiz-api portwiz-worker portwiz-beat

The database (PostgreSQL + TimescaleDB) and broker (Valkey/Redis) must be running
and reachable at the URLs in apps/api/.env. Serve apps/web/dist with your web
server (proxying /api and /health to the API), and deploy at least one agent.
EOF
