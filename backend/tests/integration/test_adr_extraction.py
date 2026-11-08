"""ADR extraction (Stage 3, `rule:adr`).

This is what finally gives the decision-conflict detector real data: before
it, only hand-written memories carried a decision payload, so the signal
ADR-0015 made a `Must` could not fire on anything a scan produced.
"""

import pathlib

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.extract import adr
from kernote.ingest.normalize import split_markdown
from kernote.ingest.pipeline import scan_project
from kernote.maintain.conflicts import detect_conflicts
from kernote.maintain.findings import open_findings

ADR_TOOLS = """# 1. Use PostgreSQL for persistence

## Status

Accepted

Date: 2026-03-11

## Context

Several render workers write widget definitions concurrently.

## Decision

We will use PostgreSQL as the primary datastore.

## Considered Options

- *SQLite* — rejected for write contention under concurrent writers.
- *MySQL* — no team experience.

## Consequences

A database server must be operated.
"""

MADR = """# Use Tailwind for styling

## Status

proposed · 2026-04-02

## Decision Outcome

Chosen option: Tailwind CSS, because it avoids bespoke CSS per screen.

## Considered Options

* `Tailwind CSS`
* `CSS Modules`
"""


def _extract(path: str, doc: str):
    return adr.extract(
        project_id="p",
        rel_path=path,
        content_hash="h",
        text=doc,
        sections=split_markdown(doc),
    )


# ------------------------------------------------------- document shapes


def test_one_decision_per_file_is_one_memory():
    """`adr-tools` puts the decision in the document and `## Status` /
    `## Decision` in sub-sections. Treating each sub-section as its own ADR --
    the first implementation -- extracted nothing at all."""
    memories = _extract("docs/adr/0001-use-postgresql.md", ADR_TOOLS)
    assert len(memories) == 1
    m = memories[0]
    assert m.title == "Use PostgreSQL for persistence", "the ADR number should be stripped"
    assert m.decision["status"] == "accepted"
    assert m.decision["chosen"] == "PostgreSQL"
    assert "SQLite" in m.decision["alternatives"]
    assert m.decision["decided_on"] == "2026-03-11"
    # The decision date is when the claim became true (ADR-0017).
    assert m.valid_from.startswith("2026-03-11")
    assert m.source_refs[0].line_start == 1


def test_madr_chosen_option_form():
    m = _extract("docs/decisions/0002-styling.md", MADR)[0]
    assert m.decision["chosen"] == "Tailwind CSS"
    assert m.decision["status"] == "proposed"
    assert "CSS Modules" in m.decision["alternatives"]


def test_combined_log_yields_one_memory_per_section():
    """Kernote's own decision log is this shape, so it is a real fixture
    rather than a synthetic one."""
    doc = pathlib.Path(__file__).resolve().parents[3] / "docs" / "DECISIONS.md"
    memories = _extract("docs/DECISIONS.md", doc.read_text())
    assert len(memories) > 10, "the combined log should yield many decisions"
    assert all(m.type.value == "decision" for m in memories)
    assert all(m.extraction_method == "rule:adr" for m in memories)
    # Status and date parse reliably from our format.
    assert sum(1 for m in memories if (m.decision or {}).get("status")) > 10
    assert sum(1 for m in memories if m.valid_from) > 10


def test_option_names_are_bare_so_they_can_be_compared():
    """Option names are matched against each other by the conflict detector,
    so markdown emphasis and trailing justification must be stripped."""
    m = _extract("docs/adr/0001-use-postgresql.md", ADR_TOOLS)[0]
    for name in m.decision["alternatives"]:
        assert not name.startswith(("*", "`", "_"))
        assert " — " not in name and " rejected" not in name
    assert m.decision["chosen"] == "PostgreSQL", "trailing prose should be trimmed"


# ------------------------------------------------------------ discipline


def test_non_adr_documents_are_ignored():
    readme = "# Widgetly\n\n## Setup\n\nRun it with make dev, which is simple enough.\n"
    assert _extract("README.md", readme) == []


def test_missing_fields_are_omitted_not_invented():
    """ADR-0006: a guessed option would feed the conflict detector a fabricated
    claim, which is worse than a missing one."""
    sparse = """# 7. Something was decided

## Status

Accepted

## Context

We talked about it at some length and reached a conclusion.
"""
    m = _extract("docs/adr/0007-something.md", sparse)[0]
    assert m.decision["status"] == "accepted"
    assert "chosen" not in m.decision
    assert "alternatives" not in m.decision


def test_prose_style_adrs_yield_status_without_a_fabricated_choice():
    """Our own ADRs state the decision as a paragraph, which is not reliably
    parseable. The extractor must decline rather than guess."""
    prose = """# ADR-0001 - Two local processes

**Status:** accepted · 2026-11-06

**Context.** Packaging a desktop shell would cost days.

**Decision.** Ship a Vite frontend plus a FastAPI backend on localhost.
"""
    m = _extract("docs/DECISIONS.md", prose)[0]
    assert m.decision["status"] == "accepted"
    assert m.decision["decided_on"] == "2026-11-06"


# ------------------------------------------------- the point of all this


def test_two_adr_files_produce_a_decision_conflict(conn, tmp_path):
    """End to end: scan real ADR files, detect that they answer the same
    question differently while both are valid."""
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0004-use-postgresql.md").write_text(ADR_TOOLS)
    (tmp_path / "docs" / "adr" / "0001-use-sqlite.md").write_text(
        ADR_TOOLS.replace("1. Use PostgreSQL", "1. Use SQLite")
        .replace("# 1. Use SQLite for persistence", "# 1. Use SQLite for persistence")
        .replace(
            "We will use PostgreSQL as the primary datastore.",
            "We will use SQLite for operational simplicity.",
        )
        .replace(
            "- *SQLite* — rejected for write contention under concurrent writers.",
            "- *PostgreSQL* — heavier to operate for one process.",
        )
        .replace("Date: 2026-03-11", "Date: 2026-01-05")
    )
    project = prepo.create(conn, Project(name="adr", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500
    )

    decisions = [
        m for m in mrepo.list_for_project(conn, project.id) if m.type.value == "decision"
    ]
    assert len(decisions) == 2, [m.title for m in decisions]
    assert {(m.decision or {}).get("chosen") for m in decisions} == {"SQLite", "PostgreSQL"}

    result = detect_conflicts(conn, project_id=project.id)
    assert result.decision_conflicts == 1, "two opposing ADRs produced no conflict"

    finding = open_findings(conn, project.id, kind="conflict")[0]
    chosen = {c["chosen"] for c in finding["evidence"]["claims"]}
    assert chosen == {"SQLite", "PostgreSQL"}
    # Both claims kept, neither record touched (ADR-0007).
    for m in decisions:
        assert m.status.value == "active"
        assert m.superseded_by is None


def test_adr_document_does_not_also_produce_generic_section_memories(conn, tmp_path):
    """The ADR extractor owns its document. Running the generic section
    extractor as well produced a second payload-less "Decision" memory for
    every `## Decision` sub-heading."""
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0001-x.md").write_text(ADR_TOOLS)
    project = prepo.create(conn, Project(name="a", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500
    )
    titles = [m.title for m in mrepo.list_for_project(conn, project.id)]
    assert "Decision" not in titles, f"duplicate section memory present: {titles}"
    assert titles == ["Use PostgreSQL for persistence"]
