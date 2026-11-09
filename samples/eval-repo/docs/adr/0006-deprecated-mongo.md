# ADR-0006: Event archive in MongoDB

Status: superseded by ADR-0007
Date: 2025-08-02

## Context

We wanted a cheap append-only archive for domain events.

## Decision

Archive events into MongoDB nightly.

## Consequences

This ran for four months and was removed. The archive now lives in S3 as
newline-delimited JSON. Do not reintroduce the MongoDB dependency; this record
is kept only so the old collection names in `docs/runbooks/` make sense.
