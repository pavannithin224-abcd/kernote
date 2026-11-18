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


# Mirrors detect_drift's own WHERE clause. A memory is *verifiable* only if it
# pins a real file region: rel_path and content_hash both present, and the
# memory still live. Anything else -- a hand-written assertion, an archived
# record -- has no file to drift from, so it cannot be fresh or stale and is
# excluded from both halves of the fraction rather than counted as fresh.
_VERIFIABLE = (
    "SELECT COUNT(DISTINCT r.memory_id) "
    "FROM memory_source_refs r JOIN memories m ON m.id = r.memory_id "
    "WHERE m.project_id = ? AND r.rel_path IS NOT NULL "
    "  AND r.content_hash IS NOT NULL "
    "  AND m.status IN ('active','needs_review')"
)

# Of those, the ones a check has actually objected to. broken_link counts: a
# citation whose file has vanished is not a fresh claim.
_FLAGGED = (
    "SELECT COUNT(DISTINCT r.memory_id) "
    "FROM memory_source_refs r JOIN memories m ON m.id = r.memory_id "
    "JOIN findings f ON f.memory_id = r.memory_id "
    "WHERE m.project_id = ? AND r.rel_path IS NOT NULL "
    "  AND r.content_hash IS NOT NULL "
    "  AND m.status IN ('active','needs_review') "
    "  AND f.status = 'open' AND f.kind IN ('stale_risk','broken_link')"
)


def freshness(conn: sqlite3.Connection, project_id: str) -> dict:
    """Three states, because two would require inventing the third.

    `checked_at` is None when no freshness check has ever run for this
    project. The UI must say "never checked" in that case -- *not* 0% and not
    100%. A project with no stale findings because nobody looked is not a
    fresh project, and `verified` is meaningless until `checked_at` is set.
    """
    row = conn.execute(
        "SELECT ran_at, refs_checked FROM drift_runs WHERE project_id=? "
        "ORDER BY ran_at DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    verifiable = int(conn.execute(_VERIFIABLE, (project_id,)).fetchone()[0])
    flagged = int(conn.execute(_FLAGGED, (project_id,)).fetchone()[0])
    return {
        "checked_at": row["ran_at"] if row else None,
        "refs_checked": int(row["refs_checked"]) if row else 0,
        "verifiable": verifiable,
        "flagged": flagged,
        "verified": max(0, verifiable - flagged),
    }


def _row(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        root_path=row["root_path"],
        is_git_repo=bool(row["is_git_repo"]),
        created_at=row["created_at"],
    )
