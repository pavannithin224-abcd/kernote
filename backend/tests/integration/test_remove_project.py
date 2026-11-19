"""Removing a project: complete, safe, and reversible by design."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "eval-repo"


@pytest.fixture
def scanned(client, tmp_path):
    root = tmp_path / "proj"
    shutil.copytree(SAMPLES, root)
    project = client.post("/api/v1/projects", json={"name": "p", "root_path": str(root)}).json()
    assert client.post(f"/api/v1/projects/{project['id']}/scan").status_code == 200
    client.post(f"/api/v1/projects/{project['id']}/analyze")
    return project, root


def _rows(client, sql, *params):
    from kernote.api.deps import db

    return db().execute(sql, params).fetchone()[0]


def test_removal_requires_confirmation(client, scanned):
    project, _ = scanned
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 400
    assert (
        client.request(
            "DELETE", f"/api/v1/projects/{project['id']}", json={"confirm": False}
        ).status_code
        == 400
    )
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 200


def test_removal_leaves_nothing_behind(client, scanned):
    project, _ = scanned
    pid = project["id"]
    # Give the project an embedding row too: that table has no foreign key.
    from kernote.api.deps import db

    mem = (
        db().execute("SELECT id FROM memories WHERE project_id=? LIMIT 1", (pid,)).fetchone()[0]
    )
    db().execute(
        "INSERT INTO embeddings(target_kind,target_id,model_id,dim,vector,built_at) "
        "VALUES('memory',?,?,?,?,?)",
        (mem, "m", 1, b"\x00\x00\x00\x00", "2026-01-01T00:00:00+00:00"),
    )
    before = _rows(client, "SELECT COUNT(*) FROM memories")
    assert before > 0

    r = client.request("DELETE", f"/api/v1/projects/{pid}", json={"confirm": True})
    assert r.status_code == 200, r.text
    assert r.json()["counts"]["memories"] == before

    counts = {
        "memories": "SELECT COUNT(*) FROM memories",
        "source_files": "SELECT COUNT(*) FROM source_files",
        "chunks": "SELECT COUNT(*) FROM chunks",
        "findings": "SELECT COUNT(*) FROM findings",
        "memory_revisions": "SELECT COUNT(*) FROM memory_revisions",
        "memory_source_refs": "SELECT COUNT(*) FROM memory_source_refs",
        "scan_runs": "SELECT COUNT(*) FROM scan_runs",
        "embeddings": "SELECT COUNT(*) FROM embeddings",
        "projects": "SELECT COUNT(*) FROM projects",
    }
    for table, sql in counts.items():
        assert _rows(client, sql) == 0, table
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404


def test_the_users_folder_is_never_touched(client, scanned):
    project, root = scanned
    snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    client.request("DELETE", f"/api/v1/projects/{project['id']}", json={"confirm": True})
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == snapshot


def test_a_safety_backup_is_taken_and_holds_the_data(client, scanned):
    import sqlite3

    project, _ = scanned
    r = client.request(
        "DELETE", f"/api/v1/projects/{project['id']}", json={"confirm": True}
    ).json()
    backup = Path(r["safety_backup"])
    assert backup.is_file()
    con = sqlite3.connect(backup)
    try:
        assert (
            con.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            == r["counts"]["memories"]
        )
    finally:
        con.close()


def test_other_projects_are_untouched(client, scanned, tmp_path):
    project, _ = scanned
    other_root = tmp_path / "other"
    other_root.mkdir()
    (other_root / "README.md").write_text(
        "# Other\n\nSome documented fact about the other project.\n", encoding="utf-8"
    )
    other = client.post(
        "/api/v1/projects", json={"name": "o", "root_path": str(other_root)}
    ).json()
    client.post(f"/api/v1/projects/{other['id']}/scan")
    kept = _rows(client, "SELECT COUNT(*) FROM memories WHERE project_id=?", other["id"])
    assert kept > 0

    client.request("DELETE", f"/api/v1/projects/{project['id']}", json={"confirm": True})
    assert (
        _rows(client, "SELECT COUNT(*) FROM memories WHERE project_id=?", other["id"]) == kept
    )


def test_unknown_project_is_404(client):
    r = client.request("DELETE", "/api/v1/projects/nope", json={"confirm": True})
    assert r.status_code == 404
