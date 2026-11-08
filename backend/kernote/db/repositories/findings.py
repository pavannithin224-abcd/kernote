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
    """
    with transaction(conn):
        dedupe_key = finding.evidence.get("dedupe_key")
        if dedupe_key:
            existing = conn.execute(
                "SELECT id FROM findings WHERE project_id=? AND kind=? AND status='open' "
                "AND json_extract(evidence_json,'$.dedupe_key')=?",
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
    sql = "SELECT * FROM findings WHERE project_id=? AND status='open'"
    params: list[object] = [project_id]
    if kind:
        sql += " AND kind=?"
        params.append(kind)
    sql += (
        " ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,"
        " created_at"
    )
    rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        record_dict = dict(row)
        record_dict["evidence"] = json.loads(record_dict.pop("evidence_json"))
        out.append(record_dict)
    return out
