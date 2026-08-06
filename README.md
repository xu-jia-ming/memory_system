# Memory System MVP

Python monorepo for the Memory System MVP (API + extraction worker + consolidation worker).

## Status

**Phase 0 bootstrap is in progress.** This repository currently provides the DEV-001 project skeleton, locked dependencies, and quality tooling only.

- Compose, Docker images, Embedding service, and host Preflight are **not** available yet (DEV-003; see technical specification §3.17).
- Configuration / `.env.example` is **not** available yet (DEV-002).
- Business APIs, workers, migrations, and infrastructure clients are **not** implemented.

Do not assume `docker compose` / Compose wrappers or application endpoints are runnable.

## Runtime

- Python **3.12.13** (see `.python-version`)
- Dependency management: **uv** with committed `uv.lock`
- Build backend: **`uv_build`** as fixed in technical specification §3.5 (`requires = ["uv_build>=0.11.32,<0.13"]`, `build-backend = "uv_build"`)

## Entrypoints (spec §3.2)

| Process | Command |
| --- | --- |
| memory-api | `python -m memory_system.entrypoints.api` |
| memory-extraction-worker | `python -m memory_system.entrypoints.extraction_worker` |
| memory-consolidation-worker | `python -m memory_system.entrypoints.consolidation_worker` |

Until later Phase 0 tasks wire settings and application services, these modules are safe to import but exit non-zero when executed.

## Local setup (after DEV-001)

```bash
uv sync --locked
uv run pytest tests/unit
uv run ruff check .
uv run mypy src tests
```

## Specification

Authoritative design document:

`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
