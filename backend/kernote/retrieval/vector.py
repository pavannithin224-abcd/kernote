"""Semantic retrieval: float32 BLOBs in SQLite, cosine by one numpy matmul.

ADR-0003/0003a: no vector extension. At MVP scale the whole index is a single
matrix multiply — 287 memories x 384 dims is 0.4 MB — and `sqlite-vec` has
documented Windows extension-load failures. `embeddings` keys on
(target_kind, target_id, model_id), so two models coexist and ADR-0014's
benchmark needs no migration.

Vectors are stored already L2-normalised, which makes cosine a dot product.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np
import structlog

from ..db.connection import transaction
from ..domain.models import utc_now
from . import embed

log = structlog.get_logger(__name__)

_BATCH = 128


@dataclass(frozen=True)
class VectorHit:
    target_kind: str
    target_id: str
    similarity: float


@dataclass
class IndexResult:
    embedded_memories: int = 0
    embedded_chunks: int = 0
    skipped: str | None = None


def _to_blob(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def _pending(
    conn: sqlite3.Connection, project_id: str, kind: str, model_id: str
) -> list[tuple[str, str]]:
    """(id, text) for rows with no vector for this model yet.

    Embedding is incremental: a rescan that adds ten memories re-embeds ten,
    not the whole project.
    """
    if kind == "memory":
        sql = (
            "SELECT m.id, m.title || ' ' || COALESCE(m.summary, '') "
            "       || ' ' || m.content AS text "
            "FROM memories m WHERE m.project_id = ? "
            "AND m.status NOT IN ('superseded','archived') "
            "AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.target_kind='memory' "
            "                AND e.target_id = m.id AND e.model_id = ?)"
        )
    else:
        sql = (
            "SELECT c.id, COALESCE(c.heading_path,'') || ' ' || c.text AS text "
            "FROM chunks c JOIN source_files sf ON sf.id = c.source_file_id "
            "WHERE c.project_id = ? AND sf.is_current = 1 "
            "AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.target_kind='chunk' "
            "                AND e.target_id = c.id AND e.model_id = ?)"
        )
    return [(r["id"], r["text"]) for r in conn.execute(sql, (project_id, model_id))]


def build_index(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    allow_download: bool = False,
    model_id: str | None = None,
) -> IndexResult:
    """Embed anything not yet embedded. Safe to call repeatedly."""
    model_id = model_id or embed.MODEL_ID
    if embed.ensure_model(allow_download=allow_download) is None:
        return IndexResult(skipped="embedding model unavailable; keyword search only")

    result = IndexResult()
    for kind in ("memory", "chunk"):
        rows = _pending(conn, project_id, kind, model_id)
        for start in range(0, len(rows), _BATCH):
            batch = rows[start : start + _BATCH]
            vectors = embed.encode(
                [text[:4000] for _, text in batch], allow_download=allow_download
            )
            if not vectors:
                return IndexResult(skipped="encoding returned nothing")
            with transaction(conn):
                for (target_id, _), vector in zip(batch, vectors, strict=True):
                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings"
                        "(target_kind,target_id,model_id,dim,vector,built_at) "
                        "VALUES(?,?,?,?,?,?)",
                        (kind, target_id, model_id, len(vector), _to_blob(vector), utc_now()),
                    )
            if kind == "memory":
                result.embedded_memories += len(batch)
            else:
                result.embedded_chunks += len(batch)

    log.info(
        "vector.indexed",
        project_id=project_id,
        memories=result.embedded_memories,
        chunks=result.embedded_chunks,
    )
    return result


def _matrix(
    conn: sqlite3.Connection, project_id: str, model_id: str
) -> tuple[list[tuple[str, str]], np.ndarray]:
    """All vectors for a project as one matrix, with their identities.

    Scoped by project through a join so one project's vectors can never score
    against another's.
    """
    rows = conn.execute(
        "SELECT e.target_kind, e.target_id, e.vector FROM embeddings e "
        "WHERE e.model_id = ? AND ("
        "  (e.target_kind='memory' AND e.target_id IN "
        "     (SELECT id FROM memories WHERE project_id=? "
        "      AND status NOT IN ('superseded','archived')))"
        "  OR (e.target_kind='chunk' AND e.target_id IN "
        "     (SELECT c.id FROM chunks c JOIN source_files sf ON sf.id=c.source_file_id "
        "      WHERE c.project_id=? AND sf.is_current=1))"
        ")",
        (model_id, project_id, project_id),
    ).fetchall()
    if not rows:
        return [], np.zeros((0, embed.DIM), dtype=np.float32)
    identities = [(r["target_kind"], r["target_id"]) for r in rows]
    matrix = np.vstack([_from_blob(r["vector"]) for r in rows])
    return identities, matrix


def search(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    query: str,
    limit: int = 40,
    allow_download: bool = False,
    model_id: str | None = None,
) -> list[VectorHit]:
    """Top-k by cosine. Returns [] when semantic search is unavailable."""
    model_id = model_id or embed.MODEL_ID
    vectors = embed.encode([query], allow_download=allow_download)
    if not vectors:
        return []
    identities, matrix = _matrix(conn, project_id, model_id)
    if not identities:
        return []
    query_vector = np.asarray(vectors[0], dtype=np.float32)
    if matrix.shape[1] != query_vector.shape[0]:
        # A model change leaves vectors of a different width behind; scoring
        # them against the new query would be meaningless.
        log.warning("vector.dim_mismatch", stored=matrix.shape[1], query=query_vector.shape[0])
        return []
    # Both sides are L2-normalised, so the dot product *is* cosine.
    scores = matrix @ query_vector
    top = np.argsort(-scores)[:limit]
    return [VectorHit(identities[i][0], identities[i][1], float(scores[i])) for i in top]


def clear(conn: sqlite3.Connection, *, project_id: str) -> int:
    """Drop a project's vectors. L4 is disposable by design (ADR-0002)."""
    with transaction(conn):
        cursor = conn.execute(
            "DELETE FROM embeddings WHERE "
            "(target_kind='memory' AND target_id IN "
            "   (SELECT id FROM memories WHERE project_id=?)) "
            "OR (target_kind='chunk' AND target_id IN "
            "   (SELECT id FROM chunks WHERE project_id=?))",
            (project_id, project_id),
        )
        return cursor.rowcount
