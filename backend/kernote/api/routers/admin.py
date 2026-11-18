"""Backup, restore and export — the vault's own safety net.

Restore is the only endpoint in Kernote that can destroy data, so it is the
only one that demands an explicit confirmation in the request body and takes
a snapshot of what it is about to replace.

Paths rather than uploads: the server is always on the same machine as the
user (local-first, bound to loopback), so streaming a multi-megabyte database
through HTTP would add a dependency and a copy for no benefit. A native file
dialog can fill the path in later.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ...config import settings
from ...db import backup as backup_db
from ...db.connection import current_version
from ...db.repositories import projects as project_repo
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["admin"])


class BackupRequest(BaseModel):
    # Where to write it. Defaults to a `backups/` folder beside the vault.
    path: str | None = None


class RestoreRequest(BaseModel):
    path: str
    # Restore replaces every memory in the vault. Nothing in Kernote else
    # does that, so nothing else asks for this.
    confirm: bool = Field(
        default=False, description="Must be true: restoring replaces the whole vault."
    )


@router.post("/backup")
def take_backup(body: BackupRequest | None = None) -> dict:
    """Snapshot the vault to a file. Safe while the app is running."""
    conn = db()
    requested = (body.path if body else None) or None
    dest = (
        Path(requested).expanduser()
        if requested
        else backup_db.backup_dir(settings.data_dir) / f"kernote-{backup_db.stamp()}.db"
    )
    try:
        snap = backup_db.snapshot(conn, dest)
    except OSError as exc:
        raise HTTPException(409, f"could not write the backup: {exc}") from None
    return {
        "path": str(snap.path),
        "bytes": snap.bytes,
        "schema_version": snap.schema_version,
        "taken_at": snap.taken_at,
    }


@router.get("/backup/download")
def download_backup() -> FileResponse:
    """A fresh snapshot, as a download, for getting a copy off the machine."""
    conn = db()
    dest = backup_db.backup_dir(settings.data_dir) / f"kernote-{backup_db.stamp()}.db"
    snap = backup_db.snapshot(conn, dest)
    return FileResponse(
        snap.path, media_type="application/vnd.sqlite3", filename=snap.path.name
    )


@router.post("/restore/inspect")
def inspect_backup(body: RestoreRequest) -> dict:
    """What a file claims to be, without touching anything.

    So a user can see what they are about to overwrite themselves with
    before they agree to it.
    """
    conn = db()
    try:
        candidate = backup_db.inspect(Path(body.path).expanduser(), current_version(conn))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {
        "path": str(candidate.path),
        "schema_version": candidate.schema_version,
        "projects": candidate.projects,
        "memories": candidate.memories,
    }


@router.post("/restore")
def restore_backup(body: RestoreRequest) -> dict:
    """Replace the vault. Refuses without `confirm`, and snapshots first."""
    if not body.confirm:
        raise HTTPException(
            400,
            "restoring replaces every memory in this vault; send confirm=true "
            "once you have seen /restore/inspect",
        )
    conn = db()
    try:
        result = backup_db.restore(
            conn,
            Path(body.path).expanduser(),
            data_dir=settings.data_dir,
            current_version=current_version(conn),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {
        "restored_from": result.restored_from,
        "safety_backup": result.safety_backup,
        "schema_version": result.schema_version,
        "projects": result.projects,
        "memories": result.memories,
    }


@router.get("/projects/{project_id}/export", response_class=PlainTextResponse)
def export_project(project_id: str) -> PlainTextResponse:
    """A readable JSON copy: memories with their provenance and lineage.

    Not a restore format -- a snapshot is. This is what you read, diff, or
    carry to something that is not Kernote. Derived indexes are left out
    because they are rebuildable by definition.
    """
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    body = backup_db.export_json(conn, project_id)
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="kernote-{project_id}.json"'},
    )
