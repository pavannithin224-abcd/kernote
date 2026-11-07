"""Project registration and lookup."""

from __future__ import annotations

import sqlite3

from ...domain.models import Project


def create(conn: sqlite3.Connection, project: Project) -> Project:
    conn.execute(
        "INSERT INTO projects(id,name,root_path,is_git_repo,created_at,settings_json) "
        "VALUES(?,?,?,?,?,'{}')",
        (
            project.id,
            project.name,
            project.root_path,
            int(project.is_git_repo),
            project.created_at,
        ),
    )
    return project


def get(conn: sqlite3.Connection, project_id: str) -> Project | None:
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return _row(row) if row else None


def get_by_path(conn: sqlite3.Connection, root_path: str) -> Project | None:
    row = conn.execute("SELECT * FROM projects WHERE root_path=?", (root_path,)).fetchone()
    return _row(row) if row else None


def list_all(conn: sqlite3.Connection) -> list[Project]:
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [_row(r) for r in rows]


def counts(conn: sqlite3.Connection, project_id: str) -> dict[str, int]:
    def one(sql: str) -> int:
        return int(conn.execute(sql, (project_id,)).fetchone()[0])

    return {
        "memories": one(
            "SELECT COUNT(*) FROM memories WHERE project_id=? AND status!='archived'"
        ),
        "source_files": one(
            "SELECT COUNT(*) FROM source_files WHERE project_id=? AND is_current=1"
        ),
        "captures": one("SELECT COUNT(*) FROM source_captures WHERE project_id=?"),
        "scans": one("SELECT COUNT(*) FROM scan_runs WHERE project_id=?"),
        "open_findings": one(
            "SELECT COUNT(*) FROM findings WHERE project_id=? AND status='open'"
        ),
    }


def _row(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        root_path=row["root_path"],
        is_git_repo=bool(row["is_git_repo"]),
        created_at=row["created_at"],
    )
