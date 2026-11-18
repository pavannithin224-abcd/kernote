"""Backup, restore and export.

Restore is the only operation in Kernote that destroys data. Most of these
tests are about what it *refuses* to do, because the failure mode is not a
wrong number on a screen -- it is somebody's vault replaced by a file that
turned out not to be a vault.
"""

from __future__ import annotations

import sqlite3

import pytest

from kernote.db import backup as backup_db
from kernote.db.connection import current_version
from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import ClaimKind, Memory, MemoryType, Project, SourceRef


def _memory(conn, project_id: str, title: str) -> Memory:
    return mrepo.create(
        conn,
        Memory(
            project_id=project_id,
            type=MemoryType.CONVENTION,
            title=title,
            content=f"Body of {title}.",
            claim_kind=ClaimKind.SOURCE_FACT,
            extraction_method="manual",
            importance=0.5,
            importance_reason="test",
            confidence=0.5,
            confidence_reason="test",
            source_refs=[SourceRef(user_note="test")],
        ),
        change_reason="test",
        actor="user",
    )


@pytest.fixture
def vault(conn, tmp_data_dir):
    project = prepo.create(conn, Project(name="v", root_path="/tmp/v"))
    for i in range(3):
        _memory(conn, project.id, f"Memory {i}")
    return project


def test_a_snapshot_is_a_usable_database(vault, conn, tmp_path):
    dest = tmp_path / "snap.db"
    snap = backup_db.snapshot(conn, dest)

    assert dest.is_file() and snap.bytes > 0
    copy = sqlite3.connect(dest)
    assert copy.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 3
    copy.close()


def test_a_snapshot_is_consistent_while_writes_continue(vault, conn, tmp_path):
    """The reason this uses the online backup API and not a file copy."""
    dest = tmp_path / "live.db"
    backup_db.snapshot(conn, dest)
    _memory(conn, vault.id, "Written after the snapshot")

    copy = sqlite3.connect(dest)
    titles = {r[0] for r in copy.execute("SELECT title FROM memories")}
    copy.close()
    assert "Written after the snapshot" not in titles, "the snapshot was not a point in time"
    assert len(titles) == 3


def test_restore_brings_back_what_was_there(vault, conn, tmp_path, tmp_data_dir):
    snap = backup_db.snapshot(conn, tmp_path / "before.db")
    _memory(conn, vault.id, "Added after the backup")
    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 4

    result = backup_db.restore(
        conn, snap.path, data_dir=tmp_data_dir, current_version=current_version(conn)
    )

    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 3
    titles = {r[0] for r in conn.execute("SELECT title FROM memories")}
    assert "Added after the backup" not in titles
    assert result.memories == 3


def test_restore_snapshots_what_it_is_about_to_destroy(vault, conn, tmp_path, tmp_data_dir):
    """An undo nobody has to ask for."""
    snap = backup_db.snapshot(conn, tmp_path / "old.db")
    _memory(conn, vault.id, "About to be lost")

    result = backup_db.restore(
        conn, snap.path, data_dir=tmp_data_dir, current_version=current_version(conn)
    )

    rescued = sqlite3.connect(result.safety_backup)
    titles = {r[0] for r in rescued.execute("SELECT title FROM memories")}
    rescued.close()
    assert (
        "About to be lost" in titles
    ), "the pre-restore snapshot did not capture the vault being replaced"


def test_the_live_connection_survives_a_restore(vault, conn, tmp_path, tmp_data_dir):
    """Copying into the connection, not swapping the file underneath it."""
    snap = backup_db.snapshot(conn, tmp_path / "s.db")
    backup_db.restore(
        conn, snap.path, data_dir=tmp_data_dir, current_version=current_version(conn)
    )
    # Same connection object, still usable, no reopen.
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


# ---------------------------------------------- what it refuses to do


def test_a_file_that_is_not_a_database_is_refused(conn, tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_text("this is not a vault", encoding="utf-8")
    with pytest.raises(ValueError, match="not"):
        backup_db.inspect(junk, current_version(conn))


def test_an_unrelated_sqlite_database_is_refused(conn, tmp_path):
    """The dangerous near-miss: a real database that is not ours."""
    other = tmp_path / "someone-elses.db"
    db = sqlite3.connect(other)
    db.execute("CREATE TABLE notes (id TEXT)")
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="does not look like a Kernote vault"):
        backup_db.inspect(other, current_version(conn))


def test_a_newer_schema_is_refused_rather_than_downgraded(vault, conn, tmp_path):
    snap = backup_db.snapshot(conn, tmp_path / "future.db")
    future = sqlite3.connect(snap.path)
    future.execute("UPDATE schema_meta SET value='999' WHERE key='schema_version'")
    future.commit()
    future.close()

    with pytest.raises(ValueError, match="newer Kernote"):
        backup_db.inspect(snap.path, current_version(conn))


def test_a_missing_file_is_refused(conn, tmp_path):
    with pytest.raises(ValueError, match="not a file"):
        backup_db.inspect(tmp_path / "nope.db", current_version(conn))


def test_a_refused_restore_leaves_the_vault_untouched(vault, conn, tmp_path, tmp_data_dir):
    """The whole point of validating before acting."""
    junk = tmp_path / "junk.db"
    junk.write_text("garbage", encoding="utf-8")

    with pytest.raises(ValueError):
        backup_db.restore(
            conn, junk, data_dir=tmp_data_dir, current_version=current_version(conn)
        )

    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 3


# ---------------------------------------------- export


def test_export_carries_provenance_and_lineage(vault, conn):
    import json

    data = json.loads(backup_db.export_json(conn, vault.id))
    assert data["kernote_export"] == 1
    assert len(data["memories"]) == 3
    first = data["memories"][0]
    assert "source_refs" in first and first["source_refs"]
    assert "revisions" in first and first["revisions"]


def test_export_refuses_an_unknown_project(conn):
    with pytest.raises(ValueError, match="not found"):
        backup_db.export_json(conn, "no-such-project")


# ---------------------------------------------- over HTTP


def test_restore_over_http_requires_confirmation(client, tmp_path):
    pid = client.post(
        "/api/v1/projects", json={"name": "h", "root_path": str(tmp_path)}
    ).json()["id"]
    assert pid

    taken = client.post("/api/v1/backup", json={}).json()
    assert taken["bytes"] > 0

    # Without confirm: refused, and nothing happens.
    refused = client.post("/api/v1/restore", json={"path": taken["path"]})
    assert refused.status_code == 400
    assert "confirm" in refused.text

    # Inspect first, as the message tells you to.
    seen = client.post("/api/v1/restore/inspect", json={"path": taken["path"]})
    assert seen.status_code == 200
    assert seen.json()["projects"] == 1

    done = client.post("/api/v1/restore", json={"path": taken["path"], "confirm": True})
    assert done.status_code == 200, done.text
    assert done.json()["safety_backup"]


def test_inspecting_junk_over_http_is_a_422_not_a_crash(client, tmp_path):
    junk = tmp_path / "x.db"
    junk.write_text("nope", encoding="utf-8")
    r = client.post("/api/v1/restore/inspect", json={"path": str(junk)})
    assert r.status_code == 422


def test_export_endpoint_returns_json_for_download(client, tmp_path):
    pid = client.post(
        "/api/v1/projects", json={"name": "e", "root_path": str(tmp_path)}
    ).json()["id"]
    r = client.get(f"/api/v1/projects/{pid}/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.json()["kernote_export"] == 1
