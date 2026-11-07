from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...db.repositories import memories as repo
from ...db.repositories import projects as project_repo
from ...domain.models import ClaimKind, Memory, MemoryType, SourceRef
from ...domain.scoring import score_confidence, score_importance
from ..deps import db
from ..schemas import (
    CreateMemory,
    MemoryDetail,
    SupersedeMemory,
    SupersedeResult,
    UpdateMemory,
)

router = APIRouter(prefix="/api/v1", tags=["memories"])


@router.get("/projects/{project_id}/memories", response_model=list[Memory])
def list_memories(
    project_id: str,
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
) -> list[Memory]:
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    return repo.list_for_project(conn, project_id, type_=type, status=status, limit=limit)


@router.post("/projects/{project_id}/memories", response_model=Memory, status_code=201)
def create_memory(project_id: str, body: CreateMemory) -> Memory:
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    try:
        mtype = MemoryType(body.type)
    except ValueError:
        raise HTTPException(422, f"unknown memory type: {body.type}") from None
    imp, imp_why = score_importance(memory_type=mtype, rel_path=None)
    conf, conf_why = score_confidence(
        claim_kind=ClaimKind.SOURCE_FACT, extraction_method="manual", has_line_range=False
    )
    memory = Memory(
        project_id=project_id,
        type=mtype,
        title=body.title,
        content=body.content,
        summary=body.summary,
        claim_kind=ClaimKind.SOURCE_FACT,
        importance=imp,
        importance_reason=imp_why,
        confidence=conf,
        confidence_reason=conf_why,
        extraction_method="manual",
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        decision=body.decision,
        source_refs=[SourceRef(user_note=body.user_note)],
    )
    return repo.create(conn, memory, change_reason="created by user", actor="user")


@router.post("/memories/{memory_id}/supersede", response_model=SupersedeResult)
def supersede_memory(memory_id: str, body: SupersedeMemory) -> SupersedeResult:
    """Replace a memory with a newer claim. The old record is never destroyed.

    This is the lifecycle operation that distinguishes maintained memory from
    an overwritten note: the previous claim keeps its content, its provenance
    and its revisions, and becomes queryable history.
    """
    conn = db()
    current = repo.get(conn, memory_id)
    if current is None:
        raise HTTPException(404, "memory not found")

    imp, imp_why = score_importance(memory_type=current.type, rel_path=None)
    conf, conf_why = score_confidence(
        claim_kind=ClaimKind.SOURCE_FACT, extraction_method="manual", has_line_range=False
    )
    replacement = Memory(
        project_id=current.project_id,
        type=current.type,
        title=body.title,
        content=body.content,
        summary=body.summary,
        claim_kind=ClaimKind.SOURCE_FACT,
        importance=imp,
        importance_reason=imp_why,
        confidence=conf,
        confidence_reason=conf_why,
        extraction_method="manual",
        valid_from=body.valid_from,
        decision=body.decision,
        source_refs=[SourceRef(user_note=f"replaces {memory_id}: {body.reason}")],
    )
    result = repo.supersede(conn, memory_id, replacement, reason=body.reason)
    if result is None:
        raise HTTPException(404, "memory not found")
    old, new = result
    return SupersedeResult(superseded=old, replacement=new)


@router.get("/memories/{memory_id}", response_model=MemoryDetail)
def get_memory(memory_id: str) -> MemoryDetail:
    conn = db()
    memory = repo.get(conn, memory_id)
    if memory is None:
        raise HTTPException(404, "memory not found")
    return MemoryDetail(
        memory=memory,
        citations=[r.citation for r in memory.source_refs],
        revisions=repo.revisions(conn, memory_id),
    )


@router.patch("/memories/{memory_id}", response_model=Memory)
def update_memory(memory_id: str, body: UpdateMemory) -> Memory:
    updated = repo.update(
        db(),
        memory_id,
        title=body.title,
        content=body.content,
        summary=body.summary,
        change_reason=body.change_reason,
    )
    if updated is None:
        raise HTTPException(404, "memory not found")
    return updated


@router.post("/memories/{memory_id}/archive")
def archive_memory(memory_id: str) -> dict:
    conn = db()
    if repo.get(conn, memory_id) is None:
        raise HTTPException(404, "memory not found")
    changed = repo.archive(conn, memory_id)
    return {"archived": changed, "note": "archive never deletes; the record stays fetchable"}
