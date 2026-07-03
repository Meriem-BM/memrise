#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

UV_ENV=(env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/tmp/uv-python}")

cleanup() {
  local exit_code=$?
  local pids
  pids="$(jobs -p || true)"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

echo "Starting API on http://localhost:8000"
"${UV_ENV[@]}" uv run uvicorn memrise_api.main:app --host 0.0.0.0 --port 8000 --reload &
echo "Starting worker"
"${UV_ENV[@]}" uv run memrise-worker &
echo "Starting web on http://localhost:3000"
pnpm --filter @memrise/web dev &

wait
