from __future__ import annotations

import os
import subprocess
from pathlib import Path

PYTHON_SUFFIXES = {".py"}
PRETTIER_SUFFIXES = {
    ".css",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
TS_SUFFIXES = {".js", ".jsx", ".mjs", ".ts", ".tsx"}
PRETTIER_EXCLUDES = {
    "docs/openapi.json",
    "pnpm-lock.yaml",
    "uv.lock",
}
PRETTIER_EXCLUDE_PARTS = {
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    "playwright-report",
    "test-results",
}


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    env = os.environ.copy()
    if command and command[0] == "uv":
        env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
        env.setdefault("UV_PYTHON_INSTALL_DIR", "/tmp/uv-python")
    subprocess.run(command, check=True, env=env)


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line and Path(line).exists()]


def prettier_file(path: str) -> bool:
    file_path = Path(path)
    if path in PRETTIER_EXCLUDES:
        return False
    if any(part in PRETTIER_EXCLUDE_PARTS for part in file_path.parts):
        return False
    if path.startswith("packages/sdk-typescript/src/generated/"):
        return False
    return file_path.suffix in PRETTIER_SUFFIXES


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    try:
        python_files = [path for path in files if Path(path).suffix in PYTHON_SUFFIXES]
        if python_files:
            run(["uv", "run", "ruff", "format", "--check", *python_files])
            run(["uv", "run", "ruff", "check", *python_files])
            run(["uv", "run", "pyright"])

        prettier_files = [path for path in files if prettier_file(path)]
        if prettier_files:
            run(["pnpm", "exec", "prettier", "--check", "--ignore-unknown", *prettier_files])

        ts_files = [path for path in files if Path(path).suffix in TS_SUFFIXES]
        if ts_files:
            run(["pnpm", "--filter", "@memrise/web", "lint"])
            run(["pnpm", "--recursive", "typecheck"])
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
