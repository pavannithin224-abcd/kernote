"""Write-integrity regression tests.

Each test here corresponds to a bug that was reproduced before it was fixed.
They exist so the fix cannot silently regress.
"""

import sqlite3
import threading

import pytest

from kernote.db.connection import transaction
from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.db.repositories import sources as srepo
from kernote.domain.models import (
    ClaimKind,
    Memory,
    MemoryStatus,
    MemoryType,
    Project,
    SourceRef,
    new_id,
    parse_temporal,
)


def _memory(project_id: str, **over) -> Memory:
    base = {
        "project_id": project_id,
        "type": MemoryType.DECISION,
        "title": "T",
        "content": "C",
        "claim_kind": ClaimKind.SOURCE_FACT,
        "importance": 0.5,
        "importance_reason": "because",
        "confidence": 0.5,
        "confidence_reason": "because",
        "extraction_method": "manual",
        "source_refs": [SourceRef(user_note="n")],
    }
    base.update(over)
    return Memory(**base)


@pytest.fixture
def project(conn):
    return prepo.create(conn, Project(name="p", root_path="/tmp/kernote-test-project"))


# ---------------------------------------------------------------- atomicity


def test_failed_revision_write_rolls_back_the_memory(conn, project, monkeypatch):
    """Bug: create() committed the memory row before writing its revision, so a
    failure left an orphan with no lineage and no provenance."""
    mem = _memory(project.id)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("simulated disk I/O error")

    monkeypatch.setattr(mrepo, "_write_revision", boom)
    with pytest.raises(sqlite3.OperationalError):
        mrepo.create(conn, mem)

    assert (
        conn.execute("SELECT COUNT(*) FROM memories WHERE id=?", (mem.id,)).fetchone()[0] == 0
    ), "orphaned memory survived a failed revision write"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM memory_revisions WHERE memory_id=?", (mem.id,)
        ).fetchone()[0]
        == 0
    )


def test_failed_source_ref_write_rolls_back_the_memory(conn, project, monkeypatch):
    """Same unit of work, failing at the third statement instead of the second."""
    mem = _memory(project.id)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(mrepo, "_write_ref", boom)
    with pytest.raises(sqlite3.OperationalError):
        mrepo.create(conn, mem)
    assert mrepo.get(conn, mem.id) is None


def test_transaction_is_reentrant(conn, project):
    """A repository write nested inside a larger unit of work must join it, not
    start a second transaction, and must roll back with the outer block."""
    created: list[str] = []
    with pytest.raises(RuntimeError), transaction(conn):
        for _ in range(3):
            m = mrepo.create(conn, _memory(project.id))  # opens a nested transaction
            created.append(m.id)
        raise RuntimeError("outer unit of work fails after inner writes")

    assert len(created) == 3
    for mid in created:
        assert mrepo.get(conn, mid) is None, "nested write survived outer rollback"


# ------------------------------------------------------------- uniqueness


def test_only_one_current_source_file_per_path(conn, project):
    """Bug: ix_source_files_current was a plain index, so two rows for one path
    could both be is_current=1. The database now refuses it."""
    run = srepo.start_scan(conn, project.id, None)
    srepo.upsert_capture(conn, project.id, "h1", "a", 1, "utf-8")
    srepo.upsert_capture(conn, project.id, "h2", "b", 1, "utf-8")
    srepo.record_file(
        conn,
        project_id=project.id,
        rel_path="R.md",
        content_hash="h1",
        language=None,
        run_id=run,
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO source_files(id,project_id,rel_path,content_hash,language,"
            "first_seen_run,last_seen_run,is_current) VALUES(?,?,?,?,?,?,?,1)",
            (new_id(), project.id, "R.md", "h2", None, run, run),
        )


def test_content_change_demotes_the_old_row_and_keeps_it(conn, project):
    run = srepo.start_scan(conn, project.id, None)
    for h in ("h1", "h2"):
        srepo.upsert_capture(conn, project.id, h, h, 1, "utf-8")
        srepo.record_file(
            conn,
            project_id=project.id,
            rel_path="R.md",
            content_hash=h,
            language=None,
            run_id=run,
        )
    rows = conn.execute(
        "SELECT content_hash,is_current FROM source_files WHERE rel_path='R.md'"
    ).fetchall()
    assert len(rows) == 2, "history was discarded instead of demoted"
    assert sum(r["is_current"] for r in rows) == 1
    assert next(r["content_hash"] for r in rows if r["is_current"]) == "h2"


# ------------------------------------------------------------ supersession


def test_supersede_retains_the_old_record(conn, project):
    old = mrepo.create(conn, _memory(project.id, title="Use SQLite", valid_from="2026-01-01"))
    replacement = _memory(project.id, title="Use Postgres", valid_from="2026-03-11")
    result = mrepo.supersede(conn, old.id, replacement, reason="write contention")
    assert result is not None
    stored_old, new = result

    assert stored_old.status is MemoryStatus.SUPERSEDED
    assert stored_old.superseded_by == new.id
    assert stored_old.valid_until, "supersession must close the validity window"
    assert not stored_old.is_current
    assert mrepo.get(conn, old.id) is not None, "invariant 5: must stay fetchable"
    assert mrepo.get(conn, new.id).supersedes == old.id, "inverse edge not derived"
    assert mrepo.get(conn, new.id).is_current


def test_supersede_writes_a_closing_revision(conn, project):
    old = mrepo.create(conn, _memory(project.id))
    before = len(mrepo.revisions(conn, old.id))
    mrepo.supersede(conn, old.id, _memory(project.id, title="New"), reason="r")
    assert len(mrepo.revisions(conn, old.id)) == before + 1


def test_supersede_records_a_typed_graph_edge(conn, project):
    old = mrepo.create(conn, _memory(project.id))
    _, new = mrepo.supersede(conn, old.id, _memory(project.id, title="N"), reason="why")
    row = conn.execute(
        "SELECT kind FROM memory_links WHERE src_id=? AND dst_id=?", (new.id, old.id)
    ).fetchone()
    assert row["kind"] == "supersedes"


def test_double_supersede_is_refused(conn, project):
    old = mrepo.create(conn, _memory(project.id))
    mrepo.supersede(conn, old.id, _memory(project.id, title="A"), reason="r")
    with pytest.raises(ValueError, match="already superseded"):
        mrepo.supersede(conn, old.id, _memory(project.id, title="B"), reason="r")


def test_supersede_across_projects_is_refused(conn, project):
    other = prepo.create(conn, Project(name="o", root_path="/tmp/kernote-other"))
    old = mrepo.create(conn, _memory(project.id))
    with pytest.raises(ValueError, match="same project"):
        mrepo.supersede(conn, old.id, _memory(other.id, title="X"), reason="r")


def test_supersede_missing_memory_returns_none(conn, project):
    assert mrepo.supersede(conn, "no-such-id", _memory(project.id), reason="r") is None


# ------------------------------------------------------- temporal validity


def test_expired_validity_window_is_not_current(conn, project):
    m = mrepo.create(
        conn, _memory(project.id, valid_from="2020-01-01", valid_until="2020-02-01")
    )
    assert not mrepo.get(conn, m.id).is_current


def test_validity_and_decision_payload_round_trip(conn, project):
    m = mrepo.create(
        conn,
        _memory(
            project.id,
            valid_from="2026-03-11",
            decision={"chosen": "Postgres", "alternatives": ["SQLite"], "status": "accepted"},
        ),
    )
    got = mrepo.get(conn, m.id)
    # Stored canonically, not as typed: the domain layer normalises every
    # accepted ISO spelling to one form so downstream comparisons are safe.
    assert got.valid_from == "2026-03-11T00:00:00+00:00"
    assert parse_temporal(got.valid_from) == parse_temporal("2026-03-11")
    assert got.decision["chosen"] == "Postgres"
    assert got.decision["alternatives"] == ["SQLite"]


# ------------------------------------------------------------- concurrency


def test_concurrent_writers_do_not_interleave(conn, project):
    """The write lock must keep one logical write indivisible under threads.

    Without it two threads can interleave inside create(), producing a memory
    whose revision belongs to the other thread's write.
    """
    errors: list[BaseException] = []
    ids: list[str] = []
    lock = threading.Lock()

    def writer(n: int) -> None:
        try:
            for i in range(8):
                m = mrepo.create(conn, _memory(project.id, title=f"t{n}-{i}"))
                with lock:
                    ids.append(m.id)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writes raised: {errors[:2]}"
    assert len(ids) == 32
    # Every memory must have exactly one revision and one source ref.
    for mid in ids:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM memory_revisions WHERE memory_id=?", (mid,)
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM memory_source_refs WHERE memory_id=?", (mid,)
            ).fetchone()[0]
            == 1
        )


# -------------------------------------------------------------------- API


def test_supersede_endpoint(client, demo_repo):
    r = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo})
    pid = r.json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    mid = client.get(f"/api/v1/projects/{pid}/memories").json()[0]["id"]

    res = client.post(
        f"/api/v1/memories/{mid}/supersede",
        json={
            "title": "Revised claim",
            "content": "The code moved.",
            "reason": "module was split in two",
            "valid_from": "2026-11-07",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["superseded"]["status"] == "superseded"
    assert body["superseded"]["superseded_by"] == body["replacement"]["id"]
    assert client.get(f"/api/v1/memories/{mid}").status_code == 200

    again = client.post(
        f"/api/v1/memories/{mid}/supersede", json={"title": "x", "content": "y", "reason": "z"}
    )
    assert again.status_code == 422, "double supersede should be rejected"


def test_create_memory_rejects_backwards_validity_window(client, demo_repo):
    r = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo})
    pid = r.json()["id"]
    bad = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={
            "type": "gotcha",
            "title": "t",
            "content": "c",
            "valid_from": "2026-05-01",
            "valid_until": "2026-01-01",
        },
    )
    assert bad.status_code == 422
    assert "valid_until" in bad.json()["detail"]
