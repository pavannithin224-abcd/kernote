"""Stage 3 drift feasibility gate (proposal P4).

Proves the mechanism before Stage 6 depends on it: a changed file produces a
finding, and the hunk/line-range overlap test distinguishes "the cited lines
changed" from "the file changed somewhere else". The second half is what keeps
a freshness feature trustworthy (risk R10).
"""

import pathlib

import pytest

from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project
from kernote.maintain.drift import Hunk, detect_drift, parse_hunks
from kernote.maintain.findings import open_findings

README = """# Widgetly

A service that renders widgets.

## Architecture

Three components exist: api, render and store.

## Testing

Run the suite before pushing:

```bash
pytest -q
```

## Notes

Nothing else to say.
"""


@pytest.fixture
def scanned(conn, tmp_path):
    (tmp_path / "README.md").write_text(README)
    project = prepo.create(conn, Project(name="d", root_path=str(tmp_path)))
    scan_project(
        conn,
        project_id=project.id,
        root=tmp_path,
        max_file_bytes=1_000_000,
        max_files=500,
    )
    return project, tmp_path


# ------------------------------------------------------------ hunk mechanics


def test_hunk_overlap_is_inclusive_at_both_edges():
    h = Hunk(5, 7)
    assert h.overlaps(7, 9) and h.overlaps(3, 5)
    assert not h.overlaps(8, 10)
    assert not h.overlaps(1, 4)


def test_parse_hunks_reports_new_file_line_numbers():
    old = "a\nb\nc\nd\n"
    assert parse_hunks(old, "a\nb\nX\nd\n", "f.md") == [Hunk(3, 3)]


def test_deletions_remain_visible_to_the_overlap_test():
    """A pure deletion has target_length 0; if that collapsed to nothing, a
    removed setup step would never raise a finding."""
    hunks = parse_hunks("a\nb\nc\nd\n", "a\nb\nd\n", "f.md")
    assert hunks, "deletion produced no hunk"
    assert any(h.overlaps(2, 3) for h in hunks)


def test_identical_text_produces_no_hunks():
    assert parse_hunks("a\nb\n", "a\nb\n", "f.md") == []


# -------------------------------------------------------- end-to-end drift


def test_unchanged_repository_produces_no_findings(scanned, conn):
    project, root = scanned
    result = detect_drift(conn, project_id=project.id, root=root)
    assert result.checked > 0, "no source refs were checked"
    assert result.findings_high == 0 and result.findings_low == 0
    assert open_findings(conn, project.id) == []


def test_edit_inside_cited_lines_is_high_severity(scanned, conn):
    project, root = scanned
    path = root / "README.md"
    path.write_text(README.replace("Three components", "Four components"))

    detect_drift(conn, project_id=project.id, root=root)
    stale = open_findings(conn, project.id, kind="stale_risk")
    assert stale, "a changed file produced no finding at all"

    high = [f for f in stale if f["severity"] == "high"]
    assert high, "no high-severity finding for an edit inside cited lines"

    # The finding must name the overlapping region, not merely say "changed".
    ev = high[0]["evidence"]
    assert ev["overlapping_hunks"], "high severity with no overlapping hunk recorded"
    assert ev["pinned_hash"] != ev["current_hash"]
    assert ev["cited_lines"][0] <= ev["overlapping_hunks"][0][0] <= ev["cited_lines"][1]
    assert "inside the lines this memory cites" in high[0]["explanation"]


def test_edit_outside_cited_lines_is_low_severity(scanned, conn):
    """The anti-false-positive half: a memory whose own lines did not move must
    not be flagged as high just because the file changed."""
    project, root = scanned
    path = root / "README.md"
    path.write_text(README.replace("Three components", "Four components"))
    detect_drift(conn, project_id=project.id, root=root)

    stale = open_findings(conn, project.id, kind="stale_risk")
    low = [f for f in stale if f["severity"] == "low"]
    assert low, "every memory in the file was flagged high; the overlap test is not working"
    for f in low:
        assert f["evidence"]["overlapping_hunks"] == []
        assert "not within the cited lines" in f["explanation"]


def test_drift_is_idempotent(scanned, conn):
    """Re-running the detector must not pile up duplicates, or the review queue
    becomes unusable after a few scans."""
    project, root = scanned
    (root / "README.md").write_text(README.replace("Three components", "Four components"))
    detect_drift(conn, project_id=project.id, root=root)
    first = len(open_findings(conn, project.id))
    detect_drift(conn, project_id=project.id, root=root)
    assert len(open_findings(conn, project.id)) == first


def test_deleted_file_is_a_broken_link_not_a_crash(scanned, conn):
    project, root = scanned
    (root / "README.md").unlink()
    detect_drift(conn, project_id=project.id, root=root)
    broken = open_findings(conn, project.id, kind="broken_link")
    assert broken
    assert "missing or unreadable" in broken[0]["explanation"]


def test_drift_works_without_git(conn, tmp_path):
    """content_hash-first provenance (ADR-0005) means drift must work in a
    plain directory that is not a repository at all."""
    (tmp_path / "README.md").write_text(README)
    project = prepo.create(conn, Project(name="nogit", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500
    )
    assert not pathlib.Path(tmp_path / ".git").exists()
    (tmp_path / "README.md").write_text(README.replace("Three components", "Nine components"))
    result = detect_drift(conn, project_id=project.id, root=tmp_path)
    assert result.findings_high >= 1
