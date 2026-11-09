"""Hybrid retrieval: keyword + semantic, fused, then boosted.

Fusion is Reciprocal Rank Fusion. RRF combines *ranks*, not scores, which
matters because bm25 is an unbounded negative number and cosine is bounded
[-1, 1] — normalising them onto a common scale means inventing a conversion,
and the conversion would be doing the ranking. RRF needs no such assumption.

Every result carries the signals that produced it. `MEMORY_MODEL.md` requires
retrieval to "return relevant evidence and score/reason metadata", and a
ranking nobody can explain is not reviewable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import structlog

from . import fts, vector

log = structlog.get_logger(__name__)

# Conventional RRF constant. Large enough that the top few ranks are close
# together, so a single signal cannot dominate on its own.
_RRF_K = 60

# Boosts are deliberately small: they reorder near-ties, they do not overrule
# the text signals.
_IMPORTANCE_WEIGHT = 0.15
_NEEDS_REVIEW_PENALTY = 0.05
_INTERPRETATION_PENALTY = 0.04


@dataclass
class Result:
    target_kind: str
    target_id: str
    score: float
    keyword_rank: int | None = None
    semantic_rank: int | None = None
    signals: list[str] = field(default_factory=list)

    @property
    def why(self) -> str:
        return "; ".join(self.signals)


@dataclass
class SearchOutcome:
    results: list[Result]
    keyword_hits: int
    semantic_hits: int
    semantic_available: bool
    note: str | None = None


def _rrf(rank: int) -> float:
    return 1.0 / (_RRF_K + rank)


def search(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    query: str,
    limit: int = 10,
    pool: int = 40,
    allow_download: bool = False,
) -> SearchOutcome:
    keyword = fts.search_memories(conn, project_id=project_id, query=query, limit=pool)
    keyword += fts.search_chunks(conn, project_id=project_id, query=query, limit=pool)
    # One ordering across both kinds: bm25 is comparable between the two FTS
    # tables because both use the same tokenizer and ranking function.
    keyword.sort(key=lambda h: h.score)

    semantic = vector.search(
        conn,
        project_id=project_id,
        query=query,
        limit=pool,
        allow_download=allow_download,
    )
    semantic_available = bool(semantic)

    merged: dict[tuple[str, str], Result] = {}

    for rank, hit in enumerate(keyword, start=1):
        key = (hit.target_kind, hit.target_id)
        result = merged.setdefault(key, Result(hit.target_kind, hit.target_id, 0.0))
        result.keyword_rank = rank
        result.score += _rrf(rank)
        result.signals.append(f"keyword rank {rank} (bm25 {hit.score:.2f})")

    for rank, hit in enumerate(semantic, start=1):
        key = (hit.target_kind, hit.target_id)
        result = merged.setdefault(key, Result(hit.target_kind, hit.target_id, 0.0))
        result.semantic_rank = rank
        result.score += _rrf(rank)
        result.signals.append(f"semantic rank {rank} (cosine {hit.similarity:.3f})")

    _apply_memory_boosts(conn, merged)

    ordered = sorted(merged.values(), key=lambda r: -r.score)
    for result in ordered:
        if result.keyword_rank and result.semantic_rank:
            result.signals.append("found by both keyword and semantic search")

    note = None
    if not semantic_available:
        note = (
            "Semantic search is off, so this is keyword-only. Enable embeddings "
            "in Settings to add meaning-based recall."
        )

    log.info(
        "hybrid.search",
        project_id=project_id,
        keyword=len(keyword),
        semantic=len(semantic),
        returned=min(limit, len(ordered)),
    )
    return SearchOutcome(
        results=ordered[:limit],
        keyword_hits=len(keyword),
        semantic_hits=len(semantic),
        semantic_available=semantic_available,
        note=note,
    )


def _apply_memory_boosts(
    conn: sqlite3.Connection, merged: dict[tuple[str, str], Result]
) -> None:
    """Reorder near-ties using what we already know about each memory."""
    memory_ids = [tid for (kind, tid) in merged if kind == "memory"]
    if not memory_ids:
        return
    placeholders = ",".join("?" * len(memory_ids))
    rows = conn.execute(
        f"SELECT id, importance, status, claim_kind FROM memories WHERE id IN ({placeholders})",  # noqa: S608
        memory_ids,
    ).fetchall()
    for row in rows:
        result = merged[("memory", row["id"])]
        bonus = row["importance"] * _IMPORTANCE_WEIGHT * _rrf(1)
        result.score += bonus
        result.signals.append(f"importance {row['importance']:.2f}")
        if row["status"] == "needs_review":
            # Surfaced, but below a claim nobody has questioned.
            result.score -= _NEEDS_REVIEW_PENALTY * _rrf(1)
            result.signals.append("ranked down: flagged for review")
        if row["claim_kind"] == "interpretation":
            result.score -= _INTERPRETATION_PENALTY * _rrf(1)
            result.signals.append("ranked down: interpretation, not a source fact")
