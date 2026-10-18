# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"ledgerly" — a multi-tenant Indian-GST invoicing/accounting + HRMS app. FastAPI + SQLAlchemy + Postgres backend, React + Vite frontend.

## Commands

### Backend (`backend/`)

```bash
pip install -e ".[dev]"            # install (or: uv sync)
docker compose up -d               # start Postgres on localhost:5433 (from repo root)
alembic upgrade head                # apply migrations (needs ALEMBIC_DATABASE_URL)
uvicorn app.main:app --reload --port 8001
pytest                              # full suite, needs the DB up and migrated
pytest tests/test_invoices.py -k test_name   # single test
ruff check .
mypy app
```

Env vars come from `backend/.env` (copy `.env.example`). `DATABASE_URL` connects as the restricted `ledgerly_app` role (RLS applies); `ALEMBIC_DATABASE_URL` connects as the `postgres` bootstrap role (DDL rights, bypasses RLS). The Postgres container runs `backend/docker/init-app-role.sql` on first init to create `ledgerly_app`.

CI (`.github/workflows/ci.yml`) is the canonical sequence: install → run `init-app-role.sql` → `alembic upgrade head` → `ruff check` → `mypy app` → `pytest`.

### Frontend (`frontend/`)

```bash
npm run dev       # Vite dev server, fixed port 5190 (strictPort)
npm run build     # tsc -b && vite build
npm run lint       # oxlint
```

`VITE_API_BASE` env var points at the backend (defaults to `http://127.0.0.1:8001`).

## Architecture

### Multi-tenancy via Postgres RLS, not query filters

Every tenant-owned table has a `tenant_id` column with a FORCE RLS policy. The app never adds `WHERE tenant_id = ...` itself — Postgres enforces it. The mechanism:

- `app/deps.py::get_tenant_db` is the per-request DB session dependency: it runs `SELECT set_config('app.tenant_id', :tid, true)` using the tenant id from the caller's JWT, then yields the session. All tenant-scoped routes depend on this, not the plain `get_db`.
- RLS only works because the app connects as `ledgerly_app`, a non-superuser role without `BYPASSRLS` (see `docker/init-app-role.sql`). Connecting as `postgres` (the migration role) would silently bypass RLS.
- `tests/test_tenant_isolation.py` verifies cross-tenant isolation at the API level — read it before changing anything auth/tenancy related.

### Auth

JWT access + refresh tokens (`app/security.py`, HS256, `argon2` password hashing). `app/deps.py::get_current_user` decodes the bearer token into a `CurrentUser(user_id, tenant_id, role)`. `require_roles(*roles)` gates money-moving endpoints (e.g. invoice issue/cancel needs `owner` or `accountant`, not just any authenticated member). Roles: `owner`, `accountant`, `member`, `hr`, `manager`.

### Modular monolith boundary (enforced by a test, not just convention)

`app/modules/<name>/` packages (currently `people`) may only be imported from outside via that module's `public.py`. Anything else in the module (`models.py`, `service.py`, `api/`) is private. This is enforced by `tests/test_module_boundaries.py`, which ASTs every file under `app/modules/` and fails the build on a cross-module import that doesn't go through `.public`. When adding a new module, add its stable cross-module API to a `public.py` and keep everything else module-private.

The older, non-modularized domains (`customers`, `items`, `quotes`, `invoices`, `payments`, `company`, `users`, `reports`) live flat under `app/api/` with shared `app/models.py` / `app/schemas.py` — they predate the modular-monolith convention and aren't held to the boundary rule.

### Money and tax representation

- All currency amounts are integer paise (no floats), e.g. `unit_price_paise`, `grand_total_paise`.
- GST rates are integer basis points (`gst_rate_bps`; 1800 = 18%).
- `app/gst.py::compute_line_tax` is the single source of truth for CGST/SGST vs IGST splitting (same-state vs inter-state) and rounding (`ROUND_HALF_UP` per half-rate, independently for CGST and SGST — they can legitimately differ by 1 paise). The frontend's `/invoices/preview` call hits this same backend logic rather than re-implementing it in TypeScript.
- `app/ledger.py` posts double-entry journals against a small fixed chart of accounts (`ACCOUNTS_RECEIVABLE`, `SALES_REVENUE`, `OUTPUT_{C,S,I}GST_PAYABLE`, etc.) — it's intentionally minimal, add an account only when a new flow needs it. A deferred DB trigger on `ledger_entry` is the real backstop against unbalanced journals (fires at commit), not application code.
- `app/gst.py::financial_year_label` encodes India's Apr–Mar fiscal year.

### Frontend structure

- `src/api.ts` / `src/peopleApi.ts`: typed fetch wrappers per domain, hold the access/refresh token pair in `localStorage`, auto-retry once on 401 via `/auth/refresh`.
- Routing in `src/App.tsx`: everything except `/login` sits behind `RequireAuth` + `AppShell`.
- `src/components/ui/`: shadcn components.
