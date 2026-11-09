# Changelog

## 1.4.0
- Bump psycopg; no PostgreSQL schema change
- Redis client upgraded to 5.2
- Session cookie max-age raised to 12 hours
- Deploy pipeline now caches the Poetry environment

## 1.3.2
- Fix duplicate invoice when the Redis stream is replayed
- PostgreSQL connection pool size made configurable
- Order status badge colour corrected in the console

## 1.3.1
- Tests: skip integration tests when Docker is absent
- Timezone rendering fix for customers in Lisbon

## 1.3.0
- Delivery windows
- Auth session storage moved from memory to Redis
- Migrations split for zero-downtime deploys
