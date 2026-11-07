"""Conflict detection — Stage 4 feasibility spike (proposal P5).

Scope: detection and evidence only. Resolution, the review UI and severity
tuning are Stage 6. This exists now because "can contradictions be found
deterministically, with no LLM?" is the riskiest unproven assumption in the
plan, and ADR-0015 made conflict detection a `Must`.

Kernote never picks a winner. A finding holds BOTH claims with their sources
and dates, and waits for a human (ADR-0007).

Two deterministic signals are implemented:

1. Same task, different commands. Two `procedure` memories whose titles
   normalise to the same task but whose command bodies differ. This is the
   common real case: a README and a CONTRIBUTING that disagree about how to
   run the tests.

2. Same question, different answer, overlapping validity. Two `decision`
   memories where one's chosen option appears in the other's alternatives --
   which is what "deciding the same question" looks like in data -- and whose
   validity windows overlap. Needs the temporal fields from ADR-0017, which is
   why this signal was not implementable before.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

import structlog

from .findings import Finding, record

log = structlog.get_logger(__name__)

DETECTOR_PROCEDURE = "rule:same_task_different_commands@1"
DETECTOR_DECISION = "rule:same_question_different_answer@1"

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
    "commands",
    "command",
    "how",
    "guide",
    "instructions",
    "steps",
    "use",
    "using",
    "decision",
    "adr",
}


def _normalise(text: str) -> str:
    words = _NOISE.sub(" ", text.lower()).split()
    return " ".join(w for w in words if w not in _FILLER)


def _commands(content: str) -> frozenset[str]:
    """The set of command lines, ignoring order, blank lines and comments."""
    return frozenset(
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _windows_overlap(
    a_from: str | None, a_until: str | None, b_from: str | None, b_until: str | None
) -> bool:
    """Open-ended windows count as overlapping; ISO strings compare correctly."""
    lo_a, hi_a = a_from or "", a_until or "9999"
    lo_b, hi_b = b_from or "", b_until or "9999"
    return lo_a <= hi_b and lo_b <= hi_a


@dataclass
class ConflictResult:
    compared: int = 0
    procedure_conflicts: int = 0
    decision_conflicts: int = 0


def detect_conflicts(conn: sqlite3.Connection, *, project_id: str) -> ConflictResult:
    result = ConflictResult()
    rows = conn.execute(
        "SELECT id,type,title,content,valid_from,valid_until,decision_json,"
        "extraction_method "
        "FROM memories WHERE project_id=? AND status IN ('active','needs_review') "
        "ORDER BY created_at",
        (project_id,),
    ).fetchall()

    _procedures(conn, project_id, rows, result)
    _decisions(conn, project_id, rows, result)
    log.info(
        "conflicts.checked",
        project_id=project_id,
        compared=result.compared,
        procedure=result.procedure_conflicts,
        decision=result.decision_conflicts,
    )
    return result


def _citation(conn: sqlite3.Connection, memory_id: str) -> str:
    row = conn.execute(
        "SELECT rel_path,line_start,line_end FROM memory_source_refs "
        "WHERE memory_id=? LIMIT 1",
        (memory_id,),
    ).fetchone()
    if row is None or not row["rel_path"]:
        return "user note"
    if row["line_start"]:
        return f"{row['rel_path']}:{row['line_start']}-{row['line_end']}"
    return row["rel_path"]


# Only extractors that yield an actual command list can disagree about
# commands. A prose section's body is not a command set, and comparing it to
# one produces nonsense -- found by the Stage 4 spike, where a README's
# "Testing" section conflicted with its own fenced block.
_COMMAND_METHODS = ("rule:markdown_commands", "manual")


def _file_of(conn: sqlite3.Connection, memory_id: str) -> str | None:
    row = conn.execute(
        "SELECT rel_path FROM memory_source_refs WHERE memory_id=? LIMIT 1",
        (memory_id,),
    ).fetchone()
    return row["rel_path"] if row else None


def _procedures(conn, project_id, rows, result: ConflictResult) -> None:
    buckets: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        if row["type"] != "procedure":
            continue
        if not row["extraction_method"].startswith(_COMMAND_METHODS):
            continue
        buckets.setdefault(_normalise(row["title"]), []).append(row)

    for task, members in buckets.items():
        if len(members) < 2 or not task:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                result.compared += 1
                cmd_a, cmd_b = _commands(a["content"]), _commands(b["content"])
                if cmd_a == cmd_b or not cmd_a or not cmd_b:
                    continue
                file_a, file_b = _file_of(conn, a["id"]), _file_of(conn, b["id"])
                if file_a is not None and file_a == file_b:
                    # Same file disagreeing with itself is a documentation bug
                    # for Stage 6 to classify, not a cross-source conflict.
                    continue
                cite_a, cite_b = _citation(conn, a["id"]), _citation(conn, b["id"])
                record(
                    conn,
                    project_id,
                    Finding(
                        kind="conflict",
                        severity="high",
                        detector=DETECTOR_PROCEDURE,
                        memory_id=a["id"],
                        other_id=b["id"],
                        explanation=(
                            f"Two sources describe the task “{task}” with different "
                            f"commands. {cite_a} says {sorted(cmd_a)!r}; "
                            f"{cite_b} says {sorted(cmd_b)!r}. "
                            "Both claims are kept until you resolve this."
                        ),
                        evidence={
                            "signal": "same_task_different_commands",
                            "task": task,
                            "claims": [
                                {
                                    "memory_id": a["id"],
                                    "citation": cite_a,
                                    "commands": sorted(cmd_a),
                                },
                                {
                                    "memory_id": b["id"],
                                    "citation": cite_b,
                                    "commands": sorted(cmd_b),
                                },
                            ],
                            "only_in_first": sorted(cmd_a - cmd_b),
                            "only_in_second": sorted(cmd_b - cmd_a),
                            "dedupe_key": (
                                f"proc:{min(a['id'], b['id'])}" f":{max(a['id'], b['id'])}"
                            ),
                        },
                    ),
                )
                result.procedure_conflicts += 1


def _decisions(conn, project_id, rows, result: ConflictResult) -> None:
    import json

    decisions = []
    for row in rows:
        if row["type"] != "decision" or not row["decision_json"]:
            continue
        try:
            payload = json.loads(row["decision_json"])
        except json.JSONDecodeError:
            continue
        chosen = payload.get("chosen")
        if not chosen:
            continue
        alts = {str(x).lower() for x in payload.get("alternatives", [])}
        decisions.append((row, str(chosen), alts))

    for i, (a, chosen_a, alts_a) in enumerate(decisions):
        for b, chosen_b, alts_b in decisions[i + 1 :]:
            result.compared += 1
            if chosen_a.lower() == chosen_b.lower():
                continue
            # "Deciding the same question" in data: each one's answer is the
            # other's rejected alternative.
            same_question = chosen_a.lower() in alts_b or chosen_b.lower() in alts_a
            if not same_question:
                continue
            if not _windows_overlap(
                a["valid_from"], a["valid_until"], b["valid_from"], b["valid_until"]
            ):
                continue  # one superseded the other in time: not a conflict
            record(
                conn,
                project_id,
                Finding(
                    kind="conflict",
                    severity="high",
                    detector=DETECTOR_DECISION,
                    memory_id=a["id"],
                    other_id=b["id"],
                    explanation=(
                        f"Two decisions answer the same question differently and are "
                        f"both valid at the same time: {_citation(conn, a['id'])} chose "
                        f"“{chosen_a}”, {_citation(conn, b['id'])} chose “{chosen_b}”. "
                        "Neither is discarded; resolve or supersede one."
                    ),
                    evidence={
                        "signal": "same_question_different_answer",
                        "claims": [
                            {
                                "memory_id": a["id"],
                                "chosen": chosen_a,
                                "alternatives": sorted(alts_a),
                                "valid_from": a["valid_from"],
                                "valid_until": a["valid_until"],
                                "citation": _citation(conn, a["id"]),
                            },
                            {
                                "memory_id": b["id"],
                                "chosen": chosen_b,
                                "alternatives": sorted(alts_b),
                                "valid_from": b["valid_from"],
                                "valid_until": b["valid_until"],
                                "citation": _citation(conn, b["id"]),
                            },
                        ],
                        "dedupe_key": f"dec:{min(a['id'], b['id'])}:{max(a['id'], b['id'])}",
                    },
                ),
            )
            result.decision_conflicts += 1
