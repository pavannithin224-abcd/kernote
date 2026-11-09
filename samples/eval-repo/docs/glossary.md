# Glossary

**Delivery window** — the span of time a customer agrees to receive a delivery
in. Quoted in the customer's local time.

**Invoice** — a billing document for one order and one period. Voided, never
deleted.

**Session** — a server-side record of a logged-in operator, stored in Redis.

**Outbox** — a PostgreSQL table holding events not yet published to the queue.

**Picked** — an order status meaning the goods have left the shelf but not the
building.

**Consumer group** — a Redis streams concept letting several workers share one
stream without duplicating work.
