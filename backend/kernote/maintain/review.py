"""The review flow: approving proposals and resolving findings (Stage 6).

This is where ADR-0007's "a finding is a request for review, never a verdict"
and `CLAUDE.md`'s "no silent destructive memory merges" become code rather than
intent. Nothing in `maintain/` writes to canonical memory except through here,
and everything here is initiated by a human decision that is recorded.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Literal

import structlog

from ..db.connection import transaction
from ..db.repositories import memories as mrepo
from ..domain.models import new_id, utc_now

log = structlog.get_logger(__name__)

Verdict = Literal["accepted", "rejected", "resolved"]


@dataclass
class ApprovalResult:
    proposal_id: str
    kept_id: str
    absorbed_id: str
    citations_before: int
    citations_after: int
    revisions_written: int


def _feedback(
    conn: sqlite3.Connection,
    project_id: str,
    target_kind: str,
    target_id: str,
    verdict: str,
    note: str | None,
) -> None:
    """Record the decision.

    MEMORY_MODEL stage 9 is explicit feedback only: this is what a human chose,
    never inferred, and it is what later tuning of thresholds must rest on.
    """
    conn.execute(
        "INSERT INTO feedback(id,project_id,target_kind,target_id,verdict,note,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (new_id(), project_id, target_kind, target_id, verdict, note, utc_now()),
    )


def approve_proposal(
    conn: sqlite3.Connection, *, project_id: str, proposal_id: str, note: str | None = None
) -> ApprovalResult | None:
    """Apply a consolidation. One transaction, nothing deleted."""
    with transaction(conn):
        row = conn.execute(
            "SELECT id,status,input_ids_json,preview_json,finding_id "
            "FROM consolidation_proposals WHERE id=? AND project_id=?",
            (proposal_id, project_id),
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "pending":
            raise ValueError(f"proposal {proposal_id} is already {row['status']}")

        keep_id, absorb_id = json.loads(row["input_ids_json"])
        preview = json.loads(row["preview_json"])
        merged_content = preview["after"]["content"]
        promised = set(preview["after"]["citations"])

        keep_before = mrepo.get(conn, keep_id)
        absorb_before = mrepo.get(conn, absorb_id)
        if keep_before is None or absorb_before is None:
            raise ValueError("a memory in this proposal no longer exists")
        citations_before = len(keep_before.source_refs)

        merged = mrepo.supersede_into(
            conn,
            absorb_id=absorb_id,
            keep_id=keep_id,
            merged_content=merged_content,
            reason=note or "approved consolidation",
        )
        if merged is None:
            raise ValueError("merge failed: a memory in this proposal is missing")
        kept, _absorbed = merged

        # The preview promised these citations would survive. Verify rather
        # than trust: a merge that quietly drops provenance is the one thing
        # this feature must never do.
        actual = {r.citation for r in kept.source_refs}
        missing = promised - actual
        if missing:
            raise ValueError(f"merge would have lost citations {sorted(missing)}; rolled back")

        conn.execute(
            "UPDATE consolidation_proposals SET status='approved',decided_at=?,"
            "result_memory_id=? WHERE id=?",
            (utc_now(), keep_id, proposal_id),
        )
        if row["finding_id"]:
            conn.execute(
                "UPDATE findings SET status='accepted',resolved_at=?,resolution_note=? "
                "WHERE id=?",
                (utc_now(), note or "consolidation approved", row["finding_id"]),
            )
        _feedback(conn, project_id, "proposal", proposal_id, "accepted", note)

        log.info(
            "review.proposal_approved",
            project_id=project_id,
            proposal_id=proposal_id,
            kept=keep_id,
            absorbed=absorb_id,
            citations=len(actual),
        )
        return ApprovalResult(
            proposal_id=proposal_id,
            kept_id=keep_id,
            absorbed_id=absorb_id,
            citations_before=citations_before,
            citations_after=len(actual),
            revisions_written=2,
        )


def reject_proposal(
    conn: sqlite3.Connection, *, project_id: str, proposal_id: str, note: str | None = None
) -> bool:
    """Decline a consolidation. Both memories are left exactly as they were."""
    with transaction(conn):
        row = conn.execute(
            "SELECT status,finding_id FROM consolidation_proposals "
            "WHERE id=? AND project_id=?",
            (proposal_id, project_id),
        ).fetchone()
        if row is None:
            return False
        if row["status"] != "pending":
            raise ValueError(f"proposal {proposal_id} is already {row['status']}")
        conn.execute(
            "UPDATE consolidation_proposals SET status='rejected',decided_at=? WHERE id=?",
            (utc_now(), proposal_id),
        )
        if row["finding_id"]:
            conn.execute(
                "UPDATE findings SET status='rejected',resolved_at=?,resolution_note=? "
                "WHERE id=?",
                (utc_now(), note or "not a duplicate", row["finding_id"]),
            )
        _feedback(conn, project_id, "proposal", proposal_id, "rejected", note)
        log.info("review.proposal_rejected", project_id=project_id, proposal_id=proposal_id)
        return True


def resolve_finding(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    finding_id: str,
    verdict: Verdict,
    note: str | None = None,
    reverify: bool = True,
) -> dict | None:
    """Close a finding with a recorded human decision.

    `accepted` means "yes, this needs attention" and leaves the memory flagged.
    `rejected` means "this is a false positive"; the memory returns to `active`
    and, when `reverify` is set, its `last_verified_at` is stamped so the same
    unchanged source does not raise it again.
    """
    if verdict not in ("accepted", "rejected", "resolved"):
        raise ValueError(f"unknown verdict: {verdict}")

    with transaction(conn):
        row = conn.execute(
            "SELECT id,status,memory_id,other_id,kind FROM findings "
            "WHERE id=? AND project_id=?",
            (finding_id, project_id),
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "open":
            raise ValueError(f"finding {finding_id} is already {row['status']}")

        conn.execute(
            "UPDATE findings SET status=?,resolved_at=?,resolution_note=? WHERE id=?",
            (verdict, utc_now(), note, finding_id),
        )

        restored = []
        if verdict in ("rejected", "resolved"):
            for memory_id in (row["memory_id"], row["other_id"]):
                if not memory_id:
                    continue
                current = conn.execute(
                    "SELECT status FROM memories WHERE id=?", (memory_id,)
                ).fetchone()
                if current is None or current["status"] != "needs_review":
                    continue
                conn.execute(
                    "UPDATE memories SET status='active',updated_at=?,"
                    "last_verified_at=? WHERE id=?",
                    (utc_now(), utc_now() if reverify else None, memory_id),
                )
                restored.append(memory_id)

        _feedback(conn, project_id, "finding", finding_id, verdict, note)
        log.info(
            "review.finding_resolved",
            project_id=project_id,
            finding_id=finding_id,
            verdict=verdict,
            restored=len(restored),
        )
        return {
            "finding_id": finding_id,
            "verdict": verdict,
            "kind": row["kind"],
            "memories_returned_to_active": restored,
        }
