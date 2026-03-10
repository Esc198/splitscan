# Backend Architecture

## Target shape

The long-term target is a modular monolith with clear application boundaries:

```text
backend/
  app/
    main.py
    application.py
    lifecycle.py
    core/
      config.py
      logging.py
    api/
      routers/
    modules/
      auth/
      users/
      groups/
      expenses/
      categories/
      receipts/
      sync/
    db/
      session.py
      models/
      migrations/
```

## Architectural rules

- Routes only handle HTTP concerns.
- Business logic lives in services.
- Persistence lives in repositories or DB modules.
- Shared runtime concerns live in `app/core`.
- Request and response contracts use explicit schemas.
- The OCR engine stays behind a service boundary so it can later move to a worker or separate process.

## Migration phases

1. Extract cross-cutting runtime concerns.
   Status: completed.
   Scope: configuration, logging, environment loading, app bootstrap helpers, lifespan bootstrap.

2. Split the HTTP layer into routers by domain.
   Scope: move route groups out of `backend/main.py` without changing business logic yet.
   Status: in progress.
   Extracted so far: health, receipt inference, users, auth, categories.
   Pending: sync, summary, groups, expenses, balances, income-related endpoints.

3. Introduce explicit schemas.
   Scope: replace raw `dict[str, Any]` payloads with Pydantic models.

4. Move business logic into domain services.
   Scope: settlements, summaries, sync scope, expense participant inference, auth helpers.

5. Replace ad-hoc SQLite access with a real persistence layer.
   Scope: SQLAlchemy 2.0, Alembic, transactional boundaries, repository layer.

6. Prepare production-grade persistence and sync.
   Scope: PostgreSQL, decimal money fields, soft deletes, better sync semantics.

7. Isolate heavy OCR execution.
   Scope: background worker or separate inference service if traffic or GPU requirements justify it.

## Current status

The repository already completed phase 1 by moving shared startup concerns into:

- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/application.py`
- `backend/app/lifecycle.py`

Phase 2 is now underway with the first extracted routers and shared support modules:

- `backend/app/api/router_setup.py`
- `backend/app/api/routers/health.py`
- `backend/app/api/routers/receipt_inference.py`
- `backend/app/api/routers/users.py`
- `backend/app/api/routers/auth.py`
- `backend/app/api/routers/categories.py`
- `backend/app/db/sqlite.py`
- `backend/app/runtime.py`
- `backend/app/support/auth.py`

`backend/main.py` remains the compatibility entrypoint while the migration continues.
