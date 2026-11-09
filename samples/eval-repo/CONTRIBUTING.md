# Contributing

## Conventions

- Branch names are `type/short-description`, for example `fix/duplicate-invoice`.
- Commit messages use the imperative mood and stay under 72 characters on the
  first line.
- Every module gets a docstring. Functions over ten lines get one too.
- Type hints are required on all public functions. `mypy --strict` runs in CI.
- Line length is 100 characters, enforced by ruff. Do not reformat files you
  are not otherwise changing.
- Database migrations are never edited after merge. Write a new one.
- Tests live beside the code they test, in `tests/` mirroring `src/`.

## Review

Two approvals are required for anything touching `src/billing/`, one for
everything else. The author merges, not the reviewer.
