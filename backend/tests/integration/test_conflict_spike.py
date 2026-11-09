"""Stage 4 conflict feasibility gate (proposal P5).

The riskiest unproven assumption in the plan: can contradictions be detected
deterministically, with no LLM, well enough for F8 to be a `Must` (ADR-0015)?

The contract being proved: one finding, holding BOTH claims with their sources,
and no winner chosen.
"""

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import (
    ClaimKind,
    Memory,
    MemoryType,
    Project,
    SourceRef,
)
from kernote.ingest.pipeline import scan_project
from kernote.maintain.conflicts import detect_conflicts
from kernote.maintain.findings import open_findings

READ_ME = """# Widgetly

## Testing

Run the suite before pushing:

```bash
pytest -q
```
"""

CONTRIBUTING = """# Contributing

## Testing

Always run the full matrix:

```bash
tox -e py312
```
"""


def _decision(
    project_id: str,
    title: str,
    chosen: str,
    alternatives: list[str],
    *,
    valid_from=None,
    valid_until=None,
    note="doc",
) -> Memory:
    return Memory(
        project_id=project_id,
        type=MemoryType.DECISION,
        title=title,
        content=f"We chose {chosen}.",
        claim_kind=ClaimKind.SOURCE_FACT,
        importance=0.6,
        importance_reason="decisions are durable",
        confidence=0.6,
        confidence_reason="stated in a document",
        extraction_method="manual",
        valid_from=valid_from,
        valid_until=valid_until,
        decision={"chosen": chosen, "alternatives": alternatives, "status": "accepted"},
        source_refs=[
            SourceRef(
                rel_path=f"docs/{note}.md", line_start=1, line_end=4, content_hash="h" + note
            )
        ],
    )


@pytest.fixture
def project(conn):
    return prepo.create(conn, Project(name="c", root_path="/tmp/kernote-conflict"))


# ------------------------------------- signal 1: same task, different commands


def test_two_docs_disagreeing_about_the_test_command_conflict(conn, tmp_path):
    (tmp_path / "README.md").write_text(READ_ME, encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text(CONTRIBUTING, encoding="utf-8")
    p = prepo.create(conn, Project(name="d", root_path=str(tmp_path)))
    scan_project(conn, project_id=p.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500)

    result = detect_conflicts(conn, project_id=p.id)
    assert result.procedure_conflicts >= 1, "two different test commands were not flagged"

    found = open_findings(conn, p.id, kind="conflict")
    assert len(found) == 1, f"expected one finding, got {len(found)}"
    f = found[0]

    # BOTH claims present, neither discarded.
    assert f["memory_id"] and f["other_id"] and f["memory_id"] != f["other_id"]
    claims = f["evidence"]["claims"]
    assert len(claims) == 2
    cites = {c["citation"].split(":")[0] for c in claims}
    assert cites == {"README.md", "CONTRIBUTING.md"}
    commands = {cmd for c in claims for cmd in c["commands"]}
    assert "pytest -q" in commands and "tox -e py312" in commands
    assert "Both claims are kept until you resolve this" in f["explanation"]


def test_agreeing_docs_do_not_conflict(conn, tmp_path):
    """The false-positive guard: identical commands in two files is duplication,
    not contradiction."""
    (tmp_path / "README.md").write_text(READ_ME, encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text(
        READ_ME.replace("# Widgetly", "# Contributing"), encoding="utf-8"
    )
    p = prepo.create(conn, Project(name="d", root_path=str(tmp_path)))
    scan_project(conn, project_id=p.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500)
    result = detect_conflicts(conn, project_id=p.id)
    assert result.procedure_conflicts == 0
    assert open_findings(conn, p.id, kind="conflict") == []


def test_single_source_is_never_a_conflict_with_itself(conn, tmp_path):
    (tmp_path / "README.md").write_text(READ_ME, encoding="utf-8")
    p = prepo.create(conn, Project(name="d", root_path=str(tmp_path)))
    scan_project(conn, project_id=p.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500)
    assert detect_conflicts(conn, project_id=p.id).procedure_conflicts == 0


# --------------------------- signal 2: same question, different answer in time


def test_overlapping_decisions_on_the_same_question_conflict(conn, project):
    """Each one's answer is the other's rejected alternative, and both are valid
    at once. That is a contradiction, not an evolution."""
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Database choice",
            "SQLite",
            ["Postgres"],
            valid_from="2026-01-01",
            note="a",
        ),
    )
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Storage decision",
            "Postgres",
            ["SQLite"],
            valid_from="2026-02-01",
            note="b",
        ),
    )

    result = detect_conflicts(conn, project_id=project.id)
    assert result.decision_conflicts == 1

    f = open_findings(conn, project.id, kind="conflict")[0]
    chosen = {c["chosen"] for c in f["evidence"]["claims"]}
    assert chosen == {"SQLite", "Postgres"}
    assert "both valid at the same time" in f["explanation"]


def test_decisions_separated_in_time_do_not_conflict(conn, project):
    """An evolution is not a contradiction: the first closed before the second
    opened. This is only decidable because validity is now a real field
    (ADR-0017)."""
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Database choice",
            "SQLite",
            ["Postgres"],
            valid_from="2026-01-01",
            valid_until="2026-01-31",
            note="a",
        ),
    )
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Storage decision",
            "Postgres",
            ["SQLite"],
            valid_from="2026-02-01",
            note="b",
        ),
    )
    assert detect_conflicts(conn, project_id=project.id).decision_conflicts == 0


def test_unrelated_decisions_do_not_conflict(conn, project):
    """Different questions, different answers: no overlap in alternatives, so
    no conflict. Guards against flagging every pair of decisions."""
    mrepo.create(
        conn, _decision(project.id, "Database choice", "Postgres", ["SQLite"], note="a")
    )
    mrepo.create(
        conn, _decision(project.id, "CI provider", "GitHub Actions", ["CircleCI"], note="b")
    )
    assert detect_conflicts(conn, project_id=project.id).decision_conflicts == 0


def test_same_answer_is_agreement_not_conflict(conn, project):
    mrepo.create(
        conn, _decision(project.id, "Database choice", "Postgres", ["SQLite"], note="a")
    )
    mrepo.create(
        conn, _decision(project.id, "Storage decision", "Postgres", ["SQLite"], note="b")
    )
    assert detect_conflicts(conn, project_id=project.id).decision_conflicts == 0


# ------------------------------------------------------------------ contract


def test_conflict_detection_never_picks_a_winner(conn, project):
    """ADR-0007: both records stay active and untouched. Kernote flags, the
    human resolves."""
    a = mrepo.create(
        conn,
        _decision(
            project.id,
            "Database choice",
            "SQLite",
            ["Postgres"],
            valid_from="2026-01-01",
            note="a",
        ),
    )
    b = mrepo.create(
        conn,
        _decision(
            project.id,
            "Storage decision",
            "Postgres",
            ["SQLite"],
            valid_from="2026-02-01",
            note="b",
        ),
    )
    detect_conflicts(conn, project_id=project.id)

    for mid in (a.id, b.id):
        m = mrepo.get(conn, mid)
        assert m is not None, "a conflicting record was deleted"
        assert m.status.value == "active", "detection silently changed a status"
        assert m.superseded_by is None, "detection silently superseded a claim"


def test_conflict_detection_is_idempotent(conn, project):
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Database choice",
            "SQLite",
            ["Postgres"],
            valid_from="2026-01-01",
            note="a",
        ),
    )
    mrepo.create(
        conn,
        _decision(
            project.id,
            "Storage decision",
            "Postgres",
            ["SQLite"],
            valid_from="2026-02-01",
            note="b",
        ),
    )
    detect_conflicts(conn, project_id=project.id)
    first = len(open_findings(conn, project.id))
    detect_conflicts(conn, project_id=project.id)
    assert len(open_findings(conn, project.id)) == first


def test_superseded_claims_are_excluded_from_conflict_detection(conn, project):
    """Once one claim has replaced the other there is nothing to resolve."""
    a = mrepo.create(
        conn,
        _decision(
            project.id,
            "Database choice",
            "SQLite",
            ["Postgres"],
            valid_from="2026-01-01",
            note="a",
        ),
    )
    replacement = _decision(
        project.id,
        "Storage decision",
        "Postgres",
        ["SQLite"],
        valid_from="2026-02-01",
        note="b",
    )
    mrepo.supersede(conn, a.id, replacement, reason="write contention")
    assert detect_conflicts(conn, project_id=project.id).decision_conflicts == 0
