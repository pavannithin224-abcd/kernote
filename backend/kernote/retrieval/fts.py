"""Keyword retrieval over FTS5.

The important part of this module is `build_match`. FTS5's MATCH takes a query
*language*, not free text, so user input reaches it as syntax. Measured before
writing any of this, 8 of 10 realistic questions raised
`sqlite3.OperationalError`:

    "what's the setup?"  -> syntax error near "'"
    sqlite-vec           -> no such column: vec
    C++                  -> syntax error near "+"
    100%                 -> syntax error near "%"
    "" (empty)           -> syntax error
    OR                   -> syntax error near "OR"

So every term is extracted and re-emitted as a quoted FTS5 string literal,
which makes operators, punctuation and reserved words inert. A question mark
can no longer take down the endpoint.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

# Word-ish runs. Keeps digits and intra-word dots/underscores so `fastapi`,
# `0.115.6` and `valid_from` survive; everything else becomes a separator.
_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._]*")
# Single letters and bare numbers match almost everything and rank nothing.
_MIN_TERM = 2
_MAX_TERMS = 24


def build_match(query: str) -> str | None:
    """A safe FTS5 MATCH expression, or None when there is nothing to search.

    Terms are OR-ed rather than AND-ed: bm25 then ranks by how many terms a
    record actually contains, which degrades gracefully for a long question
    instead of returning nothing because one word is missing.
    """
    terms = [t for t in _TERM.findall(query or "") if len(t) >= _MIN_TERM]
    if not terms:
        return None
    # Quoting makes every term a literal: AND, OR, NOT, NEAR and punctuation
    # all lose their meaning to the parser.
    quoted = [f'"{t.replace(chr(34), "")}"' for t in terms[:_MAX_TERMS]]
    return " OR ".join(quoted)


@dataclass(frozen=True)
class Hit:
    """One keyword hit. `score` is bm25, where lower is a better match."""

    target_kind: str  # "memory" | "chunk"
    target_id: str
    score: float


def search_memories(
    conn: sqlite3.Connection, *, project_id: str, query: str, limit: int = 40
) -> list[Hit]:
    match = build_match(query)
    if match is None:
        return []
    rows = conn.execute(
        "SELECT m.id AS id, bm25(memories_fts) AS score "
        "FROM memories_fts JOIN memories m ON m.rowid = memories_fts.rowid "
        "WHERE memories_fts MATCH ? AND m.project_id = ? "
        "  AND m.status NOT IN ('superseded','archived') "
        "ORDER BY score LIMIT ?",
        (match, project_id, limit),
    ).fetchall()
    return [Hit("memory", r["id"], float(r["score"])) for r in rows]


def search_chunks(
    conn: sqlite3.Connection, *, project_id: str, query: str, limit: int = 40
) -> list[Hit]:
    """Chunks carry text that never became a memory, so they add recall.

    Only current files: a chunk from a superseded file revision would cite
    lines that no longer exist.
    """
    match = build_match(query)
    if match is None:
        return []
    rows = conn.execute(
        "SELECT c.id AS id, bm25(chunks_fts) AS score "
        "FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
        "JOIN source_files sf ON sf.id = c.source_file_id "
        "WHERE chunks_fts MATCH ? AND c.project_id = ? AND sf.is_current = 1 "
        "ORDER BY score LIMIT ?",
        (match, project_id, limit),
    ).fetchall()
    return [Hit("chunk", r["id"], float(r["score"])) for r in rows]
