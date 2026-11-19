from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ... import jobs
from ...config import settings
from ...db import backup as backup_db
from ...db.repositories import graph as graph_repo
from ...db.repositories import projects as repo
from ...db.repositories import sources as source_repo
from ...domain.models import Project, ScanResult, new_id
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


class RemoveProject(BaseModel):
    # Removing a project deletes its memories, history and findings from the
    # vault. Same rule as restore: say so in the request, or nothing happens.
    confirm: bool = Field(
        default=False, description="Must be true: this deletes the project's memory."
    )


@router.delete("/projects/{project_id}")
def remove_project(project_id: str, body: RemoveProject | None = None) -> dict:
    """Remove a project from Kernote. Your folder is not touched.

    A snapshot is taken first and its path returned, so the removal can be
    undone by restoring it. Refused while a scan or analysis is running,
    because deleting rows out from under a job would make it fail halfway.
    """
    if not (body and body.confirm):
        raise HTTPException(400, "removing a project deletes its memory; send confirm=true")
    conn = db()
    if repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    for kind in ("scan", "analyze"):
        if jobs.runner.active_for(project_id, kind) is not None:
            raise HTTPException(
                409, f"a {kind} is running for this project; wait for it to finish"
            )
    safety = (
        backup_db.backup_dir(settings.data_dir)
        / f"kernote-before-remove-{backup_db.stamp()}.db"
    )
    backup_db.snapshot(conn, safety)
    removed = repo.remove(conn, project_id)
    return {"removed": project_id, "counts": removed, "safety_backup": str(safety)}


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> ProjectDetail:
    conn = db()
    project = repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return ProjectDetail(
        project=project,
        counts=repo.counts(conn, project_id),
        freshness=repo.freshness(conn, project_id),
    )


@router.get("/projects/{project_id}/graph")
def memory_graph(project_id: str) -> dict:
    """Nodes and edges that already exist in the database.

    Nothing is inferred and nothing is generated. Every edge is a row --
    an explicit link, a finding naming two memories, or a shared entity --
    and carries the reason it exists. `limits` reports what was left out, so
    a truncated graph can say so instead of looking complete.
    """
    conn = db()
    if repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    g = graph_repo.build(conn, project_id)
    return {"nodes": g.nodes, "edges": g.edges, "totals": g.totals, "limits": g.limits}


@router.post("/projects/{project_id}/scan/background")
def scan_in_background(project_id: str) -> dict:
    """Queue a scan instead of blocking on it.

    The synchronous `POST /scan` is unchanged — scripts and tests rely on
    it, and for a small repository it is the simpler thing. This is for the
    UI, where a scan that freezes the window for a minute is the difference
    between an application and a web page.
    """
    conn = db()
    project = repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    root = Path(project.root_path)
    if not root.is_dir():
        raise HTTPException(409, f"project root no longer exists: {project.root_path}")

    # Queueing a second scan of the same project does not make it finish
    # sooner; it makes the same work happen twice against a single-writer
    # database.
    existing = jobs.runner.active_for(project_id, "scan")
    if existing is not None:
        return existing.as_dict()

    def work() -> dict:
        # Exactly the call the blocking endpoint makes, including loading the
        # scan configuration itself. Reaching for `scanconfig.effective` here
        # would be a second, differently-wrong copy of that logic.
        result = scan_project(
            conn,
            project_id=project_id,
            root=root,
            max_file_bytes=settings.max_file_bytes,
            max_files=settings.max_files_per_scan,
        )
        return {
            "files_seen": result.files_seen,
            "memories_created": result.memories_created,
            "captures_created": result.captures_created,
        }

    return jobs.runner.submit(new_id(), "scan", project_id, work).as_dict()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.runner.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.as_dict()


@router.get("/jobs")
def list_jobs(project_id: str | None = None) -> list[dict]:
    """Recent background work, newest first.

    In-memory, so this is what *this process* has run. The durable record of
    what the work produced is in `scan_runs`, the findings table and
    `drift_runs`.
    """
    return [job.as_dict() for job in jobs.runner.list(project_id)]


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
