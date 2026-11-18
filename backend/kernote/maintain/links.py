"""Confirming and dismissing relationships between memories.

The knowledge graph suggests edges from entity co-occurrence (ADR-0039).
A suggestion is a heuristic; this is where it becomes a judgement, in one
direction or the other:

* **confirm** writes a real `memory_links` row with `origin='user'`, so the
  relationship survives re-indexing, shows up for agents reading the vault,
  and is distinguishable from the mechanical links a merge leaves behind;
* **dismiss** records the pair in `link_rejections`, so a wrong suggestion
  stops coming back. Without somewhere to put the negative answer, "dismiss"
  could only ever mean "hide until the page reloads".

Pairs are stored with the lower id first so that a relationship is one row
whichever way round it was suggested.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import structlog

from ..db.connection import transaction
from ..domain.models import utc_now

log = structlog.get_logger(__name__)

# Kinds a person may assert. `supersedes` and `duplicate_of` are deliberately
# absent: those change what the vault *serves*, and they belong to the
# consolidation flow with its preview, approval and undo (ADR-0040), not to
# a one-click button on a graph.
USER_KINDS = ("relates_to", "contradicts", "refines", "depends_on")

# Direction carries meaning for some of these and not others. "A refines B"
# and "A depends_on B" are claims about which way round it goes; "A relates
# to B" and "A contradicts B" are not. Sorting all of them into a canonical
# order would have silently reversed half.
SYMMETRIC = ("relates_to", "contradicts")


def pair(a: str, b: str) -> tuple[str, str]:
    """A symmetric pair in a stable order, so it is one row either way round."""
    return (a, b) if a < b else (b, a)


def _find_link(conn: sqlite3.Connection, a: str, b: str) -> sqlite3.Row | None:
    """A link between two memories, whichever order it was written in.

    `supersede_into` writes `(keeper, absorbed)` to record direction, while
    symmetric links here are stored sorted. Looking only for the sorted
    order missed every merge link, so `remove` answered "no such link"
    instead of refusing to withdraw one -- caught by a test, not by reading.
    """
    return conn.execute(
        "SELECT src_id, dst_id, kind, origin FROM memory_links "
        "WHERE (src_id=? AND dst_id=?) OR (src_id=? AND dst_id=?)",
        (a, b, b, a),
    ).fetchone()


@dataclass
class LinkResult:
    src_id: str
    dst_id: str
    kind: str
    origin: str


def confirm(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    src_id: str,
    dst_id: str,
    kind: str = "relates_to",
    note: str | None = None,
) -> LinkResult:
    """Record that a human agrees these two memories are related."""
    if kind not in USER_KINDS:
        raise ValueError(
            f"{kind} is not a relationship a person asserts here; "
            f"choose one of {', '.join(USER_KINDS)}"
        )
    if src_id == dst_id:
        raise ValueError("a memory cannot be related to itself")

    # Sorted only where direction does not carry meaning.
    low, high = pair(src_id, dst_id) if kind in SYMMETRIC else (src_id, dst_id)

    with transaction(conn):
        for memory_id in (low, high):
            row = conn.execute(
                "SELECT project_id FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"memory {memory_id} not found")
            if row["project_id"] != project_id:
                raise ValueError(f"memory {memory_id} belongs to another project")

        owned = _find_link(conn, src_id, dst_id)
        if owned is not None and owned["origin"] != "user":
            raise ValueError(
                f"these memories are already linked as {owned['kind']} by a "
                "consolidation; that relationship is not re-asserted here"
            )

        # Confirming settles the question, so an earlier dismissal no longer
        # applies. Dismissals are always sorted: a suggestion has no direction.
        conn.execute(
            "DELETE FROM link_rejections WHERE src_id=? AND dst_id=?",
            pair(src_id, dst_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO memory_links"
            "(src_id,dst_id,kind,reason,created_at,origin) VALUES(?,?,?,?,?,'user')",
            (low, high, kind, note or "confirmed in the knowledge graph", utc_now()),
        )

    log.info("links.confirmed", project_id=project_id, src=low, dst=high, kind=kind)
    return LinkResult(src_id=low, dst_id=high, kind=kind, origin="user")


def dismiss(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    src_id: str,
    dst_id: str,
    note: str | None = None,
) -> tuple[str, str]:
    """Record that a suggested relationship is wrong, so it stops recurring."""
    if src_id == dst_id:
        raise ValueError("a memory cannot be related to itself")
    low, high = pair(src_id, dst_id)
    with transaction(conn):
        # A dismissal only suppresses a *suggestion*. A link somebody
        # confirmed, or one a merge wrote, is removed explicitly -- not as a
        # side effect of dismissing something that looks similar.
        existing = _find_link(conn, src_id, dst_id)
        if existing is not None:
            raise ValueError(
                "this relationship is recorded, not suggested; remove the link "
                "itself rather than dismissing a suggestion"
            )
        conn.execute(
            "INSERT OR REPLACE INTO link_rejections"
            "(project_id,src_id,dst_id,note,created_at) VALUES(?,?,?,?,?)",
            (project_id, low, high, note, utc_now()),
        )
    log.info("links.dismissed", project_id=project_id, src=low, dst=high)
    return low, high


def remove(conn: sqlite3.Connection, *, project_id: str, src_id: str, dst_id: str) -> bool:
    """Withdraw a confirmed link. The memories are untouched.

    Deliberately narrow: it removes the assertion, not the records, and it
    refuses a link a merge wrote, because that one is a consequence of a
    consolidation and is undone by undoing the consolidation (ADR-0040).
    """
    with transaction(conn):
        row = _find_link(conn, src_id, dst_id)
        if row is None:
            return False
        if row["origin"] != "user":
            raise ValueError(
                "this link was written by a consolidation; undo the consolidation "
                "to remove it"
            )
        src, dst = row["src_id"], row["dst_id"]
        conn.execute(
            "DELETE FROM memory_links WHERE src_id=? AND dst_id=? AND origin='user'",
            (src, dst),
        )
    log.info("links.removed", project_id=project_id, src=src, dst=dst)
    return True


def rejected_pairs(conn: sqlite3.Connection, project_id: str) -> set[tuple[str, str]]:
    return {
        (row["src_id"], row["dst_id"])
        for row in conn.execute(
            "SELECT src_id,dst_id FROM link_rejections WHERE project_id=?", (project_id,)
        )
    }
