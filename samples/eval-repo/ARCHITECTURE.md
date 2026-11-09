# Architecture

Lanternfish is a single FastAPI application with two bounded contexts, `orders`
and `billing`, that share a PostgreSQL database but never import each other's
modules directly. They communicate through domain events on a Redis stream.

## Why one database

Both contexts need transactional consistency with the shared `customers` table.
Splitting the database would mean a distributed transaction for every order,
which the team judged a worse problem than the coupling.

## Request path

A request enters through `src/orders/api.py`, is validated by the Pydantic
schemas in `src/orders/schemas.py`, and is written by the repository layer in
`src/orders/repository.py`. No route function touches SQL directly.

## The order state machine

An order moves through `draft`, `submitted`, `picked`, `shipped`, `delivered`
and may enter `cancelled` from any state before `shipped`. The transitions are
declared in one table in `src/orders/state.py`; nothing else is allowed to
mutate `order.status`.

## Caching

Read-heavy customer lookups are cached in Redis with a 5 minute TTL. The cache
is keyed by customer id and invalidated on write. There is no cache on order
data, deliberately: stale order status caused two incidents in 2025.
