"""Duplicate candidate detection and consolidation proposals (F4).

Detection only proposes; nothing merges. Approval is Stage 6. What this must
guarantee now is that a proposal is reviewable: both inputs visible, a
before/after preview, and a merge that provably loses nothing.

Candidates come from two deterministic signals (ADR-0021). Embedding cosine is
the third and arrives with retrieval in Stage 5 — the structure here takes a
score from any source, so adding it is a new signal rather than a rewrite.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

import structlog

from ..db.connection import transaction
from ..db.repositories.findings import record
from ..domain.models import Finding, FindingKind, Severity, new_id, utc_now

log = structlog.get_logger(__name__)

DETECTOR = "rule:title_and_entity_overlap@1"

_NOISE = re.compile(r"[^a-z0-9 ]+")
_FILLER = {
    "the",
    "a",
    "an",
    "to",
    "for",
    "and",
    "or",
    "of",
    "in",
    "on",
    "with",
    "is",
    "are",
    "this",
    "that",
    "it",
    "its",
    "commands",
    "command",
    "overview",
}
# Below this, two titles are not about the same thing.
_TITLE_THRESHOLD = 0.6
# A matching title is not enough. Two functions named `create` in different
# modules share a title and nothing else; dogfooding produced 8 such
# candidates out of 8. A duplicate must also say a similar *thing*.
_BODY_THRESHOLD = 0.35
# Symbol memories are keyed by (file, qualified name), which is unique by
# construction, so two of them are never the same claim -- only the same
# identifier in different places.
_STRUCTURAL_METHODS = ("rule:code_symbols",)
# A shared file is weak evidence (many memories share a README); a shared
# command or dependency is stronger.
_WEAK_ENTITY_KINDS = {"file", "module"}


def _tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in _NOISE.sub(" ", text.lower()).split() if w and w not in _FILLER)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class DuplicateResult:
    compared: int = 0
    candidates: int = 0
    proposals: int = 0


def _is_nested(conn: sqlite3.Connection, first_id: str, second_id: str) -> bool:
    """True when one memory's cited lines sit inside the other's, same file."""
    rows = conn.execute(
        "SELECT memory_id, rel_path, line_start, line_end FROM memory_source_refs "
        "WHERE memory_id IN (?,?) AND rel_path IS NOT NULL AND line_start IS NOT NULL",
        (first_id, second_id),
    ).fetchall()
    by_memory: dict[str, list[tuple[str, int, int]]] = {}
    for row in rows:
        by_memory.setdefault(row["memory_id"], []).append(
            (row["rel_path"], row["line_start"], row["line_end"])
        )
    left = by_memory.get(first_id, [])
    right = by_memory.get(second_id, [])
    for path_a, start_a, end_a in left:
        for path_b, start_b, end_b in right:
            if path_a != path_b:
                continue
            if (start_a <= start_b and end_b <= end_a) or (
                start_b <= start_a and end_a <= end_b
            ):
                return True
    return False


def _entities_by_memory(
    conn: sqlite3.Connection, project_id: str
) -> dict[str, set[tuple[str, str]]]:
    rows = conn.execute(
        "SELECT me.memory_id, e.kind, e.name FROM memory_entities me "
        "JOIN entities e ON e.id = me.entity_id WHERE e.project_id=?",
        (project_id,),
    ).fetchall()
    out: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        out.setdefault(row["memory_id"], set()).add((row["kind"], row["name"]))
    return out


def detect_duplicates(
    conn: sqlite3.Connection, *, project_id: str, propose: bool = True
) -> DuplicateResult:
    result = DuplicateResult()
    rows = conn.execute(
        "SELECT id,type,title,content,importance,extraction_method "
        "FROM memories WHERE project_id=? AND status='active' "
        "ORDER BY importance DESC, created_at",
        (project_id,),
    ).fetchall()
    entities = _entities_by_memory(conn, project_id)

    # Only compare memories of the same type that share at least one entity.
    # Comparing every pair is quadratic and most pairs are unrelated.
    buckets: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
    for row in rows:
        if row["extraction_method"].startswith(_STRUCTURAL_METHODS):
            continue
        for kind, name in entities.get(row["id"], set()):
            buckets.setdefault((row["type"], kind, name), []).append(row)
        # Also bucket by title signature. Two root-level files have no shared
        # module entity, so without this a "Running the tests" section in
        # README.md and the identical one in CONTRIBUTING.md were never
        # compared at all -- the obvious duplicate was invisible.
        signature = " ".join(sorted(_tokens(row["title"])))
        if signature:
            buckets.setdefault((row["type"], "title", signature), []).append(row)

    judged: set[tuple[str, str]] = set()
    for (mem_type, kind, name), members in buckets.items():
        if len(members) < 2:
            continue
        for index, first in enumerate(members):
            for second in members[index + 1 :]:
                pair = (min(first["id"], second["id"]), max(first["id"], second["id"]))
                if pair in judged:
                    continue
                judged.add(pair)
                result.compared += 1

                if _is_nested(conn, first["id"], second["id"]):
                    # A section memory and the fenced block inside it are
                    # parent and child, not two independent claims. Without
                    # this, every "Setup" section duplicates its own
                    # "Setup: commands".
                    continue

                title_score = _jaccard(_tokens(first["title"]), _tokens(second["title"]))
                body_score = _jaccard(
                    _tokens(first["content"][:2000]), _tokens(second["content"][:2000])
                )
                shared = entities.get(first["id"], set()) & entities.get(second["id"], set())
                strong_shared = {k for k, _ in shared} - _WEAK_ENTITY_KINDS

                # A shared README alone is not evidence of duplication, so a
                # weak-only overlap needs a strong title match to qualify.
                threshold = _TITLE_THRESHOLD if strong_shared else 0.8
                if title_score < threshold or body_score < _BODY_THRESHOLD:
                    continue

                result.candidates += 1
                score = round((title_score * 0.6) + (body_score * 0.4), 3)
                severity = Severity.HIGH if score >= 0.75 else Severity.MEDIUM
                finding_id = record(
                    conn,
                    project_id,
                    Finding(
                        kind=FindingKind.DUPLICATE,
                        severity=severity,
                        detector=DETECTOR,
                        memory_id=first["id"],
                        other_id=second["id"],
                        explanation=(
                            f"Two {mem_type} memories look like the same claim "
                            f"(title overlap {title_score:.0%}, body {body_score:.0%}), "
                            f"both referring to {kind} “{name}”. "
                            "Nothing is merged without your approval."
                        ),
                        evidence={
                            "signal": "title_and_entity_overlap",
                            "title_score": title_score,
                            "body_score": body_score,
                            "score": score,
                            "shared_entities": sorted(f"{k}:{v}" for k, v in shared),
                            "dedupe_key": f"dup:{pair[0]}:{pair[1]}",
                        },
                    ),
                )
                if propose and _create_proposal(conn, project_id, finding_id, first, second):
                    result.proposals += 1

    log.info(
        "duplicates.checked",
        project_id=project_id,
        compared=result.compared,
        candidates=result.candidates,
        proposals=result.proposals,
    )
    return result


def _citations(conn: sqlite3.Connection, memory_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT rel_path,line_start,line_end,user_note FROM memory_source_refs "
        "WHERE memory_id=?",
        (memory_id,),
    ).fetchall()
    out = []
    for row in rows:
        if row["rel_path"] and row["line_start"]:
            out.append(f"{row['rel_path']}:{row['line_start']}-{row['line_end']}")
        elif row["rel_path"]:
            out.append(row["rel_path"])
        elif row["user_note"]:
            out.append(row["user_note"])
    return out


def merge_preview(conn: sqlite3.Connection, keep: sqlite3.Row, absorb: sqlite3.Row) -> dict:
    """What approving this proposal would produce.

    The merge is deliberately additive: the higher-importance record's wording
    is kept, and the other's citations are appended rather than its text being
    interleaved. Nothing is paraphrased and no sentence is dropped, so the
    preview can be checked by eye -- which is the point of an approval step.
    """
    keep_citations = _citations(conn, keep["id"])
    absorb_citations = _citations(conn, absorb["id"])
    merged_content = keep["content"]
    if absorb_citations:
        merged_content += "\n\nAlso documented at: " + ", ".join(absorb_citations)
    return {
        "before": [
            {
                "memory_id": keep["id"],
                "title": keep["title"],
                "content": keep["content"],
                "citations": keep_citations,
                "importance": keep["importance"],
                "role": "keep",
            },
            {
                "memory_id": absorb["id"],
                "title": absorb["title"],
                "content": absorb["content"],
                "citations": absorb_citations,
                "importance": absorb["importance"],
                "role": "absorb",
            },
        ],
        "after": {
            "title": keep["title"],
            "content": merged_content,
            "citations": sorted({*keep_citations, *absorb_citations}),
        },
        "guarantees": [
            "the absorbed record is superseded, never deleted",
            "every citation from both records is retained",
            "no wording is paraphrased or dropped",
        ],
    }


def _create_proposal(
    conn: sqlite3.Connection,
    project_id: str,
    finding_id: str,
    first: sqlite3.Row,
    second: sqlite3.Row,
) -> bool:
    keep, absorb = (
        (first, second) if first["importance"] >= second["importance"] else (second, first)
    )
    with transaction(conn):
        existing = conn.execute(
            "SELECT id FROM consolidation_proposals WHERE project_id=? AND finding_id=?",
            (project_id, finding_id),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO consolidation_proposals(id,project_id,finding_id,"
            "input_ids_json,preview_json,status,created_at) "
            "VALUES(?,?,?,?,?,'pending',?)",
            (
                new_id(),
                project_id,
                finding_id,
                json.dumps([keep["id"], absorb["id"]]),
                json.dumps(merge_preview(conn, keep, absorb)),
                utc_now(),
            ),
        )
    return True


def pending_proposals(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id,finding_id,input_ids_json,preview_json,created_at "
        "FROM consolidation_proposals WHERE project_id=? AND status='pending' "
        "ORDER BY created_at",
        (project_id,),
    ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "id": row["id"],
                "finding_id": row["finding_id"],
                "input_ids": json.loads(row["input_ids_json"]),
                "preview": json.loads(row["preview_json"]),
                "created_at": row["created_at"],
            }
        )
    return out
