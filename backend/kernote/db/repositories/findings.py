"""The single review queue (ADR-0007).

Persistence lives here rather than in `maintain/` because `ingest/` also needs
to raise findings, and `ARCHITECTURE.md` forbids those packages depending on
each other. Detection logic stays in `maintain/`.
"""

from __future__ import annotations

import json
import sqlite3

from ...domain.models import Finding, utc_now
from ..connection import transaction


def record(conn: sqlite3.Connection, project_id: str, finding: Finding) -> str:
    """Persist a finding, idempotently when it carries a `dedupe_key`.

    Re-running a detector must not pile up duplicate findings for the same
    cause, or the review queue becomes unusable after a few scans.

    **A closed finding suppresses its cause too.** This used to match only
    `status='open'`, so the moment a human resolved a finding the next
    `analyze` inserted an identical new one and the review queue refilled with
    exactly the item just closed -- on every scan, forever. A review that the
    product immediately discards is worse than no review.

    This puts the weight on the dedupe key: it must contain whatever would make
    the finding legitimately *new*. Drift's key carries the file's current
    content hash (`stale:{ref_id}:{hash}`), so a further edit produces a new
    key and a new finding, while the resolved one stays closed -- which is
    exactly the wanted behaviour. Conflict and duplicate keys are a pair of
    memory ids, so adjudicating that pair is final until one of them is
    replaced. That is the honest reading of a human decision, and if those
    detectors should re-raise on changed content their keys need a content
    fingerprint, not a looser query here.
    """
    with transaction(conn):
        dedupe_key = finding.evidence.get("dedupe_key")
        if dedupe_key:
            existing = conn.execute(
                "SELECT id,status FROM findings WHERE project_id=? AND kind=? "
                "AND json_extract(evidence_json,'$.dedupe_key')=? "
                "ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, created_at "
                "LIMIT 1",
                (project_id, finding.kind.value, dedupe_key),
            ).fetchone()
            if existing:
                return existing["id"]

        conn.execute(
            "INSERT INTO findings(id,project_id,kind,severity,status,memory_id,other_id,"
            "detector,evidence_json,explanation,created_at) "
            "VALUES(?,?,?,?,'open',?,?,?,?,?,?)",
            (
                finding.id,
                project_id,
                finding.kind.value,
                finding.severity.value,
                finding.memory_id,
                finding.other_id,
                finding.detector,
                json.dumps(finding.evidence),
                finding.explanation,
                utc_now(),
            ),
        )
        return finding.id


def open_findings(
    conn: sqlite3.Connection, project_id: str, kind: str | None = None
) -> list[dict]:
    return findings_by_status(conn, project_id, "open", kind)


def resolved_findings(
    conn: sqlite3.Connection,
    project_id: str,
    kind: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Recently closed findings, newest first.

    What the undo flow reads: a decision invisible in the UI cannot be taken
    back, however reversible it is underneath.
    """
    sql = "SELECT * FROM findings WHERE project_id=? AND status!='open'"
    params: list[object] = [project_id]
    if kind:
        sql += " AND kind=?"
        params.append(kind)
    sql += " ORDER BY resolved_at DESC LIMIT ?"
    params.append(limit)
    return [_decode(row) for row in conn.execute(sql, params).fetchall()]


def findings_by_status(
    conn: sqlite3.Connection,
    project_id: str,
    status: str,
    kind: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM findings WHERE project_id=? AND status=?"
    params: list[object] = [project_id, status]
    if kind:
        sql += " AND kind=?"
        params.append(kind)
    sql += (
        " ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,"
        " created_at"
    )
    return [_decode(row) for row in conn.execute(sql, params).fetchall()]


def _decode(row: sqlite3.Row) -> dict:
    record = dict(row)
    record["evidence"] = json.loads(record.pop("evidence_json"))
    return record
