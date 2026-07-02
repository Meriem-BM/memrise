UV_ENV=UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python

.PHONY: bootstrap install-hooks dev stop logs format format-check lint typecheck test test-integration check migrate migration seed export-openapi generate-sdk eval

bootstrap:
	$(UV_ENV) uv sync --all-packages
	pnpm install --frozen-lockfile
	git config core.hooksPath .githooks

install-hooks:
	git config core.hooksPath .githooks

dev:
	docker compose up --build

stop:
	docker compose down

logs:
	docker compose logs -f

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
	pnpm --recursive typecheck

test:
	$(UV_ENV) uv run pytest packages/engine/tests/unit packages/evals/tests tests/contract
	pnpm --recursive test

test-integration:
	$(UV_ENV) uv run pytest tests/integration

check: lint typecheck test

migrate:
	$(UV_ENV) uv run alembic -c packages/engine/alembic.ini upgrade head

migration:
	$(UV_ENV) uv run alembic -c packages/engine/alembic.ini revision --autogenerate -m "$(name)"

seed:
	$(UV_ENV) uv run python scripts/seed_demo.py

export-openapi:
	$(UV_ENV) uv run python scripts/export_openapi.py

generate-sdk: export-openapi
	pnpm --filter @memrise/sdk generate

eval:
	$(UV_ENV) uv run python scripts/run_evals.py
