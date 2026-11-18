"""Freshness has three states, and the third one is the whole point.

The dashboard asked for a "freshness %". The naive form of that figure --
memories without an open stale finding, over all memories -- is wrong twice
over, and both errors flatter the product:

  1. A project nobody has analyzed has no stale findings, so it reads 100%
     fresh. That reports an absence of evidence as evidence of freshness.
  2. A hand-written memory with no source citation has no file to drift from.
     Counting it in the denominator as "fresh" claims verification that never
     happened and could not happen.

So `freshness()` reports `checked_at`, and excludes memories that pin nothing.
These tests exist to stop the convenient version coming back.
"""

from __future__ import annotations

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import ClaimKind, Memory, MemoryType, Project, SourceRef
from kernote.ingest.pipeline import scan_project
from kernote.maintain.drift import detect_drift

README = """# Widget

A service that renders widgets.

## Architecture

Three components exist: api, render and store.

## Testing

Run the suite before pushing:

```bash
pytest -q
```
"""


@pytest.fixture
def scanned(conn, tmp_path):
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    project = prepo.create(conn, Project(name="f", root_path=str(tmp_path)))
    scan_project(
        conn,
        project_id=project.id,
        root=tmp_path,
        max_file_bytes=1_000_000,
        max_files=500,
    )
    return project, tmp_path


def test_a_never_checked_project_reports_no_check_not_full_freshness(scanned, conn):
    """The failure this whole design exists to prevent."""
    project, _ = scanned
    f = prepo.freshness(conn, project.id)

    assert f["checked_at"] is None, "nothing has checked this project yet"
    assert f["flagged"] == 0
    # There is real material to verify -- so a caller that divided
    # verified/verifiable here would print 100% for an unchecked project.
    assert f["verifiable"] > 0
    assert f["verified"] == f["verifiable"]
    # The guard is checked_at, and only checked_at. If this assertion ever
    # needs relaxing, the UI contract is being broken, not the test.
    assert f["checked_at"] is None


def test_running_a_check_sets_checked_at(scanned, conn):
    project, root = scanned
    detect_drift(conn, project_id=project.id, root=root)

    f = prepo.freshness(conn, project.id)
    assert f["checked_at"] is not None
    assert f["refs_checked"] > 0
    assert f["flagged"] == 0, "an untouched tree has nothing stale"
    assert f["verified"] == f["verifiable"]


def test_an_edit_moves_a_memory_from_verified_to_flagged(scanned, conn):
    project, root = scanned
    detect_drift(conn, project_id=project.id, root=root)
    before = prepo.freshness(conn, project.id)

    (root / "README.md").write_text(
        README.replace("api, render and store", "api and store only"),
        encoding="utf-8",
    )
    detect_drift(conn, project_id=project.id, root=root)
    after = prepo.freshness(conn, project.id)

    assert after["flagged"] > before["flagged"]
    assert after["verified"] < before["verified"]
    # The denominator must not move: the same claims exist, one is now doubted.
    assert after["verifiable"] == before["verifiable"]
    assert after["verified"] + after["flagged"] == after["verifiable"]


def test_a_memory_citing_nothing_is_in_neither_half(scanned, conn):
    """An assertion with no source is not fresh and not stale. It is neither.

    Built the way `POST /memories` builds one: a single `SourceRef` carrying a
    `user_note` and no `rel_path`. The provenance is real -- a human said so --
    but there is no file region to re-hash, so it belongs in neither half.
    """
    project, root = scanned
    detect_drift(conn, project_id=project.id, root=root)
    before = prepo.freshness(conn, project.id)

    mrepo.create(
        conn,
        Memory(
            project_id=project.id,
            type=MemoryType.CONVENTION,
            title="We squash before merging",
            content="Stated by the maintainer in review; no file records it.",
            claim_kind=ClaimKind.SOURCE_FACT,
            extraction_method="manual",
            importance=0.4,
            importance_reason="manual capture",
            confidence=0.5,
            confidence_reason="asserted by a human, no file to check",
            source_refs=[SourceRef(user_note="asserted by user in the UI")],
        ),
        change_reason="created by user",
        actor="user",
    )

    after = prepo.freshness(conn, project.id)
    assert after["verifiable"] == before["verifiable"], (
        "a memory with no source ref must not enter the denominator -- "
        "counting it would claim a verification that cannot exist"
    )
    assert after["verified"] == before["verified"]


def test_the_fraction_never_exceeds_one(scanned, conn):
    project, root = scanned
    detect_drift(conn, project_id=project.id, root=root)
    f = prepo.freshness(conn, project.id)
    assert 0 <= f["verified"] <= f["verifiable"]
    assert 0 <= f["flagged"] <= f["verifiable"]


def test_health_reports_database_size_including_the_wal(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db_bytes"] > 0
