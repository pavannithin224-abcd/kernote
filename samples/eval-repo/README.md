# Lanternfish

Order and billing service for a small logistics company.

## Stack

Python 3.12 with FastAPI for the API, PostgreSQL 16 for storage, Redis for the
job queue, and a React frontend in `web/`. Packaging is Poetry.

## Running it locally

You need Docker and Python 3.12.

```bash
docker compose up -d postgres redis
poetry install
poetry run alembic upgrade head
poetry run uvicorn lanternfish.main:app --reload --port 8080
```

The API then serves `http://localhost:8080`. The frontend is started
separately with `npm --prefix web run dev` and proxies to that port.

## Tests

```bash
poetry run pytest
```

Integration tests need the Docker services running. They are skipped
otherwise rather than failing.

## Layout

- `src/orders/` — order intake, validation, state machine
- `src/billing/` — invoicing and payment reconciliation
- `web/` — the React operator console
- `docs/adr/` — architecture decision records
- `docs/runbooks/` — on-call procedures
