"""L3 canonical memories, their revisions and their provenance.

Nothing here deletes. Archive sets a status; an edit writes a new revision.
"""

from __future__ import annotations

import sqlite3

from ...domain.models import Memory, MemoryStatus, SourceRef, new_id, utc_now


def create(
    conn: sqlite3.Connection,
    memory: Memory,
    *,
    change_reason: str = "initial extraction",
    actor: str = "rule",
) -> Memory:
    revision_id = new_id()
    conn.execute(
        "INSERT INTO memories(id,project_id,type,title,content,summary,status,claim_kind,"
        "importance,importance_reason,confidence,confidence_reason,extraction_method,"
        "created_at,updated_at,last_verified_at,current_revision) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            memory.id,
            memory.project_id,
            memory.type.value,
            memory.title,
            memory.content,
            memory.summary,
            memory.status.value,
            memory.claim_kind.value,
            memory.importance,
            memory.importance_reason,
            memory.confidence,
            memory.confidence_reason,
            memory.extraction_method,
            memory.created_at,
            memory.updated_at,
            memory.last_verified_at,
            revision_id,
        ),
    )
    _write_revision(conn, memory, revision_id, None, change_reason, actor)
    for ref in memory.source_refs:
        _write_ref(conn, memory.id, ref)
    return memory


def _write_revision(
    conn,
    memory: Memory,
    revision_id: str,
    parent_id: str | None,
    change_reason: str,
    actor: str,
) -> None:
    conn.execute(
        "INSERT INTO memory_revisions(id,memory_id,parent_id,title,content,summary,"
        "snapshot_json,change_reason,actor,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            revision_id,
            memory.id,
            parent_id,
            memory.title,
            memory.content,
            memory.summary,
            memory.model_dump_json(),
            change_reason,
            actor,
            utc_now(),
        ),
    )


def _write_ref(conn, memory_id: str, ref: SourceRef) -> None:
    conn.execute(
        "INSERT INTO memory_source_refs(id,memory_id,rel_path,line_start,line_end,"
        "content_hash,git_blob_hash,git_commit,url,user_note) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            new_id(),
            memory_id,
            ref.rel_path,
            ref.line_start,
            ref.line_end,
            ref.content_hash,
            ref.git_blob_hash,
            ref.git_commit,
            ref.url,
            ref.user_note,
        ),
    )


def exists_same_claim(
    conn: sqlite3.Connection, project_id: str, title: str, content_hash: str | None
) -> bool:
    """A re-scan of unchanged content must not create a second identical memory."""
    row = conn.execute(
        "SELECT 1 FROM memories m JOIN memory_source_refs r ON r.memory_id=m.id "
        "WHERE m.project_id=? AND m.title=? AND r.content_hash IS ? LIMIT 1",
        (project_id, title, content_hash),
    ).fetchone()
    return row is not None


def get(conn: sqlite3.Connection, memory_id: str) -> Memory | None:
    row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    if not row:
        return None
    return _row(conn, row)


def list_for_project(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    type_: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[Memory]:
    sql = "SELECT * FROM memories WHERE project_id=?"
    params: list[object] = [project_id]
    if type_:
        sql += " AND type=?"
        params.append(type_)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
    params.append(limit)
    return [_row(conn, r) for r in conn.execute(sql, params).fetchall()]


def revisions(conn: sqlite3.Connection, memory_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id,parent_id,title,change_reason,actor,created_at "
        "FROM memory_revisions WHERE memory_id=? ORDER BY created_at",
        (memory_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update(
    conn: sqlite3.Connection,
    memory_id: str,
    *,
    title: str | None,
    content: str | None,
    summary: str | None,
    change_reason: str,
) -> Memory | None:
    current = get(conn, memory_id)
    if current is None:
        return None
    parent = conn.execute(
        "SELECT current_revision FROM memories WHERE id=?", (memory_id,)
    ).fetchone()["current_revision"]

    updated = current.model_copy(
        update={
            "title": title if title is not None else current.title,
            "content": content if content is not None else current.content,
            "summary": summary if summary is not None else current.summary,
            "updated_at": utc_now(),
        }
    )
    revision_id = new_id()
    conn.execute(
        "UPDATE memories SET title=?,content=?,summary=?,updated_at=?,current_revision=? "
        "WHERE id=?",
        (
            updated.title,
            updated.content,
            updated.summary,
            updated.updated_at,
            revision_id,
            memory_id,
        ),
    )
    _write_revision(conn, updated, revision_id, parent, change_reason, "user")
    return updated


def archive(conn: sqlite3.Connection, memory_id: str) -> bool:
    """Archive never deletes: the record stays fetchable by id forever."""
    cur = conn.execute(
        "UPDATE memories SET status=?,updated_at=? WHERE id=? AND status!=?",
        (MemoryStatus.ARCHIVED.value, utc_now(), memory_id, MemoryStatus.ARCHIVED.value),
    )
    return cur.rowcount > 0


def _row(conn: sqlite3.Connection, row: sqlite3.Row) -> Memory:
    refs = conn.execute(
        "SELECT rel_path,line_start,line_end,content_hash,git_blob_hash,git_commit,"
        "url,user_note FROM memory_source_refs WHERE memory_id=? ORDER BY line_start",
        (row["id"],),
    ).fetchall()
    return Memory(
        id=row["id"],
        project_id=row["project_id"],
        type=row["type"],
        title=row["title"],
        content=row["content"],
        summary=row["summary"],
        status=row["status"],
        claim_kind=row["claim_kind"],
        importance=row["importance"],
        importance_reason=row["importance_reason"],
        confidence=row["confidence"],
        confidence_reason=row["confidence_reason"],
        extraction_method=row["extraction_method"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_verified_at=row["last_verified_at"],
        source_refs=[SourceRef(**dict(r)) for r in refs],
    )
