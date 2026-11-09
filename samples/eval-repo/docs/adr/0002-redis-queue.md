# ADR-0002: Redis streams for the job queue

Status: accepted
Date: 2025-03-04

## Context

Invoice generation takes up to 40 seconds and cannot happen inside a request.

## Decision

We will use Redis streams with consumer groups, not Celery.

## Alternatives

- **Celery with RabbitMQ** — rejected; a second broker to operate for features
  we do not use.
- **PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`** — seriously considered and
  rejected only because the queue depth metrics we wanted were easier in Redis.
  Revisit if Redis becomes the only reason for the Redis dependency.

## Consequences

Redis is now in the critical path for billing. `docs/runbooks/redis-down.md`
covers the failure mode.
