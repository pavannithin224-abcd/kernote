"""Change Impact: which memories a commit range may have invalidated.

Drift (ADR-0019) answers "has the file on disk moved under a pinned claim?".
This answers a different question — "I am about to review this commit range;
what knowledge does it touch?" — so it diffs two *refs* rather than a stored
capture against the working tree.

The same discipline applies either way: a citation is only reported as directly
affected when the changed hunks overlap its line range. Listing every memory
whose file appears in the diff is the behaviour that makes a freshness feature
untrustworthy (risk R10).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from unidiff import PatchSet

from ..ingest import gitmeta

log = structlog.get_logger(__name__)


@dataclass
class AffectedMemory:
    memory_id: str
    title: str
    memory_type: str
    status: str
    citation: str
    rel_path: str
    overlap: str  # "direct" | "same_file"
    changed_lines: list[list[int]] = field(default_factory=list)
    reason: str = ""


@dataclass
class ImpactReport:
    base: str
    head: str
    resolved: bool
    changed_files: list[str] = field(default_factory=list)
    files_with_memories: list[str] = field(default_factory=list)
    affected: list[AffectedMemory] = field(default_factory=list)
    note: str | None = None

    @property
    def direct(self) -> int:
        return sum(1 for a in self.affected if a.overlap == "direct")


def _hunks(diff_text: str) -> list[tuple[int, int]]:
    """Changed regions in the new file's numbering, 1-based inclusive."""
    try:
        patch = PatchSet(diff_text)
    except Exception:  # noqa: BLE001 - a malformed diff must not fail the view
        return []
    spans: list[tuple[int, int]] = []
    for patched_file in patch:
        for hunk in patched_file:
            start = hunk.target_start
            # A pure deletion has target_length 0; treat it as touching the
            # line it was removed from, or deletions become invisible.
            length = max(hunk.target_length, 1)
            spans.append((start, start + length - 1))
    return spans


def analyse(
    conn: sqlite3.Connection, *, project_id: str, root: Path, base: str, head: str = "HEAD"
) -> ImpactReport:
    changed = gitmeta.changed_files(root, base, head)
    if changed is None:
        return ImpactReport(
            base=base,
            head=head,
            resolved=False,
            note=(
                f"Could not resolve {base}..{head} in this repository. "
                "Check the refs, or that the project root is a Git repository."
            ),
        )

    report = ImpactReport(base=base, head=head, resolved=True, changed_files=changed)
    if not changed:
        report.note = "No files changed between those refs."
        return report

    placeholders = ",".join("?" * len(changed))
    # The IN-list is only `?` placeholders counted from `changed`; every value
    # is still bound, so this is not string-built SQL in the S608 sense.
    query = (
        "SELECT m.id, m.title, m.type, m.status, r.rel_path, r.line_start, r.line_end "  # noqa: S608
        "FROM memories m JOIN memory_source_refs r ON r.memory_id = m.id "
        f"WHERE m.project_id = ? AND r.rel_path IN ({placeholders}) "
        "  AND m.status NOT IN ('superseded','archived') "
        "ORDER BY m.importance DESC"
    )
    rows = conn.execute(query, [project_id, *changed]).fetchall()

    diff_cache: dict[str, list[tuple[int, int]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        rel = row["rel_path"]
        if rel not in diff_cache:
            text = gitmeta.file_diff(root, base, head, rel) or ""
            diff_cache[rel] = _hunks(text)
        spans = diff_cache[rel]

        line_start = row["line_start"] or 1
        line_end = row["line_end"] or line_start
        overlapping = [[s, e] for s, e in spans if s <= line_end and line_start <= e]
        key = (row["id"], rel)
        if key in seen:
            continue
        seen.add(key)

        citation = f"{rel}:{line_start}-{line_end}" if row["line_start"] else rel
        if overlapping:
            reason = (
                f"{rel} changed inside the lines this memory cites "
                f"({line_start}-{line_end})."
            )
            overlap = "direct"
        else:
            reason = (
                f"{rel} changed, but not within the cited lines "
                f"({line_start}-{line_end}). Likely unaffected."
            )
            overlap = "same_file"
        report.affected.append(
            AffectedMemory(
                memory_id=row["id"],
                title=row["title"],
                memory_type=row["type"],
                status=row["status"],
                citation=citation,
                rel_path=rel,
                overlap=overlap,
                changed_lines=overlapping or [list(s) for s in spans[:5]],
                reason=reason,
            )
        )

    report.files_with_memories = sorted({a.rel_path for a in report.affected})
    report.affected.sort(key=lambda a: (a.overlap != "direct", a.rel_path))
    log.info(
        "impact.analysed",
        project_id=project_id,
        base=base,
        head=head,
        files=len(changed),
        affected=len(report.affected),
        direct=report.direct,
    )
    return report
