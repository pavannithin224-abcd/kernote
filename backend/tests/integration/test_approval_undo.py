"""Undoing an approved consolidation.

`CLAUDE.md` requires a review flow for writes to canonical memory and forbids
silent destructive merges. The flow delivered the first half: a human had to
approve, and nothing was deleted. It did not deliver the second, because an
approval could not be taken back — the lineage to reverse it was all preserved,
there was simply no path to it.

The shape of the fix is the thing worth protecting: **an undo is a forward
operation.** It writes new revisions restoring the previous state. It does not
delete the merge revisions and it does not delete the `accepted` feedback row,
because "merged, then unmerged" is what happened, and an approval a human later
took back is the single most informative signal the duplicate detector can get.
"""

from __future__ import annotations

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import MemoryStatus, Project
from kernote.ingest.pipeline import scan_project
from kernote.maintain import review
from kernote.maintain.duplicates import detect_duplicates, pending_proposals

BODY = "Run the full suite with pytest before pushing any change to main.\n"
DOCS = {
    "README.md": f"# App\n\n## Running the tests\n\n{BODY}",
    "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{BODY}",
}


@pytest.fixture
def approved(conn, tmp_path):
    """A project with one consolidation already approved."""
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    project = prepo.create(conn, Project(name="u", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    detect_duplicates(conn, project_id=project.id)
    proposals = pending_proposals(conn, project.id)
    assert proposals, "fixture produced no proposal"
    proposal = proposals[0]

    before_keep = None
    ids = None
    import json

    ids = json.loads(
        conn.execute(
            "SELECT input_ids_json FROM consolidation_proposals WHERE id=?",
            (proposal["id"],),
        ).fetchone()["input_ids_json"]
    )
    before_keep = mrepo.get(conn, ids[0])

    result = review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    assert result is not None
    return project, proposal, ids, before_keep


def test_undo_restores_both_records(approved, conn):
    project, proposal, (keep_id, absorb_id), before_keep = approved

    # Precondition: the merge really happened.
    assert mrepo.get(conn, absorb_id).status is MemoryStatus.SUPERSEDED
    assert mrepo.get(conn, absorb_id).superseded_by == keep_id

    out = review.undo_approval(
        conn, project_id=project.id, proposal_id=proposal["id"], note="changed my mind"
    )
    assert out is not None

    keep = mrepo.get(conn, keep_id)
    absorb = mrepo.get(conn, absorb_id)

    assert keep.content == before_keep.content, "the keeper's wording was not restored"
    assert {r.citation for r in keep.source_refs} == {
        r.citation for r in before_keep.source_refs
    }, "the keeper's citations were not restored to the pre-merge set"
    assert absorb.status is MemoryStatus.ACTIVE, "the absorbed record was not reopened"
    assert absorb.superseded_by is None


def test_the_merge_stays_in_the_history(approved, conn):
    """The point of the design. An undo adds to the record; it never erases."""
    project, proposal, (keep_id, absorb_id), _ = approved
    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])

    reasons = [
        r["change_reason"]
        for r in conn.execute(
            "SELECT change_reason FROM memory_revisions WHERE memory_id=? "
            "ORDER BY created_at",
            (keep_id,),
        )
    ]
    assert any(
        r.startswith(f"absorbed {absorb_id}") for r in reasons
    ), "the merge revision was deleted; an undo must not rewrite history"
    assert any("undid merge" in r for r in reasons), "the undo was not itself recorded"


def test_the_original_approval_is_still_recorded(approved, conn):
    """An approval later taken back is a stronger signal than one never made.

    Deleting the `accepted` row would make those two cases indistinguishable
    to any later tuning of the duplicate thresholds.
    """
    project, proposal, _, _ = approved
    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])

    verdicts = [
        r["verdict"]
        for r in conn.execute(
            "SELECT verdict FROM feedback WHERE target_id=? ORDER BY created_at",
            (proposal["id"],),
        )
    ]
    assert verdicts == ["accepted", "undone"], f"expected both decisions, got {verdicts}"


def test_the_proposal_becomes_reviewable_again(approved, conn):
    project, proposal, _, _ = approved
    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])

    row = conn.execute(
        "SELECT status, decided_at, result_memory_id FROM consolidation_proposals WHERE id=?",
        (proposal["id"],),
    ).fetchone()
    assert row["status"] == "pending"
    assert row["decided_at"] is None
    assert row["result_memory_id"] is None
    assert pending_proposals(conn, project.id), "the proposal did not return to the queue"


def test_the_supersedes_link_is_removed(approved, conn):
    """It asserted a relationship that is no longer true.

    Unlike the revisions, the link is derived state rather than history, so
    leaving it would put a false edge in the knowledge graph (ADR-0039).
    """
    project, proposal, (keep_id, absorb_id), _ = approved
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM memory_links "
            "WHERE src_id=? AND dst_id=? AND kind='supersedes'",
            (keep_id, absorb_id),
        ).fetchone()[0]
        == 1
    )

    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM memory_links "
            "WHERE src_id=? AND dst_id=? AND kind='supersedes'",
            (keep_id, absorb_id),
        ).fetchone()[0]
        == 0
    )


def test_undo_refuses_when_the_keeper_was_edited_after_the_merge(approved, conn):
    """The mirror of approve_proposal's own guard.

    Restoring the pre-merge wording over a human's later edit would destroy
    work that has nothing to do with the merge.
    """
    project, proposal, (keep_id, _), _ = approved
    mrepo.update(
        conn,
        keep_id,
        title=None,
        content="Rewritten by hand after the merge.",
        summary=None,
        change_reason="manual edit",
    )

    with pytest.raises(ValueError, match="edited since the merge"):
        review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])

    assert (
        mrepo.get(conn, keep_id).content == "Rewritten by hand after the merge."
    ), "the refusal must leave the edit untouched"


def test_undo_refuses_twice(approved, conn):
    project, proposal, _, _ = approved
    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])
    with pytest.raises(ValueError, match="only an approved consolidation"):
        review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])


def test_undo_refuses_on_a_proposal_that_was_never_approved(conn, tmp_path):
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    project = prepo.create(conn, Project(name="p", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    detect_duplicates(conn, project_id=project.id)
    proposal = pending_proposals(conn, project.id)[0]

    with pytest.raises(ValueError, match="only an approved consolidation"):
        review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])


def test_approve_undo_approve_is_stable(approved, conn):
    """The record must survive a round trip, not drift a little each time."""
    project, proposal, (keep_id, absorb_id), before_keep = approved

    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])
    again = review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    assert again is not None

    keep = mrepo.get(conn, keep_id)
    absorb = mrepo.get(conn, absorb_id)
    assert absorb.status is MemoryStatus.SUPERSEDED
    assert absorb.superseded_by == keep_id
    # Every citation the first merge produced is present again, exactly once.
    citations = [r.citation for r in keep.source_refs]
    assert len(citations) == len(set(citations)), f"duplicate citations: {citations}"


def test_a_second_undo_still_restores(approved, conn):
    """Regression: the undo revision used to snapshot the pre-deletion refs.

    `test_approve_undo_approve_is_stable` stops after the second approve, so
    it never read that snapshot back. The second undo then treated the merged
    ref set as the pre-merge state, removed nothing, and left the absorbed
    record's citation on the keeper while restoring the absorbed memory --
    both records claiming the same citation, the merge permanently half-undone.
    """
    project, proposal, (keep_id, _), before_keep = approved
    expected = {r.citation for r in before_keep.source_refs}

    for _ in range(2):
        review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])
        assert {r.citation for r in mrepo.get(conn, keep_id).source_refs} == expected
        review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])

    review.undo_approval(conn, project_id=project.id, proposal_id=proposal["id"])
    assert {r.citation for r in mrepo.get(conn, keep_id).source_refs} == expected


# ===================== over HTTP =====================


def test_undo_round_trip_over_the_api(client, tmp_path):
    """The whole path a user actually takes, through the endpoints.

    The repository-level tests above use a direct connection; this one proves
    the wiring — the status filter the review screen reads, the undo endpoint
    itself, and the 409 that stops a second undo.
    """
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "u", "root_path": str(tmp_path)}
    ).json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    client.post(f"/api/v1/projects/{pid}/analyze")

    pending = client.get(f"/api/v1/projects/{pid}/proposals?status=pending").json()
    assert pending, "no proposal to approve"
    proposal_id = pending[0]["id"]

    approved = client.post(
        f"/api/v1/proposals/{proposal_id}/approve?project_id={pid}", json={"note": "yes"}
    )
    assert approved.status_code == 200, approved.text

    # It must now be visible as applied, or there is nothing to undo from.
    applied = client.get(f"/api/v1/projects/{pid}/proposals?status=approved").json()
    assert [p["id"] for p in applied] == [proposal_id]
    assert applied[0]["decided_at"] is not None

    undone = client.post(
        f"/api/v1/proposals/{proposal_id}/undo?project_id={pid}", json={"note": "no"}
    )
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["restored_id"]
    assert body["citations_removed"] >= 1

    # Back in the queue, out of the applied list.
    assert client.get(f"/api/v1/projects/{pid}/proposals?status=approved").json() == []
    assert [
        p["id"] for p in client.get(f"/api/v1/projects/{pid}/proposals?status=pending").json()
    ] == [proposal_id]

    # A second undo is a conflict, not a silent no-op.
    twice = client.post(
        f"/api/v1/proposals/{proposal_id}/undo?project_id={pid}", json={"note": None}
    )
    assert twice.status_code == 409, twice.text


def test_an_unknown_proposal_status_is_rejected(client, tmp_path):
    pid = client.post(
        "/api/v1/projects", json={"name": "s", "root_path": str(tmp_path)}
    ).json()["id"]
    assert client.get(f"/api/v1/projects/{pid}/proposals?status=bogus").status_code == 422


# ===================== undoing a finding resolution =====================


def _finding_project(conn, tmp_path):
    """A project with an open finding that flags a memory for review."""
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    project = prepo.create(conn, Project(name="f", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    detect_duplicates(conn, project_id=project.id)
    rows = conn.execute(
        "SELECT id, memory_id FROM findings WHERE project_id=? AND status='open'",
        (project.id,),
    ).fetchall()
    assert rows, "fixture produced no finding"
    finding_id, memory_id = rows[0]["id"], rows[0]["memory_id"]
    # Put the memory in the state a finding leaves it in.
    conn.execute("UPDATE memories SET status='needs_review' WHERE id=?", (memory_id,))
    conn.commit()
    return project, finding_id, memory_id


def test_undo_resolution_reflags_only_what_it_changed(conn, tmp_path):
    project, finding_id, memory_id = _finding_project(conn, tmp_path)

    review.resolve_finding(
        conn, project_id=project.id, finding_id=finding_id, verdict="rejected"
    )
    assert mrepo.get(conn, memory_id).status is MemoryStatus.ACTIVE

    out = review.undo_resolution(
        conn, project_id=project.id, finding_id=finding_id, note="reopened"
    )
    assert out is not None
    assert memory_id in out.reflagged
    assert mrepo.get(conn, memory_id).status is MemoryStatus.NEEDS_REVIEW

    row = conn.execute(
        "SELECT status, resolved_at, resolution_note FROM findings WHERE id=?",
        (finding_id,),
    ).fetchone()
    assert row["status"] == "open"
    assert row["resolved_at"] is None


def test_undo_resolution_leaves_untouched_memories_alone(conn, tmp_path):
    """The reason the effect is recorded instead of inferred.

    A memory that was already `active` when the finding was resolved was never
    flipped by it. Re-flagging that one on undo would invent a review
    requirement no human ever asked for.
    """
    project, finding_id, memory_id = _finding_project(conn, tmp_path)
    other_id = conn.execute(
        "SELECT other_id FROM findings WHERE id=?", (finding_id,)
    ).fetchone()["other_id"]
    if other_id is None:
        pytest.skip("this finding names only one memory")

    # The second memory is active and stays active throughout.
    conn.execute("UPDATE memories SET status='active' WHERE id=?", (other_id,))
    conn.commit()

    review.resolve_finding(
        conn, project_id=project.id, finding_id=finding_id, verdict="rejected"
    )
    review.undo_resolution(conn, project_id=project.id, finding_id=finding_id)

    assert mrepo.get(conn, memory_id).status is MemoryStatus.NEEDS_REVIEW
    assert (
        mrepo.get(conn, other_id).status is MemoryStatus.ACTIVE
    ), "a memory the resolution never touched was re-flagged"


def test_undo_resolution_keeps_both_decisions(conn, tmp_path):
    project, finding_id, _ = _finding_project(conn, tmp_path)
    review.resolve_finding(
        conn, project_id=project.id, finding_id=finding_id, verdict="rejected"
    )
    review.undo_resolution(conn, project_id=project.id, finding_id=finding_id)

    verdicts = [
        r["verdict"]
        for r in conn.execute(
            "SELECT verdict FROM feedback WHERE target_id=? ORDER BY created_at",
            (finding_id,),
        )
    ]
    assert verdicts == ["rejected", "undone"]


def test_undo_resolution_refuses_on_an_open_finding(conn, tmp_path):
    project, finding_id, _ = _finding_project(conn, tmp_path)
    with pytest.raises(ValueError, match="already open"):
        review.undo_resolution(conn, project_id=project.id, finding_id=finding_id)


def test_a_finding_closed_by_a_merge_must_be_undone_through_the_merge(approved, conn):
    """Otherwise the merge stays applied while its finding reads open.

    The two would then contradict each other: a conflict the queue says is
    unresolved, over two memories one of which no longer exists separately.
    """
    project, proposal, _, _ = approved
    finding_id = conn.execute(
        "SELECT finding_id FROM consolidation_proposals WHERE id=?", (proposal["id"],)
    ).fetchone()["finding_id"]
    if finding_id is None:
        pytest.skip("this proposal has no originating finding")

    with pytest.raises(ValueError, match="undo that consolidation instead"):
        review.undo_resolution(conn, project_id=project.id, finding_id=finding_id)
