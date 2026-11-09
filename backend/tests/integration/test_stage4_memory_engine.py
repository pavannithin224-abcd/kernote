"""Stage 4: entities, duplicate candidates, consolidation previews, importance.

The Stage 4 gate: memory CRUD persists with lineage (covered in
test_write_integrity), evidence is visible, and duplicates are *proposed* with
a reviewable before/after rather than merged.
"""

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import ClaimKind, Memory, MemoryType, Project, SourceRef
from kernote.ingest import entities
from kernote.ingest.pipeline import scan_project
from kernote.maintain.duplicates import detect_duplicates, pending_proposals
from kernote.maintain.importance import refine


def _scan(conn, root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    project = prepo.create(conn, Project(name="s", root_path=str(root)))
    scan_project(
        conn, project_id=project.id, root=root, max_file_bytes=1_000_000, max_files=200
    )
    return project


def _memory(project_id: str, **over) -> Memory:
    base = {
        "project_id": project_id,
        "type": MemoryType.PROCEDURE,
        "title": "Setup: commands",
        "content": "pytest -q\nnpm run build",
        "claim_kind": ClaimKind.SOURCE_FACT,
        "importance": 0.5,
        "importance_reason": "base",
        "confidence": 0.5,
        "confidence_reason": "r",
        "extraction_method": "rule:markdown_commands",
        "source_refs": [
            SourceRef(rel_path="docs/a.md", line_start=1, line_end=3, content_hash="h")
        ],
    }
    base.update(over)
    return Memory(**base)


# ------------------------------------------------------------- entities


def test_entities_derived_from_paths_and_commands():
    pairs = entities.derive(_memory("p"))
    assert ("file", "docs/a.md") in pairs
    assert ("module", "docs") in pairs
    assert ("command", "pytest") in pairs
    assert ("command", "npm") in pairs


def test_fence_markers_are_not_commands():
    """Dogfooding produced entities literally called "```" and "```bash"."""
    memory = _memory("p", content="```bash\npytest -q\n```")
    names = {name for kind, name in entities.derive(memory) if kind == "command"}
    assert names == {"pytest"}
    assert not any("`" in n for n in names)


def test_commands_only_from_command_lists():
    """A section-derived procedure memory is prose; its lines are not commands."""
    prose = _memory(
        "p",
        extraction_method="rule:markdown_sections",
        content="Run the suite before pushing. It takes about a minute.",
    )
    assert not [k for k, _ in entities.derive(prose) if k == "command"]


def test_decision_options_become_entities():
    memory = _memory(
        "p",
        type=MemoryType.DECISION,
        title="Database choice",
        content="We chose Postgres.",
        extraction_method="rule:adr",
        decision={"chosen": "PostgreSQL", "alternatives": ["SQLite"]},
    )
    names = {name for kind, name in entities.derive(memory) if kind == "decision"}
    assert names == {"PostgreSQL", "SQLite"}


def test_entities_are_linked_during_a_scan(conn, tmp_path):
    project = _scan(
        conn,
        tmp_path,
        {"README.md": "# A\n\n## Setup\n\nInstall it:\n\n```bash\npytest -q\n```\n"},
    )
    linked = conn.execute(
        "SELECT COUNT(*) FROM memory_entities me JOIN entities e ON e.id=me.entity_id "
        "WHERE e.project_id=?",
        (project.id,),
    ).fetchone()[0]
    assert linked > 0, "entities table is still dormant after a scan"


# -------------------------------------------------- duplicate candidates


def test_identical_sections_in_two_files_are_proposed(conn, tmp_path):
    body = "Run the full suite with pytest before pushing any change to main.\n"
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": f"# App\n\n## Running the tests\n\n{body}",
            "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{body}",
        },
    )
    result = detect_duplicates(conn, project_id=project.id)
    assert result.candidates >= 1
    assert result.proposals >= 1


def test_same_title_different_content_is_not_a_duplicate(conn, tmp_path):
    """A matching title alone is not evidence: two functions named `create`
    share a title and nothing else."""
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": "# App\n\n## Configuration\n\n"
            "Set DATABASE_URL to point at your local Postgres instance.\n",
            "DEPLOY.md": "# Deploy\n\n## Configuration\n\n"
            "Production runs three replicas behind a load balancer.\n",
        },
    )
    assert detect_duplicates(conn, project_id=project.id).candidates == 0


def test_a_section_does_not_duplicate_its_own_code_block(conn, tmp_path):
    """Dogfooding flagged every "Setup" section against its own
    "Setup: commands" child -- parent and child, not two claims."""
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": "# App\n\n## Setup\n\nInstall the dependencies first:\n\n"
            "```bash\npip install -r requirements.txt\n```\n"
        },
    )
    assert detect_duplicates(conn, project_id=project.id).candidates == 0


def test_code_symbols_are_excluded_from_duplicate_detection(conn, tmp_path):
    """Two same-named functions in different modules produced 8 false
    candidates out of 8. Symbol memories are unique by construction."""
    project = _scan(
        conn,
        tmp_path,
        {
            "a/one.py": "def create(x):\n    '''Make a thing.'''\n    return x\n",
            "a/two.py": "def create(y):\n    '''Make a thing.'''\n    return y\n",
        },
    )
    assert detect_duplicates(conn, project_id=project.id).candidates == 0


# ---------------------------------------------- the proposal is reviewable


def test_proposal_preview_keeps_every_citation(conn, tmp_path):
    body = "Run the full suite with pytest before pushing any change to main.\n"
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": f"# App\n\n## Running the tests\n\n{body}",
            "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{body}",
        },
    )
    detect_duplicates(conn, project_id=project.id)
    proposals = pending_proposals(conn, project.id)
    assert proposals

    preview = proposals[0]["preview"]
    assert len(preview["before"]) == 2
    roles = {side["role"] for side in preview["before"]}
    assert roles == {"keep", "absorb"}

    # The guarantee that makes approval safe: no citation is lost.
    before_citations = {c for side in preview["before"] for c in side["citations"]}
    assert before_citations <= set(preview["after"]["citations"])
    assert before_citations, "no citations in the preview at all"
    assert preview["guarantees"]


def test_detection_merges_nothing(conn, tmp_path):
    """ADR-0007: proposing is not applying. Both records stay active."""
    body = "Run the full suite with pytest before pushing any change to main.\n"
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": f"# App\n\n## Running the tests\n\n{body}",
            "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{body}",
        },
    )
    before = mrepo.list_for_project(conn, project.id, limit=500)
    detect_duplicates(conn, project_id=project.id)
    after = mrepo.list_for_project(conn, project.id, limit=500)
    assert len(before) == len(after)
    assert all(m.status.value == "active" for m in after)
    assert all(m.superseded_by is None for m in after)


def test_duplicate_detection_is_idempotent(conn, tmp_path):
    body = "Run the full suite with pytest before pushing any change to main.\n"
    project = _scan(
        conn,
        tmp_path,
        {
            "README.md": f"# App\n\n## Running the tests\n\n{body}",
            "CONTRIBUTING.md": f"# Contributing\n\n## Running the tests\n\n{body}",
        },
    )
    detect_duplicates(conn, project_id=project.id)
    first = len(pending_proposals(conn, project.id))
    detect_duplicates(conn, project_id=project.id)
    assert len(pending_proposals(conn, project.id)) == first


# -------------------------------------------------------------- importance


def test_shared_command_raises_importance_and_explains_itself(conn):
    project = prepo.create(conn, Project(name="p", root_path="/tmp/kernote-imp"))
    for index in range(3):
        mrepo.create(
            conn,
            _memory(
                project.id,
                title=f"Task {index}: commands",
                content="pytest -q",
                source_refs=[
                    SourceRef(
                        rel_path=f"docs/{index}.md",
                        line_start=1,
                        line_end=2,
                        content_hash=f"h{index}",
                    )
                ],
            ),
        )
    for memory in mrepo.list_for_project(conn, project.id, limit=50):
        entities.link(conn, project.id, memory)

    before = {m.id: m.importance for m in mrepo.list_for_project(conn, project.id)}
    result = refine(conn, project_id=project.id)
    assert result.adjusted > 0
    after = mrepo.list_for_project(conn, project.id, limit=50)
    assert any(m.importance > before[m.id] for m in after)
    bumped = next(m for m in after if m.importance > before[m.id])
    assert "fan-in:" in bumped.importance_reason
    assert "pytest" in bumped.importance_reason, "the reason must name the signal"


def test_incidental_sharing_does_not_change_ranking(conn, tmp_path):
    """Every memory in docs/ shares the `docs` module. Weighting that adjusted
    271 of 271 memories, which ranks nothing."""
    project = _scan(
        conn,
        tmp_path,
        {
            "docs/a.md": "# A\n\n## Architecture\n\nThe first component does one thing.\n",
            "docs/b.md": "# B\n\n## Overview\n\nThe second component does another thing.\n",
            "docs/c.md": "# C\n\n## Notes\n\nThe third component does a third thing.\n",
        },
    )
    assert refine(conn, project_id=project.id).adjusted == 0


def test_importance_refinement_is_idempotent(conn):
    project = prepo.create(conn, Project(name="p", root_path="/tmp/kernote-imp2"))
    for index in range(3):
        memory = mrepo.create(
            conn,
            _memory(
                project.id,
                title=f"T{index}: commands",
                source_refs=[
                    SourceRef(
                        rel_path=f"d/{index}.md",
                        line_start=1,
                        line_end=2,
                        content_hash=f"x{index}",
                    )
                ],
            ),
        )
        entities.link(conn, project.id, memory)
    refine(conn, project_id=project.id)
    scores = {m.id: m.importance for m in mrepo.list_for_project(conn, project.id)}
    refine(conn, project_id=project.id)
    assert {m.id: m.importance for m in mrepo.list_for_project(conn, project.id)} == scores


# -------------------------------------------------------------------- API


def test_analyze_endpoint_runs_every_detector(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    client.post(f"/api/v1/projects/{pid}/scan")
    res = client.post(f"/api/v1/projects/{pid}/analyze")
    assert res.status_code == 200, res.text
    body = res.json()
    for key in (
        "drift_high",
        "drift_medium",
        "drift_low",
        "refs_checked",
        "conflicts_procedure",
        "conflicts_decision",
        "duplicate_candidates",
        "proposals_created",
        "importance_adjusted",
        "open_findings",
    ):
        assert key in body
    assert body["refs_checked"] > 0

    assert client.get(f"/api/v1/projects/{pid}/findings").status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/proposals").status_code == 200


def test_analyze_unknown_project_is_404(client):
    assert client.post("/api/v1/projects/nope/analyze").status_code == 404


@pytest.mark.parametrize("path", ["findings", "proposals"])
def test_maintenance_reads_unknown_project_are_404(client, path):
    assert client.get(f"/api/v1/projects/nope/{path}").status_code == 404


# ===================== Stage 4 defect sweep regressions =====================


def test_filler_only_titles_are_still_compared(conn, tmp_path):
    """ "Overview" and "Commands" are entirely filler words, so the stripped
    token set was empty: the bucket signature was empty and Jaccard returned
    0.0. 120 files sharing an "Overview" heading produced zero comparisons."""
    files = {
        f"d{index}.md": f"# D{index}\n\n## Overview\n\n"
        "This module does something useful for the system.\n"
        for index in range(8)
    }
    project = _scan(conn, tmp_path, files)
    result = detect_duplicates(conn, project_id=project.id)
    assert result.compared > 0, "filler-only titles were never bucketed"
    assert result.candidates > 0, "identical sections were not flagged"


@pytest.mark.parametrize("title", ["Overview", "Commands", "This is it"])
def test_signature_and_scoring_tokens_agree(title):
    """Bucketing and scoring must use the same fallback, or a pair is bucketed
    and then scored 0.0."""
    from kernote.maintain.duplicates import _signature, _title_tokens

    assert _signature(title), f"{title!r} has no bucket signature"
    assert _title_tokens(title), f"{title!r} has no scoring tokens"


def test_large_buckets_use_a_canonical_comparison(conn, tmp_path):
    """Twenty-five identical sections are 300 pairs but only 24 useful
    statements. Pairwise findings would make the queue unusable."""
    files = {
        f"d{index}.md": f"# D{index}\n\n## Overview\n\n"
        "This module does something useful for the system.\n"
        for index in range(12)
    }
    project = _scan(conn, tmp_path, files)
    result = detect_duplicates(conn, project_id=project.id)
    # Star, not clique: n-1 rather than n(n-1)/2.
    assert result.compared == 11, result.compared


def test_very_large_bucket_is_truncated_not_unbounded(conn, tmp_path):
    files = {
        f"d{index}.md": f"# D{index}\n\n## Overview\n\nShared body text here for all.\n"
        for index in range(60)
    }
    project = _scan(conn, tmp_path, files)
    result = detect_duplicates(conn, project_id=project.id)
    assert result.compared <= 25, "bucket cap did not apply"
    assert result.candidates <= 200


def test_different_extractors_are_not_compared(conn, tmp_path):
    """A section in one file and a command block in another shared a title and
    an overlapping body, giving 4 candidates where only 2 were real."""
    block = "# {t}\n\n## Setup\n\nInstall first:\n\n```bash\npip install -e .\n```\n"
    project = _scan(
        conn,
        tmp_path,
        {"README.md": block.format(t="A"), "GUIDE.md": block.format(t="G")},
    )
    detect_duplicates(conn, project_id=project.id)
    pairs = conn.execute(
        "SELECT m1.extraction_method AS a, m2.extraction_method AS b "
        "FROM findings f JOIN memories m1 ON m1.id=f.memory_id "
        "JOIN memories m2 ON m2.id=f.other_id WHERE f.kind='duplicate'"
    ).fetchall()
    assert pairs, "no duplicate findings at all"
    for row in pairs:
        assert row["a"] == row["b"], f"cross-granularity pair: {row['a']} vs {row['b']}"


def test_entity_derivation_is_bounded(conn):
    """A 400-dependency manifest derived 401 entities and, at two queries
    each, 800 statements for one memory."""
    manifest = "\n".join(f"package-{index}>=1.0" for index in range(400))
    memory = _memory(
        "p",
        type=MemoryType.PROJECT_FACT,
        title="Python dependencies (400)",
        content=manifest,
        extraction_method="rule:manifests",
        source_refs=[SourceRef(rel_path="requirements.txt", content_hash="h")],
    )
    pairs = entities.derive(memory)
    assert len(pairs) <= 60, len(pairs)
    # The cap must not drop the path entities, which other features rely on.
    assert ("file", "requirements.txt") in pairs


def test_no_dead_fan_in_helper():
    """`entities.fan_in()` was defined and never called; importance.py has its
    own query."""
    assert not hasattr(entities, "fan_in")
