"""The single review queue (ADR-0007).

A finding is a *request for review*, never a verdict. It carries a detector id,
machine-readable evidence and an explanation, so the person reviewing it can
see exactly what triggered it and disagree.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Literal

from ..db.connection import transaction
from ..domain.models import new_id, utc_now

FindingKind = Literal["stale_risk", "conflict", "duplicate", "broken_link", "missing_doc"]
Severity = Literal["low", "medium", "high"]


@dataclass
class Finding:
    kind: FindingKind
    severity: Severity
    detector: str
    explanation: str
    memory_id: str | None = None
    other_id: str | None = None
    evidence: dict = field(default_factory=dict)
    id: str = field(default_factory=new_id)


def record(conn: sqlite3.Connection, project_id: str, finding: Finding) -> str:
    """Persist a finding. Idempotent per (kind, memory_id, other_id, evidence key).

    Re-running a detector must not pile up duplicate findings for the same
    cause, or the review queue becomes unusable after a few scans.
    """
    with transaction(conn):
        dedupe_key = finding.evidence.get("dedupe_key")
        if dedupe_key:
            existing = conn.execute(
                "SELECT id FROM findings WHERE project_id=? AND kind=? AND status='open' "
                "AND json_extract(evidence_json,'$.dedupe_key')=?",
                (project_id, finding.kind, dedupe_key),
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
                finding.kind,
                finding.severity,
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
        " ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at"
    )
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["evidence"] = json.loads(d.pop("evidence_json"))
        out.append(d)
    return out
