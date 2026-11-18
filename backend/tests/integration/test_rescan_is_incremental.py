"""A re-scan updates the vault; it does not copy it.

The idempotency check has always keyed on the **file's** content hash, so a
file was either untouched (skip everything) or changed (re-create
everything). Editing one paragraph of a document therefore re-created every
memory extracted from it.

Measured on this repository before the fix: a second scan after a day of
documentation edits produced **345 new memories while only 24 new files
appeared**, taking the vault from 587 to 932, and left 91 duplicate
proposals for a human to clear. The duplicate detector was doing cleanup for
the ingest pipeline.

Three outcomes now, and only one of them is a new memory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project

CORPUS = Path(__file__).resolve().parents[3] / "samples" / "eval-repo"


@pytest.fixture
def repo(conn, tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(CORPUS, root)
    project = prepo.create(conn, Project(name="rescan", root_path=str(root)))
    return project, root


def _scan(conn, project, root):
    return scan_project(
        conn, project_id=project.id, root=root, max_file_bytes=1_000_000, max_files=200
    )


def _counts(conn, project_id):
    total = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE project_id=?", (project_id,)
    ).fetchone()[0]
    superseded = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE project_id=? AND status='superseded'",
        (project_id,),
    ).fetchone()[0]
    return total, superseded


def test_an_unchanged_repository_creates_nothing(repo, conn):
    project, root = repo
    first = _scan(conn, project, root)
    assert first.memories_created > 0

    again = _scan(conn, project, root)
    assert (again.memories_created, again.memories_superseded, again.memories_repinned) == (
        0,
        0,
        0,
    )
    assert _counts(conn, project.id)[0] == first.memories_created


def test_appending_a_section_adds_one_memory_not_a_copy_of_the_file(repo, conn):
    """The regression that produced 345 memories from 24 new files."""
    project, root = repo
    first = _scan(conn, project, root)
    before = _counts(conn, project.id)[0]

    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## Deployment\n\nDeploy with `make deploy` once the suite passes.\n",
        encoding="utf-8",
    )
    second = _scan(conn, project, root)

    assert (
        second.memories_created == 1
    ), f"appending one section created {second.memories_created} memories"
    assert second.memories_repinned > 0, "the sections that merely moved should be re-pinned"
    assert _counts(conn, project.id)[0] == before + 1
    assert first.memories_created > 1, "guard: the corpus must produce several memories"


def test_editing_a_section_supersedes_rather_than_duplicates(repo, conn):
    """The old reading is retired with lineage, not left beside the new one."""
    project, root = repo
    _scan(conn, project, root)

    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("pytest", "pytest -q", 1), encoding="utf-8"
    )
    result = _scan(conn, project, root)

    assert result.memories_superseded >= 1
    assert result.memories_created == 0, "an edited claim is not a new claim"
    total, superseded = _counts(conn, project.id)
    assert superseded == result.memories_superseded


def test_a_superseded_reading_keeps_its_content_and_points_at_its_replacement(repo, conn):
    """MEMORY_MODEL invariant 5: nothing is destroyed."""
    project, root = repo
    _scan(conn, project, root)
    readme = root / "README.md"
    original = readme.read_text(encoding="utf-8")
    readme.write_text(original.replace("pytest", "pytest -q", 1), encoding="utf-8")
    _scan(conn, project, root)

    row = conn.execute(
        "SELECT content, superseded_by FROM memories "
        "WHERE project_id=? AND status='superseded' LIMIT 1",
        (project.id,),
    ).fetchone()
    assert row is not None
    assert row["superseded_by"], "a superseded record must name its replacement"
    assert row["content"], "its wording is kept"
    replacement = conn.execute(
        "SELECT status FROM memories WHERE id=?", (row["superseded_by"],)
    ).fetchone()
    assert replacement["status"] == "active"


def test_repinning_moves_the_citation_without_writing_a_revision(repo, conn):
    """The claim did not change; only where it lives did.

    Writing a revision for every line-number shift would fill the history
    with entries that say nothing about the claim.
    """
    project, root = repo
    _scan(conn, project, root)
    revisions_before = conn.execute("SELECT COUNT(*) FROM memory_revisions").fetchone()[0]

    readme = root / "README.md"
    readme.write_text(
        "<!-- a comment that shifts every line below it -->\n"
        + readme.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = _scan(conn, project, root)
    assert result.memories_repinned > 0

    revisions_after = conn.execute("SELECT COUNT(*) FROM memory_revisions").fetchone()[0]
    assert revisions_after == revisions_before + result.memories_created * 1 + (
        result.memories_superseded * 2
    ), "re-pinning should not write revisions of its own"
