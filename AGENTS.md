# Agent Instructions

## Product Context

This repository is `memrise` (product name: Memrise), a framework-independent temporal hybrid memory engine for AI agents. The source of truth is PostgreSQL. Episodes are immutable, canonical memories are versioned, graph edges are projections of accepted memory versions, and outcome feedback affects usefulness only.

## Boundaries

- `core/`: dataclasses, enums, pure lifecycle concepts only.
- `ports/`: Protocol interfaces for stores, jobs, providers, clocks, IDs, token counters.
- `integrations/`: PostgreSQL and Qwen implementations only. Do not add in-app fake model or in-memory runtime fallbacks.
- `runtime/`: composition root only.
- `apps/api`: request validation, auth, dependency injection, error translation, HTTP status codes.
- `apps/worker`: claims jobs and calls engine services.
- `apps/web`: public API/SDK only, never PostgreSQL.

## Forbidden Patterns

- No raw SQL in route modules.
- No Qwen calls in API routes or worker handlers.
- No SQLAlchemy models as API schemas.
- No Pydantic API schemas as domain entities.
- No duplicated memory ranking or reconciliation in TypeScript.
- No graph writes from raw episodes.
- No `utils.py`, `helpers.py`, or `common.py` dumping grounds.
- No physical deletion of normal superseded or expired memory.

## Commands Before Completion

Run the narrowest relevant checks, then `make check` for broad changes. For database changes, run `make migrate` and `make test-integration`. For API schema changes, run `make generate-sdk` and verify generated files are committed. Hooks are versioned in `.githooks/`; install them with `make install-hooks` or `make bootstrap`.

Pre-commit runs Ruff format/lint for staged Python, Prettier for staged data/frontend files, ESLint/typecheck for staged TypeScript, Pyright for Python import/type safety, and the legacy-name scanner. Commit messages must use Conventional Commits.

## Migrations

Alembic migrations are the only schema setup path. Keep downgrade behavior explicit. Use PostgreSQL and pgvector integration tests; do not substitute SQLite.

## Generated Files

`contracts/openapi.json` and `packages/sdk-typescript/src/generated/api-types.ts` are generated. Do not hand-maintain duplicate TypeScript API interfaces.

## Definition Of Done

The code installs from lockfiles, migrations apply, unit tests pass, integration tests pass when PostgreSQL is available, generated OpenAPI/SDK are current, and docs state limitations honestly.
