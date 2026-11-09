"""Cited evidence retrieval (F3) and the embedding index.

F3 is `Must (supporting)` under ADR-0015, scoped as *cited evidence
retrieval*, not chat. The response shape reflects that: an outcome, a plain
statement of what was found, labelled evidence with citations, and the terms
no source mentions.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...db.repositories import projects as project_repo
from ...retrieval import answer as answer_mod
from ...retrieval import embed, vector
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=6, ge=1, le=20)
    session_id: str | None = None


class EmbeddingStatus(BaseModel):
    model_id: str
    dim: int
    cached: bool
    enabled: bool
    usable: bool
    cache_path: str
    download_mb: int
    indexed_memories: int
    indexed_chunks: int


class IndexRequest(BaseModel):
    # The explicit opt-in. `CLAUDE.md` forbids outbound calls by default, and
    # the weights are a ~90 MB fetch, so nothing downloads without this.
    allow_download: bool = False


@router.post("/projects/{project_id}/ask")
def ask(project_id: str, body: AskRequest) -> dict:
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question=body.question,
        limit=body.limit,
        session_id=body.session_id,
    )
    return asdict(bundle)


@router.get("/projects/{project_id}/embeddings", response_model=EmbeddingStatus)
def embedding_status(project_id: str) -> EmbeddingStatus:
    """Filesystem-only status. Never reaches the network."""
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    status = embed.status()
    counts = conn.execute(
        "SELECT "
        " (SELECT COUNT(*) FROM embeddings e JOIN memories m ON m.id=e.target_id "
        "  WHERE e.target_kind='memory' AND m.project_id=?) AS mem, "
        " (SELECT COUNT(*) FROM embeddings e JOIN chunks c ON c.id=e.target_id "
        "  WHERE e.target_kind='chunk' AND c.project_id=?) AS chk",
        (project_id, project_id),
    ).fetchone()
    return EmbeddingStatus(
        model_id=status.model_id,
        dim=status.dim,
        cached=status.cached,
        enabled=status.enabled,
        usable=status.usable,
        cache_path=status.cache_path,
        download_mb=status.download_mb,
        indexed_memories=int(counts["mem"]),
        indexed_chunks=int(counts["chk"]),
    )


@router.post("/projects/{project_id}/embeddings/build")
def build_embeddings(project_id: str, body: IndexRequest) -> dict:
    """Embed anything not yet embedded. Incremental and safe to repeat."""
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    result = vector.build_index(conn, project_id=project_id, allow_download=body.allow_download)
    return {
        "embedded_memories": result.embedded_memories,
        "embedded_chunks": result.embedded_chunks,
        "skipped": result.skipped,
        "note": (
            None
            if result.skipped is None
            else "Semantic search stays off; keyword search is unaffected."
        ),
    }
