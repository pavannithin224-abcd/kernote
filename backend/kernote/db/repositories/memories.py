"""L3 canonical memories, their revisions and their provenance.

Nothing here deletes. Archive sets a status; an edit writes a new revision.
"""

from __future__ import annotations

import json
import sqlite3

from ...domain.models import Memory, MemoryStatus, SourceRef, new_id, utc_now
from ..connection import transaction


def create(
    conn: sqlite3.Connection,
    memory: Memory,
    *,
    change_reason: str = "initial extraction",
    actor: str = "rule",
) -> Memory:
    """Insert a memory with its first revision and its provenance, atomically.

    These three writes are one fact. Committing the memory row without its
    revision and source_refs would store a record with no lineage and no
    provenance -- exactly what MEMORY_MODEL.md forbids -- so they share a
    transaction and fail together.
    """
    with transaction(conn):
        return _create_locked(conn, memory, change_reason, actor)


def _create_locked(
    conn: sqlite3.Connection, memory: Memory, change_reason: str, actor: str
) -> Memory:
    revision_id = new_id()
    conn.execute(
        "INSERT INTO memories(id,project_id,type,title,content,summary,status,claim_kind,"
        "importance,importance_reason,confidence,confidence_reason,extraction_method,"
        "created_at,updated_at,last_verified_at,valid_from,valid_until,superseded_by,"
        "decision_json,current_revision,importance_base) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            memory.valid_from,
            memory.valid_until,
            memory.superseded_by,
            json.dumps(memory.decision) if memory.decision is not None else None,
            revision_id,
            # The score before any fan-in refinement, so refinement stays
            # idempotent (migration 0003).
            memory.importance,
        ),
    )
    _write_revision(conn, memory, revision_id, None, change_reason, actor)
    for ref in memory.source_refs:
        _write_ref(conn, memory.id, ref)
    return memory


def write_revision(
    conn,
    memory: Memory,
    revision_id: str,
    parent_id: str | None,
    change_reason: str,
    actor: str,
) -> None:
    """Public entry point for callers outside this module.

    `maintain/review.py` needs it to record an undo, which restores a prior
    state by writing a *new* revision rather than deleting the ones it
    reverses. Exposed deliberately rather than letting that module reach for
    the private name.
    """
    _write_revision(conn, memory, revision_id, parent_id, change_reason, actor)


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
    """A re-scan of unchanged content must not create a second identical memory.

    **Keyed on the file's hash, which is why it was not enough.** Editing one
    paragraph of a document changes that hash, so every memory extracted from
    the file looked new and was created again. On this repository a second
    scan after a day's documentation edits produced **345 new memories while
    only 24 new files appeared**, and 91 duplicate proposals to clean up
    after it.

    Kept because it is the cheap path for a genuinely untouched file.
    `find_same_claim` below is what handles a file that changed around an
    unchanged section.
    """
    row = conn.execute(
        "SELECT 1 FROM memories m JOIN memory_source_refs r ON r.memory_id=m.id "
        "WHERE m.project_id=? AND m.title=? AND r.content_hash IS ? LIMIT 1",
        (project_id, title, content_hash),
    ).fetchone()
    return row is not None


def find_same_claim(
    conn: sqlite3.Connection, project_id: str, title: str, rel_path: str | None
) -> sqlite3.Row | None:
    """The live memory this extraction is a new reading of, if there is one.

    Identity is `(project, title, file)` -- the section heading or ADR name,
    in the document it came from. That survives edits to the body, which is
    exactly the case the file-hash check cannot see.

    Returns `None` when **more than one** memory matches, rather than picking
    one. Two sections in the same file sharing a heading is unusual but
    possible, and superseding the wrong one would retire a claim nobody
    retired. Creating a duplicate is a worse-looking outcome and a safer one:
    the duplicate detector will raise it for review, where a human decides.
    """
    if rel_path is None:
        return None
    rows = conn.execute(
        "SELECT m.id, m.content FROM memories m "
        "JOIN memory_source_refs r ON r.memory_id = m.id "
        "WHERE m.project_id=? AND m.title=? AND r.rel_path=? "
        "AND m.status IN ('active','needs_review') "
        "GROUP BY m.id LIMIT 2",
        (project_id, title, rel_path),
    ).fetchall()
    return rows[0] if len(rows) == 1 else None


def repin(conn: sqlite3.Connection, memory_id: str, fresh: Memory) -> None:
    """Point an unchanged claim at where its text now lives.

    A section whose wording did not change but which moved down a file is
    the same memory with a stale citation. Re-creating it would be a
    duplicate; leaving it alone would leave drift detection comparing
    against the old line range and a `content_hash` for a file that has
    moved on -- every such memory would read as stale forever.

    So the claim, its revisions and its id are untouched, and only the
    provenance is refreshed. No revision is written, because the *claim* did
    not change: what changed is where it is.
    """
    with transaction(conn):
        conn.execute("DELETE FROM memory_source_refs WHERE memory_id=?", (memory_id,))
        for ref in fresh.source_refs:
            _write_ref(conn, memory_id, ref)
        conn.execute(
            "UPDATE memories SET last_verified_at=? WHERE id=?", (utc_now(), memory_id)
        )


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
    include_inactive: bool = False,
) -> list[Memory]:
    """Memories for a project.

    Superseded and archived records are excluded by default, per
    MEMORY_MODEL.md: a replaced claim served alongside its replacement is
    misleading. They remain fetchable by id forever (invariant 5), by an
    explicit `status` filter, or with `include_inactive`.
    """
    sql = "SELECT * FROM memories WHERE project_id=?"
    params: list[object] = [project_id]
    if type_:
        sql += " AND type=?"
        params.append(type_)
    if status:
        sql += " AND status=?"
        params.append(status)
    elif not include_inactive:
        sql += " AND status NOT IN ('superseded','archived')"
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

    with transaction(conn):
        return _update_locked(
            conn, memory_id, current, parent, title, content, summary, change_reason
        )


def _update_locked(conn, memory_id, current, parent, title, content, summary, change_reason):  # noqa: PLR0913
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
    with transaction(conn):
        cur = conn.execute(
            "UPDATE memories SET status=?,updated_at=? WHERE id=? AND status!=?",
            (MemoryStatus.ARCHIVED.value, utc_now(), memory_id, MemoryStatus.ARCHIVED.value),
        )
        return cur.rowcount > 0


def supersede(
    conn: sqlite3.Connection,
    old_id: str,
    replacement: Memory,
    *,
    reason: str,
) -> tuple[Memory, Memory] | None:
    """Replace a memory without destroying it (MEMORY_MODEL.md §4).

    The old record keeps every byte it had, gains `superseded_by`, and moves to
    status 'superseded'. It stays fetchable by id forever (invariant 5). This is
    the difference between a maintained memory and an overwritten one.

    Atomic: a half-applied supersession would either orphan the replacement or
    leave two records both claiming to be current.
    """
    with transaction(conn):
        old = get(conn, old_id)
        if old is None:
            return None
        if old.superseded_by:
            raise ValueError(f"memory {old_id} is already superseded by {old.superseded_by}")
        if replacement.project_id != old.project_id:
            raise ValueError("a replacement must belong to the same project")

        new = _create_locked(conn, replacement, f"supersedes {old_id}: {reason}", "user")

        conn.execute(
            "UPDATE memories SET superseded_by=?,status=?,updated_at=?,valid_until=? "
            "WHERE id=?",
            (
                new.id,
                MemoryStatus.SUPERSEDED.value,
                utc_now(),
                old.valid_until or utc_now(),
                old_id,
            ),
        )
        # A typed edge as well, so graph queries do not need to know the column.
        conn.execute(
            "INSERT OR IGNORE INTO memory_links(src_id,dst_id,kind,reason,created_at) "
            "VALUES(?,?,'supersedes',?,?)",
            (new.id, old_id, reason, utc_now()),
        )
        parent = conn.execute(
            "SELECT current_revision FROM memories WHERE id=?", (old_id,)
        ).fetchone()["current_revision"]
        closing_revision = new_id()
        _write_revision(
            conn,
            old.model_copy(update={"superseded_by": new.id, "status": MemoryStatus.SUPERSEDED}),
            closing_revision,
            parent,
            f"superseded by {new.id}: {reason}",
            "user",
        )
        conn.execute(
            "UPDATE memories SET current_revision=? WHERE id=?",
            (closing_revision, old_id),
        )
        refreshed = get(conn, old_id)
        assert refreshed is not None
        return refreshed, new


def supersede_into(
    conn: sqlite3.Connection,
    *,
    absorb_id: str,
    keep_id: str,
    merged_content: str,
    reason: str,
) -> tuple[Memory, Memory] | None:
    """Merge one memory into an existing one, losing nothing.

    Differs from `supersede()` in that the replacement already exists: a
    consolidation keeps one of the two records rather than creating a third.

    What this guarantees, and what the tests assert:

    * the absorbed record keeps every byte it had, gains `superseded_by`, and
      stays fetchable by id forever (invariant 5);
    * **every source ref from the absorbed record is copied onto the keeper**,
      so no citation is lost -- this is the promise the merge preview makes;
    * both records gain a revision, so the merge is in the audit trail;
    * it is one transaction, because a half-applied merge would either lose
      citations or leave two records both claiming to be current.
    """
    with transaction(conn):
        absorb = get(conn, absorb_id)
        keep = get(conn, keep_id)
        if absorb is None or keep is None:
            return None
        if absorb_id == keep_id:
            raise ValueError("a memory cannot be merged into itself")
        if absorb.project_id != keep.project_id:
            raise ValueError("cannot merge across projects")
        if absorb.superseded_by:
            raise ValueError(
                f"memory {absorb_id} is already superseded by {absorb.superseded_by}"
            )

        # Carry the absorbed record's provenance onto the keeper, skipping any
        # citation it already has.
        existing = {
            (r.rel_path, r.line_start, r.line_end, r.url, r.user_note) for r in keep.source_refs
        }
        copied = 0
        for ref in absorb.source_refs:
            key = (ref.rel_path, ref.line_start, ref.line_end, ref.url, ref.user_note)
            if key in existing:
                continue
            _write_ref(conn, keep_id, ref)
            copied += 1

        # New revision on the keeper recording the merged wording.
        keep_parent = conn.execute(
            "SELECT current_revision FROM memories WHERE id=?", (keep_id,)
        ).fetchone()["current_revision"]
        keep_revision = new_id()
        merged = keep.model_copy(update={"content": merged_content, "updated_at": utc_now()})
        conn.execute(
            "UPDATE memories SET content=?,updated_at=?,current_revision=? WHERE id=?",
            (merged_content, merged.updated_at, keep_revision, keep_id),
        )
        _write_revision(
            conn,
            merged,
            keep_revision,
            keep_parent,
            f"absorbed {absorb_id}: {reason} ({copied} citation(s) carried over)",
            "user",
        )

        # Close the absorbed record.
        absorb_parent = conn.execute(
            "SELECT current_revision FROM memories WHERE id=?", (absorb_id,)
        ).fetchone()["current_revision"]
        absorb_revision = new_id()
        conn.execute(
            "UPDATE memories SET superseded_by=?,status=?,updated_at=?,valid_until=?,"
            "current_revision=? WHERE id=?",
            (
                keep_id,
                MemoryStatus.SUPERSEDED.value,
                utc_now(),
                absorb.valid_until or utc_now(),
                absorb_revision,
                absorb_id,
            ),
        )
        _write_revision(
            conn,
            absorb.model_copy(
                update={"superseded_by": keep_id, "status": MemoryStatus.SUPERSEDED}
            ),
            absorb_revision,
            absorb_parent,
            f"merged into {keep_id}: {reason}",
            "user",
        )
        conn.execute(
            "INSERT OR IGNORE INTO memory_links(src_id,dst_id,kind,reason,created_at) "
            "VALUES(?,?,'supersedes',?,?)",
            (keep_id, absorb_id, f"consolidation: {reason}", utc_now()),
        )

        refreshed_keep = get(conn, keep_id)
        refreshed_absorb = get(conn, absorb_id)
        assert refreshed_keep is not None and refreshed_absorb is not None
        return refreshed_keep, refreshed_absorb


def _row(conn: sqlite3.Connection, row: sqlite3.Row) -> Memory:
    refs = conn.execute(
        "SELECT rel_path,line_start,line_end,content_hash,git_blob_hash,git_commit,"
        "url,user_note FROM memory_source_refs WHERE memory_id=? ORDER BY line_start",
        (row["id"],),
    ).fetchall()
    # `supersedes` is derived, never stored: superseded_by is the single
    # authoritative edge (ADR-0017), so the inverse is a lookup.
    inverse = conn.execute(
        "SELECT id FROM memories WHERE superseded_by=? LIMIT 1", (row["id"],)
    ).fetchone()
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
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        superseded_by=row["superseded_by"],
        supersedes=inverse["id"] if inverse else None,
        decision=json.loads(row["decision_json"]) if row["decision_json"] else None,
        source_refs=[SourceRef(**dict(r)) for r in refs],
    )
