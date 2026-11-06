#!/bin/sh
set -eu

export PATH="/Applications/Docker.app/Contents/Resources/bin:$HOME/.docker/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

tool_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$tool_dir/../.." && pwd)
gui_url="http://127.0.0.1:8766"
preview_dir="$repo_root/tmp/llm-preview-20261027-1zyclbhd"
export BIOTECH_SOURCE_ROOT="$repo_root"
export DEMO_RUNTIME_DIR="$repo_root/tmp/demo-update-20261106"
if [ ! -f "$DEMO_RUNTIME_DIR/demo-state.json" ]; then
  echo "Prepare the demo first with tools/local_db/start-demo.command."
  exit 1
fi
DEMO_DB_NAME=$(sed -n 's/.*"database": "\([a-zA-Z0-9_]*\)".*/\1/p' "$DEMO_RUNTIME_DIR/demo-state.json")
export DEMO_DB_NAME

compose() {
  docker compose \
    --project-name biotech-llm-preview-20261027 \
    --env-file "$preview_dir/.preview.env" \
    -f "$preview_dir/compose.preview.yml" \
    -f "$tool_dir/compose.demo.yml" \
    "$@"
}

gui_failed() {
  echo "Recent container output:"
  compose logs --tail 50 local-db-gui || true
  compose stop local-db-gui >/dev/null 2>&1 || true
  exit 1
}

prepare_gui_reload() {
  metadata=""
  if ! metadata=$(curl --silent --fail --max-time 2 "$gui_url/api/config" 2>/dev/null); then
    running_gui=""
    if ! running_gui=$(compose ps --status running --quiet local-db-gui 2>/dev/null); then
      echo "The current GUI container state could not be inspected safely."
      return 1
    fi
    if [ -n "$running_gui" ]; then
      echo "The running GUI API could not be reached safely."
      return 1
    fi
    return 0
  fi
  token=${metadata#*'"csrf_token": "'}
  if [ "$token" = "$metadata" ]; then
    echo "The running GUI did not return a local request token."
    return 1
  fi
  token=${token%%\"*}
  if [ -z "$token" ]; then
    echo "The running GUI returned an empty local request token."
    return 1
  fi

  if ! prepare_status=$(curl \
    --silent \
    --output /dev/null \
    --write-out '%{http_code}' \
    --max-time 2 \
    --request POST \
    --header "Origin: $gui_url" \
    --header 'Content-Type: application/json' \
    --header "X-Local-DB-Token: $token" \
    --data '{"confirm_restart":true}' \
    "$gui_url/api/prepare-restart"); then
    echo "The running GUI could not be prepared safely for reload."
    return 1
  fi

  case "$prepare_status" in
    200) return 0 ;;
    409) return 2 ;;
    404) return 3 ;;
    *)
      echo "The running GUI rejected the safe-reload handshake (HTTP $prepare_status)."
      return 1
      ;;
  esac
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available on PATH."
  echo "Install/start Docker Desktop, then run this launcher again."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is not available on PATH and is required for the local health check."
  exit 1
fi

if [ -n "${DOCKER_CONTEXT:-}" ] && [ -n "${DOCKER_HOST:-}" ]; then
  echo "Both DOCKER_CONTEXT and DOCKER_HOST are set."
  echo "Clear one override so the launcher can verify the effective local endpoint."
  exit 1
fi
if [ -n "${DOCKER_HOST:-}" ]; then
  docker_endpoint=$DOCKER_HOST
else
  if ! docker_endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null); then
    echo "The active Docker context could not be inspected."
    exit 1
  fi
fi
case "$docker_endpoint" in
  unix://*) ;;
  *)
    echo "Refusing to send this repository to a non-local Docker endpoint: $docker_endpoint"
    echo "Switch to a local Docker Desktop context, then run this launcher again."
    exit 1
    ;;
esac

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running or is not accessible."
  echo "Start Docker Desktop, then run this launcher again."
  exit 1
fi

job_payload=""
if job_payload=$(curl --silent --fail --max-time 2 "$gui_url/api/job" 2>/dev/null); then
  case "$job_payload" in
    *'"state": "queued"'*|*'"state":"queued"'*|*'"state": "running"'*|*'"state":"running"'*)
      echo "A local database generation job is currently queued or running."
      echo "Wait for it to finish before running this launcher again."
      exit 1
      ;;
  esac
fi

echo "Building the BIOTech local dataset GUI..."
if ! compose build local-db-gui; then
  echo "Docker Compose could not build the GUI image."
  exit 1
fi

echo "Ensuring the local PostgreSQL service is healthy..."
if ! compose up --detach --wait --no-recreate postgres; then
  echo "Docker Compose could not start a healthy local PostgreSQL service."
  exit 1
fi

prepare_result=0
prepare_gui_reload || prepare_result=$?
case "$prepare_result" in
  0) ;;
  2)
    echo "A generation job or another GUI reload is currently active."
    echo "Wait for it to finish before running this launcher again."
    exit 1
    ;;
  3)
    echo "The running GUI predates atomic safe-reload support."
    echo "Stop only local-db-gui once, then run this launcher again."
    exit 1
    ;;
  *) exit 1 ;;
esac

echo "Recreating only the GUI so it uses the current checkout..."
if ! compose up --detach --force-recreate --no-deps local-db-gui; then
  echo "Docker Compose could not recreate the GUI."
  gui_failed
fi

attempt=0
while [ "$attempt" -lt 60 ]; do
  if curl --silent --show-error --fail --max-time 1 "$gui_url/api/health" >/dev/null 2>&1; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 0.5
done

if [ "$attempt" -ge 60 ]; then
  echo "The GUI did not become ready at $gui_url."
  gui_failed
fi

echo "GUI ready / 生成器已就绪: $gui_url"
if [ "${LOCAL_DB_GUI_SKIP_OPEN:-0}" = "1" ]; then
  exit 0
fi
python3 -B - "$tool_dir" "$gui_url/" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from demo import open_demo_browser
open_demo_browser(sys.argv[2])
PY
