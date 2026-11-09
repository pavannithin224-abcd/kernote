"""Stage 6: the review flow — approval, resolution, change impact.

This is where `CLAUDE.md`'s "no silent destructive memory merges" and
ADR-0007's "a finding is a request for review, never a verdict" stop being
intent and become enforced behaviour.
"""

import subprocess

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.db.repositories.findings import open_findings
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project
from kernote.maintain import impact, review
from kernote.maintain.duplicates import detect_duplicates, pending_proposals

BODY = "Run the full suite with pytest before pushing any change to main.\n"
DUPLICATE_DOCS = {
    "README.md": f"# App\n\n## Running the tests\n\n{BODY}",
    "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{BODY}",
}


def _with_proposal(conn, tmp_path):
    for name, text in DUPLICATE_DOCS.items():
        (tmp_path / name).write_text(text)
    project = prepo.create(conn, Project(name="r", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    detect_duplicates(conn, project_id=project.id)
    proposals = pending_proposals(conn, project.id)
    assert proposals, "fixture produced no proposal"
    return project, proposals[0]


# ===================== approval keeps its promise =====================


def test_approval_preserves_every_citation(conn, tmp_path):
    """The preview promises no citation is lost. That is the whole basis for
    letting a human approve a merge they have only skim-read."""
    project, proposal = _with_proposal(conn, tmp_path)
    promised = set(proposal["preview"]["after"]["citations"])
    keep_id, absorb_id = proposal["input_ids"]

    result = review.approve_proposal(
        conn, project_id=project.id, proposal_id=proposal["id"], note="same instruction"
    )
    assert result is not None
    kept = mrepo.get(conn, keep_id)
    actual = {r.citation for r in kept.source_refs}
    assert promised <= actual, f"lost {promised - actual}"
    assert result.citations_after >= result.citations_before + 1
    assert absorb_id  # used below


def test_absorbed_record_is_superseded_never_deleted(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, absorb_id = proposal["input_ids"]
    before = mrepo.get(conn, absorb_id)

    review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])

    after = mrepo.get(conn, absorb_id)
    assert after is not None, "invariant 5: the record must stay fetchable"
    assert after.status.value == "superseded"
    assert after.superseded_by == keep_id
    assert after.content == before.content, "the absorbed wording was altered"
    assert after.valid_until, "supersession must close the validity window"
    # Hidden from current listings, still reachable explicitly.
    listed = {m.id for m in mrepo.list_for_project(conn, project.id, limit=200)}
    assert absorb_id not in listed and keep_id in listed
    assert absorb_id in {
        m.id for m in mrepo.list_for_project(conn, project.id, limit=200, include_inactive=True)
    }


def test_approval_writes_revisions_on_both_records(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, absorb_id = proposal["input_ids"]
    before_keep = len(mrepo.revisions(conn, keep_id))
    before_absorb = len(mrepo.revisions(conn, absorb_id))

    review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])

    assert len(mrepo.revisions(conn, keep_id)) == before_keep + 1
    assert len(mrepo.revisions(conn, absorb_id)) == before_absorb + 1
    reasons = " ".join(r["change_reason"] for r in mrepo.revisions(conn, absorb_id))
    assert "merged into" in reasons


def test_approval_records_the_decision(conn, tmp_path):
    """Explicit feedback only (MEMORY_MODEL stage 9): this is what a human
    chose, and it is what later threshold tuning must rest on."""
    project, proposal = _with_proposal(conn, tmp_path)
    review.approve_proposal(
        conn, project_id=project.id, proposal_id=proposal["id"], note="clearly the same"
    )
    row = conn.execute(
        "SELECT target_kind,verdict,note FROM feedback WHERE target_id=?",
        (proposal["id"],),
    ).fetchone()
    assert row["target_kind"] == "proposal"
    assert row["verdict"] == "accepted"
    assert row["note"] == "clearly the same"
    assert open_findings(conn, project.id, kind="duplicate") == []


def test_double_approval_is_refused(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    with pytest.raises(ValueError, match="already approved"):
        review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])


def test_rejection_leaves_both_memories_untouched(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, absorb_id = proposal["input_ids"]
    before = {mid: mrepo.get(conn, mid) for mid in (keep_id, absorb_id)}

    assert review.reject_proposal(
        conn, project_id=project.id, proposal_id=proposal["id"], note="different tasks"
    )

    for mid, snapshot in before.items():
        now = mrepo.get(conn, mid)
        assert now.status == snapshot.status
        assert now.superseded_by is None
        assert now.content == snapshot.content
        assert len(now.source_refs) == len(snapshot.source_refs)
    assert pending_proposals(conn, project.id) == []


def test_merging_a_memory_into_itself_is_refused(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, _ = proposal["input_ids"]
    with pytest.raises(ValueError, match="into itself"):
        mrepo.supersede_into(
            conn, absorb_id=keep_id, keep_id=keep_id, merged_content="x", reason="r"
        )


def test_merge_across_projects_is_refused(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    other_root = tmp_path / "other"
    other_root.mkdir()
    (other_root / "README.md").write_text(
        "# Other\n\n## Deployment notes\n\n"
        "This unrelated project deploys to a single host behind a reverse proxy.\n"
    )
    other = prepo.create(conn, Project(name="o", root_path=str(other_root)))
    scan_project(
        conn, project_id=other.id, root=other_root, max_file_bytes=1_000_000, max_files=50
    )
    foreign = mrepo.list_for_project(conn, other.id, limit=10)[0]
    keep_id, _ = proposal["input_ids"]
    with pytest.raises(ValueError, match="across projects"):
        mrepo.supersede_into(
            conn, absorb_id=foreign.id, keep_id=keep_id, merged_content="x", reason="r"
        )


def test_approving_an_unknown_proposal_returns_none(conn, tmp_path):
    project, _ = _with_proposal(conn, tmp_path)
    assert review.approve_proposal(conn, project_id=project.id, proposal_id="nope") is None


# ===================== finding resolution =====================


def _conflict_project(conn, tmp_path):
    (tmp_path / "README.md").write_text(
        "# App\n\n## Testing\n\nRun:\n\n```bash\npytest -q\n```\n"
    )
    (tmp_path / "CONTRIBUTING.md").write_text(
        "# Contributing\n\n## Testing\n\nAlways:\n\n```bash\ntox -e py312\n```\n"
    )
    project = prepo.create(conn, Project(name="c", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    from kernote.maintain.conflicts import detect_conflicts

    detect_conflicts(conn, project_id=project.id)
    findings = open_findings(conn, project.id, kind="conflict")
    assert findings
    return project, findings[0]


def test_resolving_a_finding_records_a_verdict(conn, tmp_path):
    project, finding = _conflict_project(conn, tmp_path)
    result = review.resolve_finding(
        conn,
        project_id=project.id,
        finding_id=finding["id"],
        verdict="accepted",
        note="README is authoritative",
    )
    assert result["verdict"] == "accepted"
    assert open_findings(conn, project.id, kind="conflict") == []
    row = conn.execute(
        "SELECT verdict,note FROM feedback WHERE target_id=?", (finding["id"],)
    ).fetchone()
    assert row["verdict"] == "accepted" and row["note"] == "README is authoritative"


def test_rejecting_a_finding_returns_memories_to_active(conn, tmp_path):
    """A dismissed false positive must not keep the memory flagged, and must
    stamp last_verified_at so the same unchanged source does not re-raise it."""
    project, finding = _conflict_project(conn, tmp_path)
    conn.execute(
        "UPDATE memories SET status='needs_review' WHERE id IN (?,?)",
        (finding["memory_id"], finding["other_id"]),
    )
    result = review.resolve_finding(
        conn,
        project_id=project.id,
        finding_id=finding["id"],
        verdict="rejected",
        note="both are valid in different contexts",
    )
    assert result["memories_returned_to_active"]
    for memory_id in result["memories_returned_to_active"]:
        memory = mrepo.get(conn, memory_id)
        assert memory.status.value == "active"
        assert memory.last_verified_at


def test_resolution_never_edits_memory_content(conn, tmp_path):
    """Resolving a conflict must not pick a winner (ADR-0007)."""
    project, finding = _conflict_project(conn, tmp_path)
    before = {
        mid: mrepo.get(conn, mid).content for mid in (finding["memory_id"], finding["other_id"])
    }
    review.resolve_finding(
        conn, project_id=project.id, finding_id=finding["id"], verdict="resolved"
    )
    for mid, content in before.items():
        assert mrepo.get(conn, mid).content == content


def test_double_resolution_is_refused(conn, tmp_path):
    project, finding = _conflict_project(conn, tmp_path)
    review.resolve_finding(
        conn, project_id=project.id, finding_id=finding["id"], verdict="accepted"
    )
    with pytest.raises(ValueError, match="already accepted"):
        review.resolve_finding(
            conn, project_id=project.id, finding_id=finding["id"], verdict="rejected"
        )


def test_unknown_verdict_is_refused(conn, tmp_path):
    project, finding = _conflict_project(conn, tmp_path)
    with pytest.raises(ValueError, match="unknown verdict"):
        review.resolve_finding(
            conn, project_id=project.id, finding_id=finding["id"], verdict="maybe"
        )


# ===================== change impact =====================


def _git_repo(tmp_path):
    def git(*args):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    return git


def test_impact_reports_only_overlapping_citations(conn, tmp_path):
    """The discriminator: a memory whose file changed but whose cited lines did
    not move is not "directly affected"."""
    git = _git_repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "# App\n\n"
        "## Architecture\n\nThe render package produces SVG output here.\n\n"
        "## Testing\n\nRun the suite with pytest before pushing.\n"
    )
    git("add", "-A")
    git("commit", "-q", "-m", "initial")

    project = prepo.create(conn, Project(name="i", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )

    # Change only the Architecture paragraph.
    (tmp_path / "README.md").write_text(
        "# App\n\n"
        "## Architecture\n\nThe render package now produces PNG output here.\n\n"
        "## Testing\n\nRun the suite with pytest before pushing.\n"
    )
    git("add", "-A")
    git("commit", "-q", "-m", "swap svg for png")

    report = impact.analyse(
        conn, project_id=project.id, root=tmp_path, base="HEAD~1", head="HEAD"
    )
    assert report.resolved
    assert "README.md" in report.changed_files
    assert report.affected, "no memories reported at all"
    direct = [a for a in report.affected if a.overlap == "direct"]
    nearby = [a for a in report.affected if a.overlap == "same_file"]
    assert direct, "the edited section was not flagged"
    assert any("Architecture" in a.title for a in direct)
    assert nearby, "every memory in the file was flagged; the overlap test is not working"
    assert not any("Architecture" in a.title for a in nearby)


def test_impact_handles_an_unknown_ref(conn, tmp_path):
    _git_repo(tmp_path)
    (tmp_path / "README.md").write_text("# App\n\n## Notes\n\nSomething here to index.\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "x"], check=True, capture_output=True
    )
    project = prepo.create(conn, Project(name="i", root_path=str(tmp_path)))
    report = impact.analyse(
        conn, project_id=project.id, root=tmp_path, base="no-such-ref", head="HEAD"
    )
    assert not report.resolved
    assert report.note and "Could not resolve" in report.note
    assert report.affected == []


def test_impact_outside_a_git_repository_degrades(conn, tmp_path):
    (tmp_path / "README.md").write_text("# App\n\n## Notes\n\nSomething here to index.\n")
    project = prepo.create(conn, Project(name="i", root_path=str(tmp_path)))
    report = impact.analyse(
        conn, project_id=project.id, root=tmp_path, base="HEAD~1", head="HEAD"
    )
    assert not report.resolved
    assert report.note


# ===================== API =====================


def test_review_endpoints(client, tmp_path):
    for name, text in DUPLICATE_DOCS.items():
        (tmp_path / name).write_text(text)
    pid = client.post(
        "/api/v1/projects", json={"name": "r", "root_path": str(tmp_path)}
    ).json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    client.post(f"/api/v1/projects/{pid}/analyze")

    proposals = client.get(f"/api/v1/projects/{pid}/proposals").json()
    assert proposals
    proposal_id = proposals[0]["id"]

    res = client.post(
        f"/api/v1/proposals/{proposal_id}/approve?project_id={pid}",
        json={"note": "same instruction"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["citations_after"] >= body["citations_before"]

    # Approving twice is a conflict, not a crash.
    again = client.post(
        f"/api/v1/proposals/{proposal_id}/approve?project_id={pid}", json={"note": None}
    )
    assert again.status_code == 409


def test_resolve_endpoint_and_impact_endpoint(client, tmp_path):
    (tmp_path / "README.md").write_text(
        "# App\n\n## Testing\n\nRun:\n\n```bash\npytest -q\n```\n"
    )
    (tmp_path / "CONTRIBUTING.md").write_text(
        "# Contributing\n\n## Testing\n\nAlways:\n\n```bash\ntox -e py312\n```\n"
    )
    pid = client.post(
        "/api/v1/projects", json={"name": "c", "root_path": str(tmp_path)}
    ).json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    client.post(f"/api/v1/projects/{pid}/analyze")

    findings = client.get(f"/api/v1/projects/{pid}/findings?kind=conflict").json()
    assert findings
    res = client.post(
        f"/api/v1/findings/{findings[0]['id']}/resolve?project_id={pid}",
        json={"verdict": "rejected", "note": "both valid"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["verdict"] == "rejected"

    # Not a git repo, so impact degrades rather than failing.
    impact_res = client.get(f"/api/v1/projects/{pid}/impact?base=HEAD~1")
    assert impact_res.status_code == 200
    assert impact_res.json()["resolved"] is False


def test_resolve_rejects_a_bad_verdict(client, tmp_path):
    (tmp_path / "README.md").write_text("# A\n\n## Notes\n\nSomething here to index.\n")
    pid = client.post(
        "/api/v1/projects", json={"name": "v", "root_path": str(tmp_path)}
    ).json()["id"]
    res = client.post(
        f"/api/v1/findings/whatever/resolve?project_id={pid}",
        json={"verdict": "maybe"},
    )
    assert res.status_code == 422


# ===================== Stage 6 defect sweep regressions =====================


def test_approval_refuses_a_stale_proposal(conn, tmp_path):
    """The worst bug in Stage 6: the merged content is computed at detection
    time, so approving after someone edits the keeper silently overwrote their
    wording. A proposal is a contract; if the inputs moved, it is void."""
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, _ = proposal["input_ids"]

    mrepo.update(
        conn,
        keep_id,
        title=None,
        content="REVISED BY HAND: run pytest -q and ruff check before pushing.",
        summary=None,
        change_reason="clarified by hand",
    )
    with pytest.raises(ValueError, match="edited since this proposal"):
        review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    assert "REVISED BY HAND" in mrepo.get(conn, keep_id).content
    # And the proposal is still pending, so a fresh analysis can replace it.
    assert pending_proposals(conn, project.id)


def test_editing_the_absorbed_record_also_invalidates_the_proposal(conn, tmp_path):
    project, proposal = _with_proposal(conn, tmp_path)
    _, absorb_id = proposal["input_ids"]
    mrepo.update(
        conn,
        absorb_id,
        title=None,
        content="Different instruction now.",
        summary=None,
        change_reason="edited",
    )
    with pytest.raises(ValueError, match="edited since this proposal"):
        review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])


def test_an_untouched_proposal_still_approves(conn, tmp_path):
    """The staleness guard must not block the normal path."""
    project, proposal = _with_proposal(conn, tmp_path)
    result = review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    assert result is not None
    assert result.citations_after > result.citations_before


@pytest.mark.parametrize("state", ["archived", "superseded"])
def test_merging_into_a_dead_record_is_refused(conn, tmp_path, state):
    """Merging into a record nobody will see is not a merge: the merged wording
    would land somewhere hidden from every listing."""
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, _ = proposal["input_ids"]
    if state == "archived":
        mrepo.archive(conn, keep_id)
    else:
        conn.execute("UPDATE memories SET status='superseded' WHERE id=?", (keep_id,))
    with pytest.raises(ValueError, match=f"is {state}"):
        review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])


def test_merging_an_already_absorbed_record_is_refused(conn, tmp_path):
    """Guards against a chain forming by accident."""
    project, proposal = _with_proposal(conn, tmp_path)
    keep_id, absorb_id = proposal["input_ids"]
    review.approve_proposal(conn, project_id=project.id, proposal_id=proposal["id"])
    with pytest.raises(ValueError, match="already superseded"):
        mrepo.supersede_into(
            conn,
            absorb_id=absorb_id,
            keep_id=keep_id,
            merged_content="again",
            reason="chain",
        )


def test_impact_handles_a_range_wider_than_the_variable_limit(conn, tmp_path):
    """A wide commit range builds a long IN-list. SQLite's limit here is
    250,000 parameters, not the 999 that is often assumed, so 1,200 files are
    fine -- but the behaviour is pinned rather than assumed."""
    git = _git_repo(tmp_path)
    (tmp_path / "README.md").write_text("# A\n\n## Notes\n\nLong enough to index here.\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    for index in range(1100):
        (tmp_path / f"f{index}.md").write_text(
            f"# F{index}\n\n## S{index}\n\nBody text for file {index}, long enough.\n"
        )
    git("add", "-A")
    git("commit", "-q", "-m", "bulk add")

    project = prepo.create(conn, Project(name="w", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=5000
    )
    report = impact.analyse(
        conn, project_id=project.id, root=tmp_path, base="HEAD~1", head="HEAD"
    )
    assert report.resolved
    assert len(report.changed_files) >= 1100
    assert report.affected
