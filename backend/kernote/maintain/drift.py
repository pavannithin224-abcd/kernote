"""Drift detection — Stage 3 feasibility spike (proposal P4).

Scope: detection and evidence only. Severity bands, the review UI and the
resolution flow are Stage 6. This exists now to prove the mechanism works
before Stage 6 depends on it.

The mechanism, in order:

    memory.source_refs  ->  pinned (rel_path, line_start..line_end, content_hash)
            |
            v  content_hash != current file hash?
        no  ->  nothing. An untouched file cannot invalidate a claim.
        yes ->  diff the stored capture against the file on disk
            |
            v  do any changed hunks overlap the pinned line range?
        yes ->  stale_risk, HIGH    (the cited lines themselves moved)
        no  ->  stale_risk, LOW     (the file changed around the citation)

The overlap test is the whole point. Flagging every memory whose file changed
is what destroys trust in a freshness feature (risk R10).
"""

from __future__ import annotations

import difflib
import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import structlog
from unidiff import PatchSet

from ..domain.models import Finding, FindingKind, Severity
from .findings import record

log = structlog.get_logger(__name__)

DETECTOR = "rule:hash_and_hunk_overlap@1"


def _squash(lines: list[str]) -> str:
    """Collapse all whitespace so formatting differences vanish.

    `str.split()` splits on any run of whitespace including newlines, so this
    also neutralises reflow: a sentence rewrapped across two lines squashes to
    the same text as the single-line version.
    """
    return " ".join("".join(lines).split())


@dataclass(frozen=True)
class Hunk:
    """A changed region, in the *new* file's line numbering (1-based inclusive).

    `cosmetic` means the removed and added text are identical once whitespace
    is collapsed: reindentation, rewrapping, trailing spaces, blank lines. The
    bytes moved but no claim did.
    """

    start: int
    end: int
    cosmetic: bool = False

    def overlaps(self, line_start: int, line_end: int) -> bool:
        return self.start <= line_end and line_start <= self.end


def parse_hunks(old_text: str, new_text: str, rel_path: str) -> list[Hunk]:
    """Changed regions between two versions of a file.

    difflib produces the unified diff and unidiff parses it, rather than either
    being hand-rolled. Working from the stored capture instead of `git diff`
    means drift also works for untracked files and non-git directories, which
    is the point of ADR-0005's content_hash-first provenance.
    """
    diff_lines = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
        n=0,  # no context: only the lines that actually changed
    )
    patch = PatchSet("".join(diff_lines))
    hunks: list[Hunk] = []
    for patched_file in patch:
        for hunk in patched_file:
            # target_* is the new file's numbering. A pure deletion has
            # target_length 0; treat it as touching the line it was removed
            # from, otherwise deletions become invisible to the overlap test.
            start = hunk.target_start
            length = max(hunk.target_length, 1)
            removed = [line.value for line in hunk.source_lines()]
            added = [line.value for line in hunk.target_lines()]
            cosmetic = _squash(removed) == _squash(added)
            hunks.append(Hunk(start, start + length - 1, cosmetic))
    return hunks


@dataclass
class DriftResult:
    checked: int = 0
    unchanged_files: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0


def detect_drift(conn: sqlite3.Connection, *, project_id: str, root: Path) -> DriftResult:
    """Compare every pinned source ref against the file on disk."""
    result = DriftResult()
    rows = conn.execute(
        "SELECT r.id AS ref_id, r.memory_id, r.rel_path, r.line_start, r.line_end, "
        "       r.content_hash, m.title, m.status "
        "FROM memory_source_refs r "
        "JOIN memories m ON m.id = r.memory_id "
        "WHERE m.project_id = ? AND r.rel_path IS NOT NULL "
        "  AND r.content_hash IS NOT NULL "
        "  AND m.status IN ('active','needs_review')",
        (project_id,),
    ).fetchall()

    # Cache per path so a file referenced by ten memories is read once.
    disk: dict[str, tuple[str, str] | None] = {}

    for row in rows:
        rel = row["rel_path"]
        if rel not in disk:
            path = root / rel
            if not path.is_file():
                disk[rel] = None
            else:
                raw = path.read_bytes()
                try:
                    disk[rel] = (hashlib.sha256(raw).hexdigest(), raw.decode("utf-8"))
                except UnicodeDecodeError:
                    disk[rel] = None
        current = disk[rel]
        result.checked += 1

        if current is None:
            record(
                conn,
                project_id,
                Finding(
                    kind=FindingKind.BROKEN_LINK,
                    severity=Severity.MEDIUM,
                    detector=DETECTOR,
                    memory_id=row["memory_id"],
                    explanation=(
                        f"{rel} is referenced by this memory " "but is missing or unreadable."
                    ),
                    evidence={
                        "rel_path": rel,
                        "dedupe_key": f"missing:{rel}:{row['memory_id']}",
                    },
                ),
            )
            continue

        current_hash, current_text = current
        if current_hash == row["content_hash"]:
            result.unchanged_files += 1
            continue

        old = conn.execute(
            "SELECT text FROM source_captures WHERE project_id=? AND content_hash=?",
            (project_id, row["content_hash"]),
        ).fetchone()
        if old is None or old["text"] is None:
            # No stored capture to diff against: report the hash change alone
            # rather than inventing hunk evidence we do not have.
            record(
                conn,
                project_id,
                Finding(
                    kind=FindingKind.STALE_RISK,
                    severity=Severity.LOW,
                    detector=DETECTOR,
                    memory_id=row["memory_id"],
                    explanation=(
                        f"{rel} changed since this memory was captured, but the original "
                        "capture is unavailable so the changed lines cannot be identified."
                    ),
                    evidence={
                        "rel_path": rel,
                        "pinned_hash": row["content_hash"],
                        "current_hash": current_hash,
                        "hunks": [],
                        "dedupe_key": f"stale:{row['ref_id']}:{current_hash}",
                    },
                ),
            )
            result.findings_low += 1
            continue

        hunks = parse_hunks(old["text"], current_text, rel)
        line_start = row["line_start"] or 1
        line_end = row["line_end"] or line_start
        overlapping = [h for h in hunks if h.overlaps(line_start, line_end)]
        substantive = [h for h in overlapping if not h.cosmetic]

        # Three bands, because "the cited lines were reformatted" and "the
        # cited lines were rewritten" are different news. Without the middle
        # band, one run of a formatter over the docs flags every citation in
        # the touched lines as high, and the queue stops being believable --
        # risk R10 arriving by a second route.
        if substantive:
            severity = Severity.HIGH
            explanation = (
                f"{rel} changed inside the lines this memory cites "
                f"({line_start}-{line_end}). "
                f"{len(substantive)} changed region(s) overlap the citation."
            )
            result.findings_high += 1
        elif overlapping:
            severity = Severity.MEDIUM
            explanation = (
                f"{rel} was reformatted within the cited lines "
                f"({line_start}-{line_end}) but the wording is unchanged once "
                "whitespace is ignored. The claim almost certainly still holds; "
                "accept to re-pin the source hash."
            )
            result.findings_medium += 1
        else:
            severity = Severity.LOW
            explanation = (
                f"{rel} changed, but not within the cited lines "
                f"({line_start}-{line_end}). The claim may still hold."
            )
            result.findings_low += 1

        record(
            conn,
            project_id,
            Finding(
                kind=FindingKind.STALE_RISK,
                severity=severity,
                detector=DETECTOR,
                memory_id=row["memory_id"],
                explanation=explanation,
                evidence={
                    "rel_path": rel,
                    "cited_lines": [line_start, line_end],
                    "pinned_hash": row["content_hash"],
                    "current_hash": current_hash,
                    "hunks": [[h.start, h.end] for h in hunks],
                    "overlapping_hunks": [[h.start, h.end] for h in overlapping],
                    "substantive_hunks": [[h.start, h.end] for h in substantive],
                    "cosmetic_only": bool(overlapping) and not substantive,
                    "dedupe_key": f"stale:{row['ref_id']}:{current_hash}",
                },
            ),
        )

    log.info(
        "drift.checked",
        project_id=project_id,
        refs=result.checked,
        high=result.findings_high,
        medium=result.findings_medium,
        low=result.findings_low,
    )
    return result
