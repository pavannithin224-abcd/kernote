"""Maintenance endpoints: run the detectors, read the review queue.

Detection is explicit, not automatic on scan. Running analysis is cheap but it
writes findings, and `CLAUDE.md` wants writes to be deliberate; it also keeps a
scan fast and a scan's meaning narrow ("what is in the repository") separate
from analysis ("what looks wrong").
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...db.repositories import projects as project_repo
from ...db.repositories.findings import open_findings
from ...ingest import gitmeta
from ...maintain import impact, review
from ...maintain.conflicts import detect_conflicts
from ...maintain.drift import detect_drift
from ...maintain.duplicates import detect_duplicates, pending_proposals
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


@router.get("/projects/{project_id}/findings")
def list_findings(project_id: str, kind: str | None = Query(default=None)) -> list[dict]:
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
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
def list_proposals(project_id: str) -> list[dict]:
    """Consolidation proposals awaiting approval, each with a before/after."""
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    return pending_proposals(conn, project_id)
