---
name: backend
description: Backend conventions for Schedler (FastAPI, SQLModel, SQLite WAL, Alembic, APScheduler jobs, settings, errors, API shape). Load before writing code in backend/.
---

# Backend conventions

## Layers (keep them separate)

`api/` (HTTP, validation, auth) → `services/` (business rules) → `models/` + `publishers/` + `pipeline/` + `storage/` (I/O). Jobs in `jobs/` call services; they contain no business logic.

## API shape

- JSON under `/api/v1`. Resource routes: `/media`, `/posts`, `/targets`, `/accounts`, `/settings`, `/health`, `/events`.
- Request/response models are Pydantic/SQLModel schemas separate from table models (`XCreate`, `XRead`, `XUpdate`).
- Errors: `{ "error": { "code": "ig_quota_exhausted", "message": "<Indonesian human message>", "detail": {...} } }` with proper HTTP status. A single exception handler maps domain errors.
- Pagination: `?limit=&cursor=` (ULID cursor).
- OpenAPI must stay accurate (the frontend generates types from it).

## Database

- SQLite with `PRAGMA journal_mode=WAL; busy_timeout=5000; foreign_keys=ON` on every connection.
- One writer process (uvicorn `--workers 1`). Keep transactions short; never hold a transaction during network I/O.
- Alembic migrations for every schema change, with `render_as_batch=True` (SQLite ALTER limitations). Never edit an applied migration.
- UTC everywhere (`datetime.now(UTC)`); ULID primary keys.
- Encrypt platform tokens with Fernet before storing (`core/crypto.py`).

## Jobs (APScheduler)

- `AsyncIOScheduler` started in the FastAPI lifespan; `max_instances=1` and `coalesce=True` per job.
- Jobs are **idempotent**: claim rows by updating status in a short transaction (`queued_local → publishing`) before doing I/O, so a crash or overlap can't double-post.
- Each job run logs a summary event (counts, duration) at debug level and errors at error level.

## Config

`pydantic-settings` `Settings` class reading `.env`; fail fast at startup on missing required values for the active features (e.g. Buffer key only required if a Buffer account exists).

## Style

Python 3.14, full type hints, `ruff` (lint + format), async I/O with `httpx.AsyncClient` (shared client per integration, created in lifespan). Logging via stdlib `logging` with JSON formatter in production.
