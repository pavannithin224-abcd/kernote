"""Shared request dependencies.

One SQLite connection per process, single writer, WAL. check_same_thread is
disabled because FastAPI's sync endpoints run in a threadpool; writes are
serialised by SQLite's own locking plus busy_timeout (risk R6).
"""

from __future__ import annotations

import sqlite3

_conn: sqlite3.Connection | None = None


def set_db(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("database not initialised; app lifespan did not run")
    return _conn
