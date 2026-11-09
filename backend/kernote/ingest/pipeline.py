"""Scan orchestration: capture -> normalize -> understand -> curate -> store.

Read-only with respect to the project tree. The only writes are to Kernote's
own database, and each file is one transactional unit of work.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from ..db.connection import transaction
from ..db.repositories import memories as memory_repo
from ..db.repositories import sources as source_repo
from ..domain.models import ScanResult, SecretWarning, SkippedFile, SkipReason
from . import entities, gitmeta, scanconfig
from .capture import Capture, capture_file
from .extract import adr, code_symbols, manifests
from .extract import markdown as md_extract
from .normalize import split_markdown
from .secrets import classify, read_lines, scan_path, scanning_session
from .walker import Found, walk

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
    # Read before anything is touched, so a malformed config fails the scan
    # rather than silently scanning with the wrong rules.
    config = scanconfig.effective(conn, project_id, root)
    is_repo = gitmeta.is_repo(root)
    commit = gitmeta.head_commit(root) if is_repo else None
    blobs = gitmeta.blob_hashes(root) if is_repo else {}

    run_id = source_repo.start_scan(conn, project_id, commit)
    captures_created = 0
    memories_created = 0
    secrets_refused = 0
    secret_warnings: list[SecretWarning] = []
    found: list[Found] = []
    skipped: list = []

    try:
        found, skipped = walk(
            root, max_file_bytes=max_file_bytes, max_files=max_files, config=config
        )
        with transaction(conn):
            for skip in skipped:
                source_repo.record_skip(
                    conn, run_id, SkippedFile(rel_path=skip.rel_path, reason=skip.reason)
                )

        # One settings context for the whole run: entering it per file is
        # measurable overhead across a few thousand files.
        with scanning_session():
            refusals: dict[str, list] = {}
            for item in found:
                hits = scan_path(item.abs_path)
                if not hits:
                    continue
                refuse, warn = classify(hits, read_lines(item.abs_path))
                if refuse:
                    refusals[item.rel_path] = refuse
                elif warn:
                    # A keyword or entropy guess does not refuse the file; it
                    # is recorded so a human can glance at it.
                    secret_warnings.append(
                        SecretWarning(
                            rel_path=item.rel_path,
                            lines=sorted({h.line_number for h in warn}),
                            detectors=sorted({h.detector for h in warn}),
                        )
                    )

        for item in found:
            if item.rel_path in refusals:
                hits = refusals[item.rel_path]
                # Refuse the whole file. Redacting instead would make the
                # stored capture differ from the bytes on disk, and every
                # later drift diff would then report phantom hunks at the
                # redacted lines, forever.
                source_repo.record_skip(
                    conn,
                    run_id,
                    SkippedFile(rel_path=item.rel_path, reason=SkipReason.SECRET_SUSPECTED),
                )
                # Log locations and detector names only -- never the value.
                log.warning(
                    "scan.secret_refused",
                    project_id=project_id,
                    rel_path=item.rel_path,
                    hits=[{"line": h.line_number, "detector": h.detector} for h in hits],
                )
                secrets_refused += 1
                continue

            cap = capture_file(item.abs_path)
            if cap.text is None:
                continue
            # One file is one unit of work. Without this, a failure partway
            # through a file leaves its capture committed but its chunks and
            # memories missing -- and the next scan sees the capture as already
            # known, so the extraction is never retried.
            with transaction(conn):
                new_captures, new_memories = _ingest_one_file(
                    conn,
                    project_id=project_id,
                    item=item,
                    cap=cap,
                    run_id=run_id,
                    blobs=blobs,
                    commit=commit,
                )
            captures_created += new_captures
            memories_created += new_memories

        source_repo.finish_scan(
            conn,
            run_id,
            status="completed",
            seen=len(found),
            new=captures_created,
            skipped=len(skipped) + secrets_refused,
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
        secrets_refused=secrets_refused,
    )

    return ScanResult(
        scan_run_id=run_id,
        project_id=project_id,
        status=status,
        git_commit=commit,
        files_seen=len(found) - secrets_refused,
        files_new=captures_created,
        files_skipped=len(skipped) + secrets_refused,
        captures_created=captures_created,
        memories_created=memories_created,
        skipped=source_repo.skipped_for_run(conn, run_id),
        secret_warnings=secret_warnings,
    )


def _ingest_one_file(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    item: Found,
    cap: Capture,
    run_id: str,
    blobs: dict[str, str],
    commit: str | None,
) -> tuple[int, int]:
    """Capture, chunk and extract one file. The caller owns the transaction."""
    captures_created = 0
    memories_created = 0

    if source_repo.upsert_capture(
        conn, project_id, cap.content_hash, cap.text, cap.byte_size, cap.encoding
    ):
        captures_created = 1

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
    if code_symbols.language_for(item.rel_path):
        symbols = code_symbols.extract(
            project_id=project_id,
            rel_path=item.rel_path,
            content_hash=cap.content_hash,
            text=cap.text,
            git_blob_hash=blob,
            git_commit=commit,
        )
        candidates += symbols
        # Chunk source files by symbol rather than by arbitrary window: the
        # chunk then has a real line range and a name, which is what makes it
        # citable when retrieval lands in Stage 5.
        for ordinal, mem in enumerate(symbols):
            ref = mem.source_refs[0]
            source_repo.add_chunk(
                conn,
                project_id=project_id,
                source_file_id=file_id,
                ordinal=ordinal,
                line_start=ref.line_start or 1,
                line_end=ref.line_end or 1,
                heading_path=mem.title,
                text=mem.content,
            )
    elif suffix in _MARKDOWN_SUFFIXES:
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
        # ADR extraction runs on the same sections but needs the whole
        # document too, because a one-decision-per-file ADR *is* the document.
        adr_memories = adr.extract(
            project_id=project_id,
            rel_path=item.rel_path,
            content_hash=cap.content_hash,
            text=cap.text,
            sections=sections,
            git_blob_hash=blob,
            git_commit=commit,
        )
        candidates += adr_memories
        if adr_memories:
            # The ADR extractor owns this document. Letting the generic section
            # extractor run as well produced a second, payload-less "Decision"
            # memory for every `## Decision` sub-heading -- a duplicate of the
            # record that already carries the chosen option and alternatives.
            candidates += md_extract.extract_commands(**shared)
        else:
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
        # Curate before store: an identical claim from identical content is not
        # a new memory. This is what keeps a re-scan idempotent.
        if memory_repo.exists_same_claim(conn, project_id, mem.title, cap.content_hash):
            continue
        memory_repo.create(conn, mem)
        # Entity links are what make duplicate candidates and importance
        # fan-in possible; without them both features compare every pair.
        entities.link(conn, project_id, mem)
        memories_created += 1

    return captures_created, memories_created
