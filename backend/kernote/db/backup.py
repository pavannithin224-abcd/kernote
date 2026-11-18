"""Backup, restore and portable export of the vault.

The vault is one SQLite file, so a correct backup is cheap -- but only if it
is taken the right way. Copying the file with `shutil` while the process is
running can capture a torn page or miss committed data still sitting in the
write-ahead log. `sqlite3.Connection.backup()` is the online backup API: it
takes a consistent snapshot of a live database, WAL included, without
stopping writers.

**Restore is the dangerous direction**, and this module treats it that way:

* the incoming file is **validated as a Kernote database** before anything is
  touched -- a stray file would otherwise destroy the vault and leave
  nothing;
* a database from a **newer schema** is refused rather than downgraded,
  because this code does not know what its rows mean;
* the current vault is **always snapshotted first**, so a restore someone
  regrets is itself reversible;
* the copy happens **into the live connection** rather than by swapping files
  on disk. That is atomic from the application's point of view, keeps every
  open connection valid, and avoids the Windows problem where an open file
  cannot be replaced.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# Tables a file must have before we will believe it is a Kernote vault.
REQUIRED_TABLES = ("schema_meta", "projects", "memories", "memory_source_refs")


def stamp() -> str:
    """A filename-safe timestamp, so backups sort chronologically."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def backup_dir(data_dir: Path) -> Path:
    path = data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Snapshot:
    path: Path
    bytes: int
    schema_version: int
    taken_at: str


def snapshot(conn: sqlite3.Connection, dest: Path) -> Snapshot:
    """Write a consistent copy of the live vault to `dest`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(dest)
    try:
        # The online backup API, not a file copy: safe while writers are
        # active and it folds in anything still in the WAL.
        conn.backup(target)
        version = int(
            target.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()[0]
        )
    finally:
        target.close()

    taken = Snapshot(
        path=dest,
        bytes=dest.stat().st_size,
        schema_version=version,
        taken_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    log.info("backup.taken", path=str(dest), bytes=taken.bytes, schema_version=version)
    return taken


@dataclass
class Candidate:
    """What a file claims to be, before we act on it."""

    path: Path
    schema_version: int
    projects: int
    memories: int


def inspect(path: Path, current_version: int) -> Candidate:
    """Confirm a file is a restorable Kernote vault, or raise saying why.

    Every refusal here is a refusal to destroy the current vault on the
    strength of a guess.
    """
    if not path.is_file():
        raise ValueError(f"{path} is not a file")

    try:
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"{path} could not be opened as a database: {exc}") from None

    try:
        try:
            names = {
                row[0]
                for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        except sqlite3.DatabaseError:
            raise ValueError(f"{path} is not an SQLite database") from None

        missing = [t for t in REQUIRED_TABLES if t not in names]
        if missing:
            raise ValueError(
                f"{path} does not look like a Kernote vault (missing {', '.join(missing)})"
            )

        row = src.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        if row is None:
            raise ValueError(f"{path} has no schema version recorded")
        version = int(row[0])

        if version > current_version:
            raise ValueError(
                f"{path} was written by a newer Kernote (schema v{version}; this "
                f"build understands v{current_version}). Upgrade before restoring: "
                "restoring it here would misread rows this code does not know about."
            )

        projects = int(src.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
        memories = int(src.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
    finally:
        src.close()

    return Candidate(path=path, schema_version=version, projects=projects, memories=memories)


@dataclass
class RestoreResult:
    restored_from: str
    safety_backup: str
    schema_version: int
    projects: int
    memories: int


def restore(
    conn: sqlite3.Connection, source: Path, *, data_dir: Path, current_version: int
) -> RestoreResult:
    """Replace the live vault's contents with `source`.

    Validates first, snapshots the current vault second, and only then
    copies. The safety snapshot is returned so the caller can tell the user
    where the previous vault went -- an undo nobody has to ask for.
    """
    candidate = inspect(source, current_version)

    safety = snapshot(conn, backup_dir(data_dir) / f"pre-restore-{stamp()}.db")

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        # Into the live connection: every open handle stays valid and there
        # is no file to swap underneath a running process.
        src.backup(conn)
    finally:
        src.close()

    log.info(
        "backup.restored",
        source=str(source),
        safety_backup=str(safety.path),
        schema_version=candidate.schema_version,
    )
    return RestoreResult(
        restored_from=str(source),
        safety_backup=str(safety.path),
        schema_version=candidate.schema_version,
        projects=candidate.projects,
        memories=candidate.memories,
    )


@dataclass
class Export:
    """A portable, readable copy. Not a restore format.

    The snapshot above is what you restore from; this is what you read, diff,
    or move to something that is not Kernote. It carries the memories and
    their provenance, deliberately not the derived indexes -- those are
    rebuildable by definition and would triple the size for nothing.
    """

    project: dict
    memories: list[dict] = field(default_factory=list)
    exported_at: str = ""


def export_project(conn: sqlite3.Connection, project_id: str) -> Export:
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")

    memories = []
    for row in conn.execute(
        "SELECT * FROM memories WHERE project_id=? ORDER BY created_at", (project_id,)
    ):
        record = dict(row)
        record["source_refs"] = [
            dict(ref)
            for ref in conn.execute(
                "SELECT rel_path,line_start,line_end,content_hash,git_blob_hash,"
                "git_commit,url,user_note FROM memory_source_refs WHERE memory_id=?",
                (record["id"],),
            )
        ]
        record["revisions"] = [
            dict(rev)
            for rev in conn.execute(
                "SELECT id,parent_id,change_reason,actor,created_at "
                "FROM memory_revisions WHERE memory_id=? ORDER BY created_at",
                (record["id"],),
            )
        ]
        memories.append(record)

    return Export(
        project=dict(project),
        memories=memories,
        exported_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def export_json(conn: sqlite3.Connection, project_id: str) -> str:
    data = export_project(conn, project_id)
    return json.dumps(
        {
            "kernote_export": 1,
            "exported_at": data.exported_at,
            "project": data.project,
            "memories": data.memories,
        },
        indent=1,
    )
