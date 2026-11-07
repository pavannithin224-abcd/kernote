"""Scan orchestration: capture -> normalize -> understand -> curate -> store.

Read-only with respect to the project tree. The only writes are to Kernote's
own database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from ..db.repositories import memories as memory_repo
from ..db.repositories import sources as source_repo
from ..domain.models import ScanResult, SkippedFile
from . import gitmeta
from .capture import capture_file
from .extract import manifests
from .extract import markdown as md_extract
from .normalize import split_markdown
from .walker import walk

log = structlog.get_logger(__name__)

_MARKDOWN_SUFFIXES = {".md", ".markdown"}


def scan_project(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    root: Path,
    max_file_bytes: int,
    max_files: int,
) -> ScanResult:
    root = root.resolve()
    is_repo = gitmeta.is_repo(root)
    commit = gitmeta.head_commit(root) if is_repo else None
    blobs = gitmeta.blob_hashes(root) if is_repo else {}

    run_id = source_repo.start_scan(conn, project_id, commit)
    captures_created = 0
    memories_created = 0
    found: list = []
    skipped: list = []

    try:
        found, skipped = walk(root, max_file_bytes=max_file_bytes, max_files=max_files)
        for skip in skipped:
            source_repo.record_skip(
                conn, run_id, SkippedFile(rel_path=skip.rel_path, reason=skip.reason)
            )

        for item in found:
            cap = capture_file(item.abs_path)
            if cap.text is None:
                continue
            if source_repo.upsert_capture(
                conn, project_id, cap.content_hash, cap.text, cap.byte_size, cap.encoding
            ):
                captures_created += 1

            blob = blobs.get(item.rel_path)
            file_id = source_repo.record_file(
                conn,
                project_id=project_id,
                rel_path=item.rel_path,
                content_hash=cap.content_hash,
                language=cap.language,
                run_id=run_id,
                git_blob_hash=blob,
                git_commit=commit,
            )

            candidates = []
            suffix = Path(item.rel_path).suffix.lower()
            if suffix in _MARKDOWN_SUFFIXES:
                sections = split_markdown(cap.text)
                for ordinal, sec in enumerate(sections):
                    source_repo.add_chunk(
                        conn,
                        project_id=project_id,
                        source_file_id=file_id,
                        ordinal=ordinal,
                        line_start=sec.line_start,
                        line_end=sec.line_end,
                        heading_path=sec.heading_path,
                        text=sec.text,
                    )
                shared = {
                    "project_id": project_id,
                    "rel_path": item.rel_path,
                    "content_hash": cap.content_hash,
                    "sections": sections,
                    "git_blob_hash": blob,
                    "git_commit": commit,
                }
                candidates += md_extract.extract_sections(**shared)
                candidates += md_extract.extract_commands(**shared)
            else:
                candidates += manifests.extract(
                    project_id=project_id,
                    rel_path=item.rel_path,
                    content_hash=cap.content_hash,
                    text=cap.text,
                    git_blob_hash=blob,
                    git_commit=commit,
                )

            for mem in candidates:
                # Curate before store: identical claim from identical content is
                # not a new memory. This is what keeps a re-scan idempotent.
                if memory_repo.exists_same_claim(conn, project_id, mem.title, cap.content_hash):
                    continue
                memory_repo.create(conn, mem)
                memories_created += 1

        source_repo.finish_scan(
            conn,
            run_id,
            status="completed",
            seen=len(found),
            new=captures_created,
            skipped=len(skipped),
        )
        status = "completed"
    except Exception as exc:  # never swallow: record and re-raise
        source_repo.finish_scan(
            conn,
            run_id,
            status="failed",
            seen=len(found),
            new=captures_created,
            skipped=len(skipped),
            error=f"{type(exc).__name__}: {exc}",
        )
        log.error("scan.failed", project_id=project_id, error=str(exc))
        raise

    log.info(
        "scan.completed",
        project_id=project_id,
        files=len(found),
        captures_new=captures_created,
        memories_new=memories_created,
        skipped=len(skipped),
    )

    return ScanResult(
        scan_run_id=run_id,
        project_id=project_id,
        status=status,
        git_commit=commit,
        files_seen=len(found),
        files_new=captures_created,
        files_skipped=len(skipped),
        captures_created=captures_created,
        memories_created=memories_created,
        skipped=source_repo.skipped_for_run(conn, run_id),
    )
