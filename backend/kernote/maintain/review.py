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
from ..domain.models import MemoryStatus, new_id, utc_now
from .duplicates import content_fingerprint

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

        # A proposal is a contract. If either record was edited after the
        # preview was built, applying the stored merged content would silently
        # overwrite the newer wording -- losing a human's own edit, which is
        # the worst thing this feature could do.
        fingerprints = preview.get("input_fingerprints") or {}
        for memory in (keep_before, absorb_before):
            expected = fingerprints.get(memory.id)
            if expected is None:
                continue  # proposal predates fingerprinting; fall through
            if content_fingerprint(memory.content) != expected:
                raise ValueError(
                    f"memory {memory.id} has been edited since this proposal was "
                    "created, so the preview no longer describes the result. "
                    "Re-run analysis to get a fresh proposal."
                )

        # Merging into a record nobody will see is not a merge.
        for memory, role in ((keep_before, "keeper"), (absorb_before, "absorbed")):
            if memory.status in (MemoryStatus.ARCHIVED, MemoryStatus.SUPERSEDED):
                raise ValueError(
                    f"the {role} memory {memory.id} is {memory.status.value}; "
                    "consolidation needs two live records"
                )

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


@dataclass
class UndoResult:
    proposal_id: str
    kept_id: str
    restored_id: str
    citations_removed: int
    content_restored: bool


def undo_approval(
    conn: sqlite3.Connection, *, project_id: str, proposal_id: str, note: str | None = None
) -> UndoResult | None:
    """Reverse an approved consolidation.

    **An undo is a forward operation, not an erasure.** It writes new
    revisions restoring the previous state; it does not delete the merge
    revisions, and it does not delete the `accepted` feedback row. The history
    reads "merged, then unmerged", because that is what happened. Deleting the
    merge from the record would be the silent rewriting `CLAUDE.md` forbids,
    and it would also destroy the most informative signal the duplicate
    detector can get -- an approval a human later took back.

    This is possible at all because `memory_revisions.snapshot_json` holds the
    complete record at every revision, including its source refs, and
    `parent_id` chains them. The pre-merge state is simply the parent of the
    revision the merge wrote.

    It refuses rather than guesses in three cases, each of which would mean
    destroying something that is not part of the merge:

    * the keeper has been **edited since** the merge -- restoring the old
      content would discard that edit, exactly the failure `approve_proposal`
      already guards against in the other direction;
    * the absorbed record has since been superseded by something **else**;
    * either record is gone.
    """
    with transaction(conn):
        row = conn.execute(
            "SELECT id,status,input_ids_json,finding_id FROM consolidation_proposals "
            "WHERE id=? AND project_id=?",
            (proposal_id, project_id),
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "approved":
            raise ValueError(
                f"proposal {proposal_id} is {row['status']}; only an approved "
                "consolidation can be undone"
            )

        keep_id, absorb_id = json.loads(row["input_ids_json"])
        keep = mrepo.get(conn, keep_id)
        absorb = mrepo.get(conn, absorb_id)
        if keep is None or absorb is None:
            raise ValueError("a memory in this proposal no longer exists")

        if absorb.superseded_by != keep_id:
            raise ValueError(
                f"memory {absorb_id} is no longer superseded by {keep_id}, so this "
                "merge is not the most recent thing that happened to it"
            )

        # The revision the merge wrote on the keeper, and the state before it.
        merge_rev = conn.execute(
            "SELECT id,parent_id FROM memory_revisions "
            "WHERE memory_id=? AND change_reason LIKE ? "
            "ORDER BY created_at DESC LIMIT 1",
            (keep_id, f"absorbed {absorb_id}:%"),
        ).fetchone()
        if merge_rev is None:
            raise ValueError("no merge revision found for this consolidation")

        current = conn.execute(
            "SELECT current_revision FROM memories WHERE id=?", (keep_id,)
        ).fetchone()["current_revision"]
        if current != merge_rev["id"]:
            raise ValueError(
                f"memory {keep_id} has been edited since the merge, so undoing "
                "would discard that edit. Edit it by hand instead."
            )
        if merge_rev["parent_id"] is None:
            raise ValueError("the merge revision has no parent to restore from")

        before_row = conn.execute(
            "SELECT snapshot_json FROM memory_revisions WHERE id=?",
            (merge_rev["parent_id"],),
        ).fetchone()
        if before_row is None:
            raise ValueError("the pre-merge revision is missing")
        before = json.loads(before_row["snapshot_json"])

        # Restore the keeper's citations to exactly the pre-merge set. The
        # refs carried over from the absorbed record are the ones that go;
        # rebuilding from the snapshot avoids having to have recorded which.
        if "source_refs" not in before:
            # Defaulting to an empty set here would delete every citation on
            # the keeper -- the one thing `supersede_into` promises can never
            # happen. Every other unknown in this function refuses; so does
            # this one.
            raise ValueError(
                "the pre-merge revision records no source refs, so the citations "
                "to restore are unknown. Refusing rather than stripping provenance."
            )
        kept_keys = {
            (
                r.get("rel_path"),
                r.get("line_start"),
                r.get("line_end"),
                r.get("url"),
                r.get("user_note"),
            )
            for r in before["source_refs"]
        }
        removed = 0
        for ref in conn.execute(
            "SELECT id,rel_path,line_start,line_end,url,user_note "
            "FROM memory_source_refs WHERE memory_id=?",
            (keep_id,),
        ).fetchall():
            key = (
                ref["rel_path"],
                ref["line_start"],
                ref["line_end"],
                ref["url"],
                ref["user_note"],
            )
            if key not in kept_keys:
                conn.execute("DELETE FROM memory_source_refs WHERE id=?", (ref["id"],))
                removed += 1

        restored_content = before["content"]
        content_changed = restored_content != keep.content

        undo_reason = note or "approval undone"
        keep_rev = new_id()
        conn.execute(
            "UPDATE memories SET content=?,updated_at=?,current_revision=? WHERE id=?",
            (restored_content, utc_now(), keep_rev, keep_id),
        )
        # Re-read after the deletions: `keep` was fetched at the top of this
        # function and still carries the merged refs. Snapshotting that would
        # record provenance the undo has just removed -- and a later undo,
        # reading this revision as its pre-merge state, would restore nothing
        # and leave the absorbed record's citations on the keeper for good.
        restored_keep = mrepo.get(conn, keep_id)
        if restored_keep is None:
            raise ValueError(f"memory {keep_id} vanished during undo")
        mrepo.write_revision(
            conn,
            restored_keep,
            keep_rev,
            merge_rev["id"],
            f"undid merge of {absorb_id}: {undo_reason} ({removed} citation(s) removed)",
            "user",
        )

        # Reopen the absorbed record.
        absorb_parent = conn.execute(
            "SELECT current_revision FROM memories WHERE id=?", (absorb_id,)
        ).fetchone()["current_revision"]
        absorb_rev = new_id()
        prior_valid_until = None
        prior = conn.execute(
            "SELECT snapshot_json FROM memory_revisions WHERE id=?", (absorb_parent,)
        ).fetchone()
        if prior is not None:
            prior_valid_until = json.loads(prior["snapshot_json"]).get("valid_until")
        conn.execute(
            "UPDATE memories SET superseded_by=NULL,status=?,updated_at=?,valid_until=?,"
            "current_revision=? WHERE id=?",
            (
                MemoryStatus.ACTIVE.value,
                utc_now(),
                prior_valid_until,
                absorb_rev,
                absorb_id,
            ),
        )
        mrepo.write_revision(
            conn,
            absorb.model_copy(
                update={
                    "superseded_by": None,
                    "status": MemoryStatus.ACTIVE,
                    "valid_until": prior_valid_until,
                }
            ),
            absorb_rev,
            absorb_parent,
            f"restored from merge into {keep_id}: {undo_reason}",
            "user",
        )

        # The link asserted a relationship that no longer holds. It is derived
        # state, not history -- the revisions above are the history.
        conn.execute(
            "DELETE FROM memory_links WHERE src_id=? AND dst_id=? AND kind='supersedes'",
            (keep_id, absorb_id),
        )

        # The proposal becomes undecided again, so it can be reviewed afresh.
        conn.execute(
            "UPDATE consolidation_proposals SET status='pending',decided_at=NULL,"
            "result_memory_id=NULL WHERE id=?",
            (proposal_id,),
        )
        if row["finding_id"]:
            conn.execute(
                "UPDATE findings SET status='open',resolved_at=NULL,resolution_note=NULL "
                "WHERE id=?",
                (row["finding_id"],),
            )
        _feedback(conn, project_id, "proposal", proposal_id, "undone", note)

        log.info(
            "review.approval_undone",
            project_id=project_id,
            proposal_id=proposal_id,
            kept=keep_id,
            restored=absorb_id,
            citations_removed=removed,
        )
        return UndoResult(
            proposal_id=proposal_id,
            kept_id=keep_id,
            restored_id=absorb_id,
            citations_removed=removed,
            content_restored=content_changed,
        )


@dataclass
class FindingUndoResult:
    finding_id: str
    reflagged: list[str]


def undo_resolution(
    conn: sqlite3.Connection, *, project_id: str, finding_id: str, note: str | None = None
) -> FindingUndoResult | None:
    """Reopen a resolved finding and put back what resolving it changed.

    The same principle as `undo_approval` (ADR-0040): the decision stays in
    the feedback log and an `undone` row is added beside it. A finding
    reopened by a human is a different, more informative thing than one never
    closed, and collapsing the two would lose that.

    Only the memories this resolution actually flipped are flipped back --
    read from `findings.effect_json`, written when the resolution ran. A
    resolution recorded before migration 0009 has no effect record, and this
    says so rather than guessing which memories to re-flag.
    """
    with transaction(conn):
        row = conn.execute(
            "SELECT id,status,effect_json FROM findings WHERE id=? AND project_id=?",
            (finding_id, project_id),
        ).fetchone()
        if row is None:
            return None
        if row["status"] == "open":
            raise ValueError(f"finding {finding_id} is already open")

        # A finding closed by approving a consolidation must be reopened by
        # undoing that consolidation, which also unpicks the merge. Reopening
        # it here would leave the merge applied and the finding open --
        # contradicting each other.
        proposal = conn.execute(
            "SELECT id FROM consolidation_proposals "
            "WHERE finding_id=? AND status='approved'",
            (finding_id,),
        ).fetchone()
        if proposal is not None:
            raise ValueError(
                f"finding {finding_id} was closed by approving consolidation "
                f"{proposal['id']}; undo that consolidation instead"
            )

        if row["effect_json"] is None:
            raise ValueError(
                f"finding {finding_id} was resolved before its effect was recorded "
                "(migration 0009), so what to restore is unknown. Re-run analysis "
                "to raise it again."
            )

        effect = json.loads(row["effect_json"])
        reflagged = []
        for item in effect:
            memory_id = item["memory_id"]
            current = conn.execute(
                "SELECT status FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
            if current is None:
                continue
            # Only put back what this resolution changed. If the memory has
            # moved on since -- archived, superseded, edited into review again
            # -- leave it alone rather than overwrite a later decision.
            if current["status"] != "active":
                continue
            conn.execute(
                "UPDATE memories SET status=?,updated_at=?,last_verified_at=? WHERE id=?",
                (
                    item.get("prior_status") or "needs_review",
                    utc_now(),
                    item.get("prior_last_verified_at"),
                    memory_id,
                ),
            )
            reflagged.append(memory_id)

        conn.execute(
            "UPDATE findings SET status='open',resolved_at=NULL,resolution_note=NULL,"
            "effect_json=NULL WHERE id=?",
            (finding_id,),
        )
        _feedback(conn, project_id, "finding", finding_id, "undone", note)

        log.info(
            "review.resolution_undone",
            project_id=project_id,
            finding_id=finding_id,
            reflagged=len(reflagged),
        )
        return FindingUndoResult(finding_id=finding_id, reflagged=reflagged)


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
        # What this resolution changes, written down so it can be reversed.
        # These status flips write no revision, so without this record an undo
        # would have to guess -- and the obvious guess is wrong, because a
        # memory already 'active' beforehand was never touched (migration
        # 0009, ADR-0041).
        effect = []
        if verdict in ("rejected", "resolved"):
            for memory_id in (row["memory_id"], row["other_id"]):
                if not memory_id:
                    continue
                current = conn.execute(
                    "SELECT status, last_verified_at FROM memories WHERE id=?", (memory_id,)
                ).fetchone()
                if current is None or current["status"] != "needs_review":
                    continue
                effect.append(
                    {
                        "memory_id": memory_id,
                        "prior_status": current["status"],
                        "prior_last_verified_at": current["last_verified_at"],
                    }
                )
                conn.execute(
                    "UPDATE memories SET status='active',updated_at=?,"
                    "last_verified_at=? WHERE id=?",
                    (utc_now(), utc_now() if reverify else None, memory_id),
                )
                restored.append(memory_id)

        conn.execute(
            "UPDATE findings SET effect_json=? WHERE id=?",
            (json.dumps(effect), finding_id),
        )

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
