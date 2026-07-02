# Contributing

Use focused changes, keep generated files current, and run the checks listed in `AGENTS.md`. New database schema changes require Alembic migrations and PostgreSQL integration tests.

Install hooks with:

```bash
make install-hooks
```

Before opening a PR, run:

```bash
make format
make check
```
