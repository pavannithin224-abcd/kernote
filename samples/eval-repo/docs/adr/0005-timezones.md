# ADR-0005: Store UTC, render local

Status: accepted
Date: 2025-07-14

## Context

Delivery windows are quoted in the customer's local time; two incidents came
from mixed storage conventions.

## Decision

Every timestamp is stored as `timestamptz` in UTC. The customer's IANA zone is
stored on the customer record and applied only at render time.

## Consequences

`src/orders/windows.py` is the only module permitted to convert zones.
