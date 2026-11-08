"""Importance refinement from entity fan-in.

MEMORY_MODEL.md requires that a score can always explain itself, so the
adjustment is appended to `importance_reason` in words rather than applied
silently. A reader can see both the base score's reasoning and what fan-in
added.

This is the honest first version of the fan-in signal: a reference count.
ADR-0012a records the refinement — personalized PageRank over the symbol graph,
the Aider approach — as later work. A count is explainable in one sentence,
which is the constraint that matters most here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import structlog

from ..db.connection import transaction
from ..domain.models import utc_now

log = structlog.get_logger(__name__)

# Fan-in below this is not a signal.
_MIN_FAN_IN = 3
_MAX_BONUS = 0.15
# Only entities that are shared *because the memories are about the same
# thing* count. Files and modules are shared incidentally -- every memory in
# docs/ shares the `docs` module -- and weighting them adjusted 271 of 271
# memories, which ranks nothing. They are deliberately absent.
_KIND_WEIGHT = {
    "command": 0.05,
    "dependency": 0.05,
    "decision": 0.05,
    "component": 0.04,
}


@dataclass
class ImportanceResult:
    considered: int = 0
    adjusted: int = 0


def refine(conn: sqlite3.Connection, *, project_id: str) -> ImportanceResult:
    result = ImportanceResult()
    rows = conn.execute(
        "SELECT me.memory_id, e.kind, e.name, "
        "       (SELECT COUNT(DISTINCT m2.memory_id) FROM memory_entities m2 "
        "        WHERE m2.entity_id = e.id) AS fan_in "
        "FROM memory_entities me JOIN entities e ON e.id = me.entity_id "
        "WHERE e.project_id=?",
        (project_id,),
    ).fetchall()

    bonuses: dict[str, list[tuple[float, str]]] = {}
    for row in rows:
        if row["fan_in"] < _MIN_FAN_IN:
            continue
        weight = _KIND_WEIGHT.get(row["kind"], 0.0)
        if weight <= 0:
            continue
        bonuses.setdefault(row["memory_id"], []).append(
            (
                weight,
                f"{row['kind']} “{row['name']}” is referenced by " f"{row['fan_in']} memories",
            )
        )

    if not bonuses:
        return result

    with transaction(conn):
        for memory_id, signals in bonuses.items():
            current = conn.execute(
                "SELECT importance, importance_base, importance_reason "
                "FROM memories WHERE id=?",
                (memory_id,),
            ).fetchone()
            if current is None:
                continue
            result.considered += 1
            # Apply the bonus to the stored base, never to the current score:
            # adding it to the current value made a second run bump importance
            # again, so repeated analysis inflated every record (migration 0003).
            base_score = (
                current["importance_base"]
                if current["importance_base"] is not None
                else current["importance"]
            )
            # Strongest few signals only: summing every shared file would push
            # every memory to 1.0 and rank nothing.
            top = sorted(signals, key=lambda s: -s[0])[:3]
            bonus = min(_MAX_BONUS, sum(weight for weight, _ in top))
            if bonus <= 0:
                continue
            marker = "; fan-in:"
            base_reason = current["importance_reason"].split(marker)[0]
            new_score = round(min(1.0, base_score + bonus), 3)
            if new_score == current["importance"] and marker in current["importance_reason"]:
                continue
            reason = f"{base_reason}{marker} +{bonus:.2f} because " + "; ".join(
                text for _, text in top
            )
            conn.execute(
                "UPDATE memories SET importance=?, importance_reason=?, updated_at=? "
                "WHERE id=?",
                (new_score, reason, utc_now(), memory_id),
            )
            result.adjusted += 1

    log.info(
        "importance.refined",
        project_id=project_id,
        considered=result.considered,
        adjusted=result.adjusted,
    )
    return result
