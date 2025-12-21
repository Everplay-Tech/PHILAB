#!/usr/bin/env sh
set -eu

port="${PORT:-8080}"

if [ "${PHILAB_AUTO_MIGRATE:-false}" = "true" ]; then
  echo "[philab] Running alembic migrations..."
  tries=0
  max_tries="${PHILAB_MIGRATE_MAX_RETRIES:-15}"
  sleep_seconds="${PHILAB_MIGRATE_RETRY_SLEEP_SECONDS:-4}"

  while :; do
    tries=$((tries + 1))
    if python -m alembic -c alembic.ini upgrade head; then
      echo "[philab] Migrations complete."
      break
    fi
    if [ "$tries" -ge "$max_tries" ]; then
      echo "[philab] Migrations failed after $tries attempts." >&2
      exit 1
    fi
    echo "[philab] Migration attempt $tries failed; retrying in ${sleep_seconds}s..." >&2
    sleep "$sleep_seconds"
  done
fi

exec uvicorn phi2_lab.platform.api:app --host 0.0.0.0 --port "$port"

