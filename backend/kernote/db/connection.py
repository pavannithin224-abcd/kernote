"""SQLite connection and forward-only migration runner.

SQLite is the source of truth (ADR-0002). Everything here exists to keep that
claim honest: WAL so a scan and a query do not block each other, foreign keys
ON because the schema relies on them, and a busy timeout because R6 in
docs/ARCHITECTURE.md is a real failure mode on this stack.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False because FastAPI runs sync endpoints in a
    # threadpool, so one process-wide connection is touched from several
    # threads. Safe here only because there is a single writer and SQLite's
    # own serialized threading mode plus busy_timeout handle contention (R6).
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# One process-wide writer. SQLite's serialized mode protects the C layer, but it
# cannot protect a multi-statement unit of work: without this lock two threads
# can interleave inside one logical write and leave a memory without its
# revision. WAL still lets readers run concurrently with the writer.
_write_lock = threading.RLock()


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block as one atomic unit of work.

    The connection is in autocommit mode (``isolation_level=None``), so without
    this every statement commits on its own and a failure halfway through a
    multi-statement write leaves the earlier rows permanently committed. That
    is how a memory ends up stored with no revision and no provenance.

    Re-entrant: a nested call joins the outer transaction instead of starting a
    second one, so repositories can be composed inside a larger scan without
    either having to know about the other.

    BEGIN IMMEDIATE takes the write lock up front rather than upgrading a read
    lock later, which is what turns a lock conflict into a clean wait instead
    of an intermittent "database is locked".
    """
    with _write_lock:
        if conn.in_transaction:
            yield conn  # join the caller's unit of work
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")


def current_version(conn: sqlite3.Connection) -> int:
    """The schema version this database is at.

    Public because restore has to compare an incoming file against it, and
    refuse anything newer than this build understands.
    """
    return _current_version(conn)


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone()
    if row is None:
        return 0
    v = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    return int(v["value"]) if v else 0


def migrate(conn: sqlite3.Connection) -> int:
    """Apply every unapplied migration in filename order. Idempotent."""
    applied = _current_version(conn)
    files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not files:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")

    for path in files:
        version = int(path.name[:4])
        if version <= applied:
            continue
        log.info("migration.apply", version=version, file=path.name)
        # executescript() implicitly COMMITs any open transaction before it
        # runs, so an outer BEGIN here would be silently discarded. Wrapping
        # the transaction *inside* the script is what actually makes a
        # half-applied migration impossible.
        script = f"BEGIN;\n{path.read_text(encoding='utf-8')}\nCOMMIT;"
        try:
            conn.executescript(script)
        except Exception:
            # The failed script already rolled itself back; clear any residue.
            with contextlib.suppress(sqlite3.OperationalError):
                conn.execute("ROLLBACK")
            log.error("migration.failed", version=version, file=path.name)
            raise
        # 0001 seeds schema_version itself; later migrations just bump it.
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(version),),
        )
        applied = version

    return applied


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    version = migrate(conn)
    log.info("db.ready", path=str(db_path), schema_version=version)
    return conn
