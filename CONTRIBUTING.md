# Contributing to Memrise

Thanks for helping build Memrise. This guide covers how the codebase is organized, the rules that keep it clean, and the checks to run before opening a PR. For the full architecture, see [README.md](README.md); for the terse machine-readable rules, see [AGENTS.md](AGENTS.md).

## Getting set up

```bash
make bootstrap                                  # install deps + configure .githooks/
docker compose -f infra/compose.yaml up -d postgres
make migrate                                    # apply Alembic migrations
make dev                                         # everything in Docker (API + worker + inspector)
```

Or run the apps on the host with hot reload (Postgres stays in Docker); this brings up Postgres, applies migrations, then starts the API, worker, and web (`http://localhost:3000`):

```bash
make dev-local
```

Copy `.env.example` to `.env` and set `ALIBABA_CLOUD_API_KEY`, the Qwen adapter is required for capture, remember, retrieve, and respond (there is no in-app model fallback). If hooks ever fall out of sync, reinstall them with `make install-hooks`.

## Architecture boundaries

Memrise is a layered engine with a strict dependency direction. Respect these boundaries, most review friction comes from crossing them.

| Layer                                                | May contain                                                                    | Must not contain                                  |
| ---------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------- |
| `packages/engine/src/memrise/core`                   | Dataclasses, enums, pure lifecycle logic                                       | I/O, SQL, HTTP, model calls                       |
| `.../ports`                                          | `Protocol` interfaces for stores, jobs, providers, clocks, IDs, token counters | Concrete implementations                          |
| `.../integrations`                                   | PostgreSQL and Qwen implementations only                                       | In-app fake models or in-memory runtime fallbacks |
| `.../write`, `.../read`, `.../learning`, `.../graph` | Domain services                                                                | Direct HTTP handling                              |
| `.../runtime`                                        | Composition root / wiring                                                      | Business logic                                    |
| `apps/api`                                           | Request validation, auth, DI, error translation, HTTP status                   | Raw SQL, Qwen calls, business logic               |
| `apps/worker`                                        | Claiming jobs and calling engine services                                      | Qwen calls in handlers, raw SQL                   |
| `apps/web`                                           | Public API/SDK usage only                                                      | Any direct PostgreSQL access                      |

**PostgreSQL is the single source of truth.** Episodes are immutable, canonical memories are versioned, graph edges are projections of accepted memory versions, and feedback affects usefulness only.

### Forbidden patterns

- No raw SQL in route modules.
- No Qwen calls in API routes or worker handlers.
- No SQLAlchemy models used as API schemas; no Pydantic API schemas used as domain entities.
- No duplicated memory ranking or reconciliation logic in TypeScript, that lives in the engine.
- No graph writes from raw episodes (claims-first only).
- No `utils.py` / `helpers.py` / `common.py` dumping grounds.
- **No physical deletion of normal superseded or expired memory**, history is preserved by design.

## Making changes

Keep changes focused and grouped into clean, logically separated commits. When touching the memory pipeline, know which path you're in:

- **Write path** (`write/`, `learning/reconciliation.py`): importance gate, extraction, validation, reconciliation.
- **Read path** (`read/retrieval.py`): channels, RRF fusion, ranking, critical reservation, packing.
- **Forgetting** (`learning/lifecycle.py`): expiry, usefulness decay, contested resolution.
- **Graph** (`graph/`, `integrations/apache_age`): claims and temporal projection.

### Database changes

Alembic migrations are the **only** schema setup path. Every new schema change needs a migration with explicit downgrade behavior, plus PostgreSQL + pgvector integration tests. Do not substitute SQLite.

```bash
make migrate
make test-integration     # requires Postgres up + migrated
```

### API / schema changes

`contracts/openapi.json` and `packages/sdk-typescript/src/generated/api-types.ts` are **generated**. After changing API schemas, regenerate and commit them:

```bash
make generate-sdk
```

Never hand-maintain duplicate TypeScript API interfaces.

## Before opening a PR

Run the narrowest relevant checks while iterating, then the broad suite:

```bash
make format          # Ruff + Prettier
make check           # static checks + unit/contract tests
make test-integration   # when touching storage/DB (Postgres required)
```

### Commit messages

Commits use **Conventional Commits** (enforced by the commit-msg hook), e.g.:

```
feat(read): reserve critical-memory budget in the packer
fix(engine): humanize memory keys in trace labels
```

Valid types include `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`. The hook also blocks legacy product/package names.

The pre-commit hook runs staged-file-aware Ruff (format + lint), Prettier, ESLint/typecheck for TypeScript, Pyright for Python type safety, and the legacy-name scanner.

## Definition of done

A change is ready when: it installs from lockfiles, migrations apply, unit tests pass, integration tests pass when PostgreSQL is available, generated OpenAPI/SDK files are current, and the docs state any limitations honestly.
