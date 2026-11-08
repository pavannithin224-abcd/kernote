"""Maintenance endpoints: run the detectors, read the review queue.

Detection is explicit, not automatic on scan. Running analysis is cheap but it
writes findings, and `CLAUDE.md` wants writes to be deliberate; it also keeps a
scan fast and a scan's meaning narrow ("what is in the repository") separate
from analysis ("what looks wrong").
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...db.repositories import projects as project_repo
from ...db.repositories.findings import open_findings
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


@router.get("/projects/{project_id}/proposals")
def list_proposals(project_id: str) -> list[dict]:
    """Consolidation proposals awaiting approval, each with a before/after."""
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    return pending_proposals(conn, project_id)
