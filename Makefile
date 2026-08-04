# Use uv's default (persistent) Python + cache locations. The old /tmp dirs got
# purged on reboot, breaking the venv. Override UV_ENV in ephemeral CI if wanted,
# e.g. `make check UV_ENV="UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python"`.
UV_ENV ?=
COMPOSE=docker compose -f infra/compose.yaml

.PHONY: bootstrap install-hooks dev dev-local stop logs format format-check lint typecheck test test-integration test-e2e check build package-check db-reset postgres-up migrate migration export-openapi generate-sdk benchmark-retrieval

bootstrap:
	$(UV_ENV) uv sync --all-packages
	pnpm install --frozen-lockfile
	git config core.hooksPath .githooks

install-hooks:
	git config core.hooksPath .githooks

dev:
	$(COMPOSE) up --build

postgres-up:
	$(COMPOSE) up -d --build postgres
	@$(MAKE) postgres-wait

postgres-wait:
	@for _ in $$(seq 1 40); do \
		if $(COMPOSE) exec -T postgres pg_isready -U memrise -d memrise >/dev/null 2>&1; then \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "postgres failed to become ready"; \
	exit 1

dev-local: postgres-up migrate
	bash scripts/dev-local.sh

stop:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

format:
	$(UV_ENV) uv run ruff format .
	pnpm exec prettier --write . --ignore-unknown

format-check:
	$(UV_ENV) uv run ruff format --check .
	pnpm exec prettier --check . --ignore-unknown

lint:
	$(UV_ENV) uv run ruff format --check .
	$(UV_ENV) uv run ruff check .
	pnpm exec prettier --check . --ignore-unknown
	pnpm --recursive lint

typecheck:
	$(UV_ENV) uv run pyright
	pnpm --filter memrise-memory-sdk build
	pnpm --recursive typecheck

test:
	$(UV_ENV) uv run pytest tests/unit tests/api tests/contract tests/eval
	pnpm --recursive test

test-integration:
	$(UV_ENV) uv run pytest tests/integration tests/contract

benchmark-retrieval:
	$(UV_ENV) uv run python scripts/benchmark_retrieval.py

test-e2e:
	pnpm --filter @memrise/web test:e2e

check: lint typecheck test

build: generate-sdk
	pnpm --recursive build
	$(UV_ENV) uv build --package memrise-memory --out-dir /tmp/memrise-package-check/python
	$(UV_ENV) uv build --package memrise-api --out-dir /tmp/memrise-package-check/python
	$(UV_ENV) uv build --package memrise-worker --out-dir /tmp/memrise-package-check/python

package-check: build
	mkdir -p /tmp/memrise-package-check/js
	pnpm --filter memrise-memory-sdk pack --pack-destination /tmp/memrise-package-check/js

migrate:
	$(UV_ENV) uv run alembic -c packages/engine/alembic.ini upgrade head

db-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d postgres
	$(UV_ENV) uv run alembic -c packages/engine/alembic.ini upgrade head

migration:
	$(UV_ENV) uv run alembic -c packages/engine/alembic.ini revision --autogenerate -m "$(name)"

export-openapi:
	$(UV_ENV) uv run python scripts/export_openapi.py
	pnpm exec prettier --write contracts/openapi.json --ignore-unknown

generate-sdk: export-openapi
	pnpm --filter memrise-memory-sdk generate
	pnpm exec prettier --write packages/sdk-typescript/src/generated/api-types.ts --ignore-unknown

