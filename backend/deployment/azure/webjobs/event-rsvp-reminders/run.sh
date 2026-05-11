#!/bin/bash
set -euo pipefail

APP_ROOT="/home/site/wwwroot"
BACKEND_ROOT="${APP_ROOT}/backend"

if [ ! -f "${BACKEND_ROOT}/manage.py" ]; then
  echo "Expected Django manage.py at ${BACKEND_ROOT}/manage.py" >&2
  exit 1
fi

cd "${BACKEND_ROOT}"

if [ -x "${BACKEND_ROOT}/.venv/bin/python" ]; then
  PYTHON_BIN="${BACKEND_ROOT}/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "No python interpreter found on PATH." >&2
  exit 1
fi

# The reminder
# behavior itself lives in the Django management command so local/test/Azure
# invocations all execute the same code path.
exec "${PYTHON_BIN}" manage.py send_event_rsvp_reminders --settings=config.settings "$@"
