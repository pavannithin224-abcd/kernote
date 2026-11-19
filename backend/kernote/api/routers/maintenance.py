"""Maintenance endpoints: run the detectors, read the review queue.

Detection is explicit, not automatic on scan. Running analysis is cheap but it
writes findings, and the project contract wants writes to be deliberate; it also keeps a
scan fast and a scan's meaning narrow ("what is in the repository") separate
from analysis ("what looks wrong").
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ... import jobs
from ...db.repositories import projects as project_repo
from ...db.repositories.findings import open_findings, resolved_findings
from ...domain.models import new_id
from ...ingest import gitmeta
from ...maintain import impact, links, review, suggestions
from ...maintain.conflicts import detect_conflicts
from ...maintain.drift import detect_drift
from ...maintain.duplicates import detect_duplicates, proposals_by_status
from ...maintain.importance import refine
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["maintenance"])


class AnalysisResult(BaseModel):
    drift_high: int
    drift_medium: int
    drift_low: int
    refs_checked: int
    conflicts_procedure: int
    conflicts_decision: int
    duplicate_candidates: int
    proposals_created: int
    importance_adjusted: int
    open_findings: int


@router.post("/projects/{project_id}/analyze", response_model=AnalysisResult)
def analyze(project_id: str) -> AnalysisResult:
    """Run every detector. Findings are requests for review, never verdicts."""
    conn = db()
    project = project_repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    root = Path(project.root_path)
    if not root.is_dir():
        raise HTTPException(409, f"project root no longer exists: {project.root_path}")

    drift = detect_drift(conn, project_id=project_id, root=root)
    conflicts = detect_conflicts(conn, project_id=project_id)
    duplicates = detect_duplicates(conn, project_id=project_id)
    importance = refine(conn, project_id=project_id)

    return AnalysisResult(
        drift_high=drift.findings_high,
        drift_medium=drift.findings_medium,
        drift_low=drift.findings_low,
        refs_checked=drift.checked,
        conflicts_procedure=conflicts.procedure_conflicts,
        conflicts_decision=conflicts.decision_conflicts,
        duplicate_candidates=duplicates.candidates,
        proposals_created=duplicates.proposals,
        importance_adjusted=importance.adjusted,
        open_findings=len(open_findings(conn, project_id)),
    )


@router.post("/projects/{project_id}/analyze/background")
def analyze_in_background(project_id: str) -> dict:
    """Queue every detector instead of blocking on them.

    On a 587-memory vault this re-checks every pinned ref, so it is the
    other operation that should never hold a request open.
    """
    conn = db()
    project = project_repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    root = Path(project.root_path)
    if not root.is_dir():
        raise HTTPException(409, f"project root no longer exists: {project.root_path}")

    existing = jobs.runner.active_for(project_id, "analyze")
    if existing is not None:
        return existing.as_dict()

    def work() -> dict:
        drift = detect_drift(conn, project_id=project_id, root=root)
        conflicts = detect_conflicts(conn, project_id=project_id)
        duplicates = detect_duplicates(conn, project_id=project_id)
        importance = refine(conn, project_id=project_id)
        return {
            "drift_high": drift.findings_high,
            "refs_checked": drift.checked,
            "conflicts": conflicts.procedure_conflicts + conflicts.decision_conflicts,
            "duplicate_candidates": duplicates.candidates,
            "importance_adjusted": importance.adjusted,
            "open_findings": len(open_findings(conn, project_id)),
        }

    return jobs.runner.submit(new_id(), "analyze", project_id, work).as_dict()


@router.get("/projects/{project_id}/findings")
def list_findings(
    project_id: str,
    kind: str | None = Query(default=None),
    status: str = Query(default="open"),
) -> list[dict]:
    """Findings awaiting review by default.

    `status=resolved` lists recently closed ones, newest first — what the
    review screen reads to offer an undo.
    """
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    if status == "resolved":
        return resolved_findings(conn, project_id, kind)
    if status != "open":
        raise HTTPException(422, f"unknown finding status: {status}")
    return open_findings(conn, project_id, kind)


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ResolveFinding(Decision):
    verdict: str = Field(pattern="^(accepted|rejected|resolved)$")
    # Stamp last_verified_at when a finding is dismissed, so the same unchanged
    # source does not raise it again.
    reverify: bool = True


def _project_or_404(project_id: str):
    conn = db()
    project = project_repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return conn, project


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: str, body: Decision, project_id: str = Query(...)) -> dict:
    """Apply a consolidation. One transaction; nothing is deleted.

    The absorbed record keeps its content, gains `superseded_by` and stays
    fetchable by id. Every citation from both records is carried onto the
    keeper, and the merge is rolled back if any promised citation would be
    lost.
    """
    conn, _ = _project_or_404(project_id)
    try:
        result = review.approve_proposal(
            conn, project_id=project_id, proposal_id=proposal_id, note=body.note
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if result is None:
        raise HTTPException(404, "proposal not found")
    return asdict(result)


@router.post("/proposals/{proposal_id}/undo")
def undo(proposal_id: str, body: Decision, project_id: str = Query(...)) -> dict:
    """Reverse an approved consolidation.

    Restores the keeper's previous wording and citations and brings the
    absorbed record back. The merge stays in the revision history and the
    original `accepted` feedback is kept -- an undo is recorded as having
    happened, never erased. Refuses if either record has moved on since.
    """
    conn, _ = _project_or_404(project_id)
    try:
        result = review.undo_approval(
            conn, project_id=project_id, proposal_id=proposal_id, note=body.note
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if result is None:
        raise HTTPException(404, "proposal not found")
    return asdict(result)


@router.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: str, body: Decision, project_id: str = Query(...)) -> dict:
    """Decline a consolidation. Both memories are left exactly as they were."""
    conn, _ = _project_or_404(project_id)
    try:
        ok = review.reject_proposal(
            conn, project_id=project_id, proposal_id=proposal_id, note=body.note
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if not ok:
        raise HTTPException(404, "proposal not found")
    return {"rejected": True, "note": "both memories left unchanged"}


@router.post("/findings/{finding_id}/resolve")
def resolve(finding_id: str, body: ResolveFinding, project_id: str = Query(...)) -> dict:
    """Close a finding with a recorded decision (ADR-0007)."""
    conn, _ = _project_or_404(project_id)
    try:
        result = review.resolve_finding(
            conn,
            project_id=project_id,
            finding_id=finding_id,
            verdict=body.verdict,
            note=body.note,
            reverify=body.reverify,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if result is None:
        raise HTTPException(404, "finding not found")
    return result


@router.post("/findings/{finding_id}/undo")
def undo_finding(finding_id: str, body: Decision, project_id: str = Query(...)) -> dict:
    """Reopen a resolved finding, putting back what resolving it changed.

    Only the memories the resolution actually flipped are re-flagged, read
    from the effect it recorded. The decision stays in the feedback log with
    an `undone` row beside it.
    """
    conn, _ = _project_or_404(project_id)
    try:
        result = review.undo_resolution(
            conn, project_id=project_id, finding_id=finding_id, note=body.note
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if result is None:
        raise HTTPException(404, "finding not found")
    return asdict(result)


class LinkDecision(BaseModel):
    other_id: str
    kind: str = Field(default="relates_to")
    note: str | None = Field(default=None, max_length=500)


@router.post("/memories/{memory_id}/links")
def confirm_link(memory_id: str, body: LinkDecision, project_id: str = Query(...)) -> dict:
    """Agree that two memories are related.

    Turns a suggestion the graph derived from shared entities into a durable
    row with `origin='user'` — distinguishable from the links a merge leaves
    behind, because one is a judgement and the other a consequence.
    """
    conn, _ = _project_or_404(project_id)
    try:
        result = links.confirm(
            conn,
            project_id=project_id,
            src_id=memory_id,
            dst_id=body.other_id,
            kind=body.kind,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return asdict(result)


@router.post("/memories/{memory_id}/links/dismiss")
def dismiss_link(memory_id: str, body: LinkDecision, project_id: str = Query(...)) -> dict:
    """Say a suggested relationship is wrong, so it stops being suggested."""
    conn, _ = _project_or_404(project_id)
    try:
        low, high = links.dismiss(
            conn,
            project_id=project_id,
            src_id=memory_id,
            dst_id=body.other_id,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"dismissed": [low, high]}


@router.delete("/memories/{memory_id}/links")
def remove_link(
    memory_id: str, other_id: str = Query(...), project_id: str = Query(...)
) -> dict:
    """Withdraw a confirmed link. The memories themselves are untouched."""
    conn, _ = _project_or_404(project_id)
    try:
        removed = links.remove(conn, project_id=project_id, src_id=memory_id, dst_id=other_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if not removed:
        raise HTTPException(404, "no such link")
    return {"removed": True}


@router.get("/projects/{project_id}/links/suggestions")
def link_suggestions(project_id: str, limit: int = Query(default=50, le=200)) -> list[dict]:
    """Unanswered relationship suggestions, strongest first.

    Ranked by the summed specificity of everything a pair shares, so
    repeated rare overlap outranks a single vague one. Pairs already linked,
    already dismissed, or already in the review queue as a duplicate or
    conflict are left out — a triage list that keeps showing settled
    questions is one nobody finishes.
    """
    conn, _ = _project_or_404(project_id)
    return [s.as_dict() for s in suggestions.ranked(conn, project_id, limit)]


class BatchDecision(BaseModel):
    src_id: str
    dst_id: str
    verdict: str = Field(pattern="^(confirm|dismiss)$")
    kind: str | None = None


class BatchRequest(BaseModel):
    decisions: list[BatchDecision] = Field(max_length=200)


@router.post("/projects/{project_id}/links/batch")
def batch_links(project_id: str, body: BatchRequest) -> dict:
    """Answer several suggestions at once.

    Every decision still goes through the same guards as the single-pair
    endpoints — this is a convenience for a human answering many questions,
    not a side door around the rules. A decision that cannot be applied is
    reported rather than discarding the rest of the batch.
    """
    conn, _ = _project_or_404(project_id)
    result = suggestions.apply_batch(
        conn,
        project_id=project_id,
        decisions=[d.model_dump() for d in body.decisions],
    )
    return result.as_dict()


@router.get("/projects/{project_id}/impact")
def change_impact(
    project_id: str,
    base: str = Query(default="HEAD~1"),
    head: str = Query(default="HEAD"),
) -> dict:
    """Which memories a commit range may have invalidated."""
    conn, project = _project_or_404(project_id)
    report = impact.analyse(
        conn, project_id=project_id, root=Path(project.root_path), base=base, head=head
    )
    payload = asdict(report)
    payload["direct"] = report.direct
    return payload


@router.get("/projects/{project_id}/commits")
def commits(project_id: str, limit: int = Query(default=20, le=100)) -> list[dict]:
    """Recent commits, for choosing a range."""
    _conn, project = _project_or_404(project_id)
    return gitmeta.recent_commits(Path(project.root_path), limit)


@router.get("/projects/{project_id}/proposals")
def list_proposals(project_id: str, status: str = Query(default="pending")) -> list[dict]:
    """Consolidation proposals, each with a before/after.

    Defaults to those awaiting approval. `status=approved` lists ones already
    applied, newest first — which is what the undo flow reads, since a merge
    that leaves no trace in the UI cannot be taken back.
    """
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    if status not in ("pending", "approved", "rejected"):
        raise HTTPException(422, f"unknown proposal status: {status}")
    return proposals_by_status(conn, project_id, status)
