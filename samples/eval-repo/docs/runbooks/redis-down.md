# Runbook: Redis is unavailable

## Symptoms

Invoice jobs stop being consumed and `/healthz` reports `queue: degraded`.
Logins fail because sessions live in Redis (ADR-0004).

## Immediate steps

1. Check the managed Redis status page before anything else.
2. Confirm with `redis-cli -h $REDIS_HOST ping`.
3. If Redis is up but the stream is stuck, list pending entries with
   `XPENDING lanternfish:invoices billing-workers`.
4. Reclaim entries older than 10 minutes with `XAUTOCLAIM`. Do **not** delete
   the consumer group; that loses the pending list.

## Recovery

Orders continue to be accepted while Redis is down — intake does not touch it.
Invoices queue up in the `outbox` table and drain automatically once the
stream is reachable. There is no manual replay step and running one twice
caused duplicate invoices in March 2025.
