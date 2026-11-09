# ADR-0001: PostgreSQL as the primary datastore

Status: accepted
Date: 2025-02-11

## Context

We needed a datastore for orders and invoices with strong transactional
guarantees and a team that already knew it well.

## Decision

We will use PostgreSQL 16.

## Alternatives

- **MySQL** — rejected; weaker support for the range and exclusion constraints
  the delivery-window feature needs.
- **MongoDB** — rejected; the data is highly relational and invoice
  reconciliation is a join-heavy workload.
- **SQLite** — rejected for production; fine for tests, but concurrent writes
  from the queue workers would serialise.

## Consequences

Operational cost is a managed instance. We gain exclusion constraints, which
`src/orders/state.py` relies on to prevent overlapping delivery windows.
