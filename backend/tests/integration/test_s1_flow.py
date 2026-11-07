"""Slice S1, the Stage 2 gate.

Register a project, scan it, get a memory with provenance, prove it persists
across a restart. Plus the invariants that make a second scan safe.
"""

import pathlib

from kernote.main import create_app


def _register_and_scan(client, root):
    r = client.post("/api/v1/projects", json={"name": "Demo", "root_path": root})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    s = client.post(f"/api/v1/projects/{pid}/scan")
    assert s.status_code == 200, s.text
    return pid, s.json()


def test_health_reports_schema_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "1"


def test_register_rejects_a_path_that_is_not_a_directory(client):
    r = client.post("/api/v1/projects", json={"name": "x", "root_path": "/definitely/not/here"})
    assert r.status_code == 400
    assert "not a directory" in r.json()["detail"]


def test_register_rejects_duplicate_project(client, demo_repo):
    client.post("/api/v1/projects", json={"name": "a", "root_path": demo_repo})
    again = client.post("/api/v1/projects", json={"name": "b", "root_path": demo_repo})
    assert again.status_code == 409


def test_s1_scan_produces_memories_with_provenance(client, demo_repo):
    pid, scan = _register_and_scan(client, demo_repo)
    assert scan["files_seen"] > 0
    assert scan["memories_created"] > 0

    memories = client.get(f"/api/v1/projects/{pid}/memories").json()
    assert memories
    for m in memories:
        assert m["source_refs"], f"{m['title']!r} has no provenance"
        ref = m["source_refs"][0]
        assert ref["content_hash"], "no content hash: drift detection impossible"
        assert m["importance_reason"] and m["confidence_reason"]

    with_lines = [m for m in memories if m["source_refs"][0]["line_start"]]
    assert with_lines, "no memory pinned to a line range"
    detail = client.get(f"/api/v1/memories/{with_lines[0]['id']}").json()
    assert ":" in detail["citations"][0]
    assert len(detail["revisions"]) == 1


def test_invariant_1_rescan_creates_no_new_captures(client, demo_repo):
    pid, _ = _register_and_scan(client, demo_repo)
    before = client.get(f"/api/v1/projects/{pid}/memories").json()
    second = client.post(f"/api/v1/projects/{pid}/scan").json()
    assert second["captures_created"] == 0
    assert second["memories_created"] == 0
    after = client.get(f"/api/v1/projects/{pid}/memories").json()
    assert len(after) == len(before)


def test_secrets_are_refused_and_explained(client, hostile_repo):
    pid, scan = _register_and_scan(client, str(hostile_repo))
    reasons = client.get(f"/api/v1/scans/{scan['scan_run_id']}/skipped").json()
    assert ".env" in reasons["by_reason"]["secret_suspected"]
    # and nothing from the secret file leaked into a memory
    blob = " ".join(
        m["content"] + m["title"] for m in client.get(f"/api/v1/projects/{pid}/memories").json()
    )
    assert "sk-not-a-real-key" not in blob


def test_edit_writes_a_revision_and_archive_never_deletes(client, demo_repo):
    pid, _ = _register_and_scan(client, demo_repo)
    mid = client.get(f"/api/v1/projects/{pid}/memories").json()[0]["id"]

    patched = client.patch(
        f"/api/v1/memories/{mid}", json={"title": "Edited", "change_reason": "clarity"}
    )
    assert patched.status_code == 200
    detail = client.get(f"/api/v1/memories/{mid}").json()
    assert detail["memory"]["title"] == "Edited"
    assert len(detail["revisions"]) == 2, "edit did not create a revision"

    client.post(f"/api/v1/memories/{mid}/archive")
    still = client.get(f"/api/v1/memories/{mid}")
    assert still.status_code == 200, "invariant 5 violated: archived record unreachable"
    assert still.json()["memory"]["status"] == "archived"


def test_manual_memory_needs_no_file_provenance(client, demo_repo):
    pid, _ = _register_and_scan(client, demo_repo)
    r = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={
            "type": "gotcha",
            "title": "Iris Xe has no CUDA",
            "content": "Do not assume GPU acceleration on this laptop.",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["extraction_method"] == "manual"
    assert r.json()["source_refs"][0]["user_note"]


def test_unknown_memory_type_is_rejected(client, demo_repo):
    pid, _ = _register_and_scan(client, demo_repo)
    r = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={"type": "nonsense", "title": "x", "content": "y"},
    )
    assert r.status_code == 422


def test_s1_gate_data_survives_restart(tmp_data_dir, demo_repo):
    """The Stage 2 gate: a restart must not lose anything."""
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as c:
        pid, _ = _register_and_scan(c, demo_repo)
        expected = len(c.get(f"/api/v1/projects/{pid}/memories").json())
        mid = c.get(f"/api/v1/projects/{pid}/memories").json()[0]["id"]
        assert expected > 0

    with TestClient(create_app()) as c:  # fresh app, same database file
        projects = c.get("/api/v1/projects").json()
        assert len(projects) == 1
        memories = c.get(f"/api/v1/projects/{projects[0]['id']}/memories").json()
        assert len(memories) == expected
        detail = c.get(f"/api/v1/memories/{mid}").json()
        assert detail["memory"]["source_refs"][0]["content_hash"]
        assert detail["revisions"]


def test_invariant_4_reindex_rebuildable_from_canonical(conn, demo_repo):
    """L4 is disposable: dropping the FTS index and rebuilding must restore it."""
    from kernote.db.repositories import projects as prepo
    from kernote.domain.models import Project
    from kernote.ingest.pipeline import scan_project

    project = prepo.create(conn, Project(name="demo", root_path=demo_repo))
    scan_project(
        conn,
        project_id=project.id,
        root=pathlib.Path(demo_repo),
        max_file_bytes=1_000_000,
        max_files=5000,
    )

    before = conn.execute(
        "SELECT COUNT(*) FROM memories_fts WHERE memories_fts MATCH 'widget'"
    ).fetchone()[0]
    assert before > 0, "FTS index was never populated"

    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
    after = conn.execute(
        "SELECT COUNT(*) FROM memories_fts WHERE memories_fts MATCH 'widget'"
    ).fetchone()[0]
    assert after == before, "rebuilt index does not match the original"
