#!/usr/bin/env bash
# Run Django migrations using local dev settings (Postgres via POSTGRES_* / settings_local).
# Usage (from anywhere):
#   backend/scripts/db_migrate.sh
#   backend/scripts/db_migrate.sh migrate --plan
#   backend/scripts/db_migrate.sh makemigrations

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_local}"

if [[ ! -f "$ROOT/manage.py" ]]; then
  echo "Expected manage.py at $ROOT/manage.py" >&2
  exit 1
fi

if [[ -f "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

exec "$PYTHON" manage.py "$@"
