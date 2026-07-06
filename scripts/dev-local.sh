#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

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
uv run uvicorn memrise_api.main:app --host 0.0.0.0 --port 8000 --reload &
echo "Starting worker"
uv run memrise-worker &
echo "Starting web on http://localhost:3000"
pnpm --filter @memrise/web dev &

wait
