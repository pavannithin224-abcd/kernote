# Decisions

## Decision: Postgres over SQLite

We chose Postgres because widget definitions are written concurrently by
several render workers. SQLite was rejected for write contention. Status:
accepted, 2026-03-11.
