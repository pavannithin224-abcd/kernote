from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import settings
from ...db.repositories import projects as repo
from ...db.repositories import sources as source_repo
from ...domain.models import Project, ScanResult
from ...ingest import gitmeta, scanconfig
from ...ingest.pipeline import scan_project
from ..deps import db
from ..schemas import ProjectDetail, RegisterProject

router = APIRouter(prefix="/api/v1", tags=["projects"])


@router.get("/projects", response_model=list[Project])
def list_projects() -> list[Project]:
    return repo.list_all(db())


@router.post("/projects", response_model=Project, status_code=201)
def register_project(body: RegisterProject) -> Project:
    root = Path(body.root_path).expanduser()
    if not root.is_dir():
        raise HTTPException(400, f"not a directory: {body.root_path}")
    root = root.resolve()
    conn = db()
    existing = repo.get_by_path(conn, str(root))
    if existing:
        raise HTTPException(409, f"already registered as project {existing.id}")
    project = Project(name=body.name, root_path=str(root), is_git_repo=gitmeta.is_repo(root))
    return repo.create(conn, project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> ProjectDetail:
    conn = db()
    project = repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return ProjectDetail(project=project, counts=repo.counts(conn, project_id))


@router.post("/projects/{project_id}/scan", response_model=ScanResult)
def scan(project_id: str) -> ScanResult:
    conn = db()
    project = repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    root = Path(project.root_path)
    if not root.is_dir():
        raise HTTPException(409, f"project root no longer exists: {project.root_path}")
    return scan_project(
        conn,
        project_id=project_id,
        root=root,
        max_file_bytes=settings.max_file_bytes,
        max_files=settings.max_files_per_scan,
    )


@router.get("/scans/{run_id}/skipped")
def scan_skipped(run_id: str) -> dict:
    """Why each file was not imported. Transparency is a product requirement."""
    items = source_repo.skipped_for_run(db(), run_id)
    by_reason: dict[str, list[str]] = {}
    for item in items:
        by_reason.setdefault(item.reason.value, []).append(item.rel_path)
    return {"total": len(items), "by_reason": by_reason}


# ─── scan configuration (CLAUDE.md: a configurable include/exclude list) ───


class ScanConfigUpdate(BaseModel):
    include: list[str] = Field(default_factory=list, max_length=500)
    exclude: list[str] = Field(default_factory=list, max_length=500)


def _config_payload(project_id: str, root: Path) -> dict:
    conn = db()
    try:
        effective = scanconfig.effective(conn, project_id, root)
    except scanconfig.ScanConfigError as exc:
        # Surfaced, not swallowed: a config the user believes is in force but
        # which failed to parse is worse than an error.
        raise HTTPException(422, str(exc)) from exc
    override = scanconfig.load_override(conn, project_id)
    return {
        "effective": effective.to_dict(),
        "override": {"include": list(override.include), "exclude": list(override.exclude)},
        "config_filename": scanconfig.CONFIG_FILENAME,
        "ignore_filename": scanconfig.IGNORE_FILENAME,
        "rules": [
            "Exclude always wins over include.",
            "Include widens only the allowlist -- which kinds of file are read.",
            "Include cannot override a secret refusal, .gitignore, the size "
            "limit or the binary check.",
            ".gitignore is always respected and cannot be disabled.",
        ],
    }


@router.get("/projects/{project_id}/scan-config")
def get_scan_config(project_id: str) -> dict:
    """The patterns a scan will actually use, and where each came from."""
    project = repo.get(db(), project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return _config_payload(project_id, Path(project.root_path))


@router.put("/projects/{project_id}/scan-config")
def put_scan_config(project_id: str, body: ScanConfigUpdate) -> dict:
    """Set this machine's local adjustment.

    Kernote never writes `.kernote.toml` into the user's repository: that file
    is the project's own declared intent, and `CLAUDE.md` forbids rewriting a
    user's files. This override is the local layer, like `.git/info/exclude`.
    """
    project = repo.get(db(), project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    try:
        scanconfig.save_override(db(), project_id, include=body.include, exclude=body.exclude)
    except scanconfig.ScanConfigError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _config_payload(project_id, Path(project.root_path))
