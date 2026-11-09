# ADR-0003: REST, not GraphQL

Status: accepted
Date: 2025-04-22

## Context

The operator console needed fewer round trips and someone proposed GraphQL.

## Decision

We will stay with REST and add purpose-built aggregate endpoints instead.

## Alternatives

- **GraphQL via Strawberry** — rejected; the client count is one, so the main
  benefit does not apply, and query-cost control would be new work.

## Consequences

`GET /api/orders/{id}/console` exists purely to serve one screen. That is
accepted duplication, documented here so it is not "cleaned up" by mistake.
