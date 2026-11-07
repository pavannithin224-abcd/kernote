"""L1 raw captures and L2 chunks.

The content-addressed upsert here is what makes invariant 1 true: re-scanning
an unchanged repository creates zero new captures.
"""

from __future__ import annotations

import sqlite3

from ...domain.models import SkippedFile, new_id, utc_now


def start_scan(conn: sqlite3.Connection, project_id: str, git_commit: str | None) -> str:
    run_id = new_id()
    conn.execute(
        "INSERT INTO scan_runs(id,project_id,started_at,status,git_commit) "
        "VALUES(?,?,?,'running',?)",
        (run_id, project_id, utc_now(), git_commit),
    )
    return run_id


def finish_scan(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    seen: int,
    new: int,
    skipped: int,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE scan_runs SET finished_at=?,status=?,files_seen=?,files_new=?,"
        "files_skipped=?,error=? WHERE id=?",
        (utc_now(), status, seen, new, skipped, error, run_id),
    )


def upsert_capture(
    conn: sqlite3.Connection,
    project_id: str,
    content_hash: str,
    text: str | None,
    byte_size: int,
    encoding: str,
) -> bool:
    """Store raw bytes once per project, forever. Returns True if newly created."""
    exists = conn.execute(
        "SELECT 1 FROM source_captures WHERE project_id=? AND content_hash=?",
        (project_id, content_hash),
    ).fetchone()
    if exists:
        return False
    conn.execute(
        "INSERT INTO source_captures"
        "(content_hash,project_id,text,byte_size,encoding,captured_at) "
        "VALUES(?,?,?,?,?,?)",
        (content_hash, project_id, text, byte_size, encoding, utc_now()),
    )
    return True


def record_file(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    language: str | None,
    run_id: str,
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> str:
    """Record path -> capture for this run. Unchanged file: update last_seen only."""
    row = conn.execute(
        "SELECT id FROM source_files WHERE project_id=? AND rel_path=? AND content_hash=?",
        (project_id, rel_path, content_hash),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE source_files SET last_seen_run=?,is_current=1 WHERE id=?",
            (run_id, row["id"]),
        )
        return row["id"]

    # The path changed content: the old row stops being current but is retained.
    conn.execute(
        "UPDATE source_files SET is_current=0 WHERE project_id=? AND rel_path=?",
        (project_id, rel_path),
    )
    file_id = new_id()
    conn.execute(
        "INSERT INTO source_files(id,project_id,rel_path,content_hash,git_blob_hash,"
        "git_commit,language,first_seen_run,last_seen_run,is_current) "
        "VALUES(?,?,?,?,?,?,?,?,?,1)",
        (
            file_id,
            project_id,
            rel_path,
            content_hash,
            git_blob_hash,
            git_commit,
            language,
            run_id,
            run_id,
        ),
    )
    return file_id


def record_skip(conn: sqlite3.Connection, run_id: str, skip: SkippedFile) -> None:
    conn.execute(
        "INSERT INTO skipped_files(id,scan_run_id,rel_path,reason) VALUES(?,?,?,?)",
        (new_id(), run_id, skip.rel_path, skip.reason.value),
    )


def add_chunk(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    source_file_id: str,
    ordinal: int,
    line_start: int,
    line_end: int,
    heading_path: str | None,
    text: str,
) -> str:
    chunk_id = new_id()
    conn.execute(
        "INSERT INTO chunks(id,project_id,source_file_id,ordinal,line_start,line_end,"
        "heading_path,text,token_estimate) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            chunk_id,
            project_id,
            source_file_id,
            ordinal,
            line_start,
            line_end,
            heading_path,
            text,
            max(1, len(text) // 4),
        ),
    )
    return chunk_id


def skipped_for_run(conn: sqlite3.Connection, run_id: str) -> list[SkippedFile]:
    rows = conn.execute(
        "SELECT rel_path,reason FROM skipped_files WHERE scan_run_id=? ORDER BY rel_path",
        (run_id,),
    ).fetchall()
    return [SkippedFile(rel_path=r["rel_path"], reason=r["reason"]) for r in rows]
