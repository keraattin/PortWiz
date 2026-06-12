#!/usr/bin/env sh
set -e

command="${1:-api}"

case "$command" in
  api)
    echo "[entrypoint] applying migrations..."
    alembic upgrade head
    echo "[entrypoint] starting API..."
    if [ -n "$UVICORN_RELOAD" ]; then
      exec uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000 --reload
    else
      exec uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000
    fi
    ;;
  worker)
    exec celery -A portwiz_api.workers.celery_app.celery_app worker --loglevel=info
    ;;
  beat)
    exec celery -A portwiz_api.workers.celery_app.celery_app beat --loglevel=info
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
