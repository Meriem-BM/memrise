#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

run() {
  printf '+ %s\n' "$*"
  if [[ "${1:-}" == "uv" ]]; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/tmp/uv-python}" \
      "$@"
  else
    "$@"
  fi
}

prettier_file() {
  local path="$1"
  local part

  case "$path" in
    contracts/openapi.json | pnpm-lock.yaml | uv.lock) return 1 ;;
  esac
  IFS=/ read -ra parts <<< "$path"
  for part in "${parts[@]}"; do
    case "$part" in
      node_modules | .next | dist | build | coverage | playwright-report | test-results) return 1 ;;
    esac
  done
  case "$path" in
    packages/sdk-typescript/src/generated/*) return 1 ;;
  esac
  case "$path" in
    *.css | *.js | *.json | *.jsx | *.md | *.mjs | *.ts | *.tsx | *.yaml | *.yml) return 0 ;;
  esac
  return 1
}

files=()
while IFS= read -r path; do
  [[ -n "$path" && -e "$path" ]] && files+=("$path")
done < <(git diff --cached --name-only --diff-filter=ACMR)

if ((${#files[@]} == 0)); then
  exit 0
fi

python_files=()
prettier_files=()
ts_files=()
for path in "${files[@]}"; do
  case "$path" in
    *.py) python_files+=("$path") ;;
  esac
  if prettier_file "$path"; then
    prettier_files+=("$path")
  fi
  case "$path" in
    *.js | *.jsx | *.mjs | *.ts | *.tsx) ts_files+=("$path") ;;
  esac
done

if ((${#python_files[@]} > 0)); then
  run uv run ruff format --check "${python_files[@]}"
  run uv run ruff check "${python_files[@]}"
  run uv run pyright
fi

if ((${#prettier_files[@]} > 0)); then
  run pnpm exec prettier --check --ignore-unknown "${prettier_files[@]}"
fi

if ((${#ts_files[@]} > 0)); then
  run pnpm --filter @memrise/web lint
  run pnpm --recursive typecheck
fi