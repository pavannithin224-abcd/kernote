"""Stage 5: keyword search, semantic search, fusion, evidence composition.

The gate measures citation correctness and honest abstention, not answer
fluency (ADR-0015). Semantic tests skip when the model is not cached, because
`CLAUDE.md` forbids a test suite that reaches the network.
"""

import pytest

from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project
from kernote.retrieval import answer, embed, fts, hybrid, vector

PROJECT_DOCS = {
    "README.md": """# Widgetly

## Architecture

The render package turns widget definitions into SVG and must stay free of
database imports.

## Running the tests

Run the suite with pytest before pushing.
""",
    "docs/adr/0001-postgres.md": """# 1. Use PostgreSQL for persistence

## Status

Accepted

Date: 2026-03-11

## Decision

We will use PostgreSQL because several render workers write concurrently.

## Considered Options

- *SQLite* — rejected for write contention.
""",
}

SEMANTIC_AVAILABLE = embed.status().cached


def _project(conn, tmp_path, docs=None):
    for name, text in (docs or PROJECT_DOCS).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    project = prepo.create(conn, Project(name="s", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=200
    )
    return project


# ============================ query safety ============================
# Measured before this module existed: 8 of 10 realistic questions raised
# sqlite3.OperationalError when passed straight to MATCH.


@pytest.mark.parametrize(
    "query",
    [
        "what's the setup?",
        "sqlite-vec",
        "C++",
        "100%",
        "",
        "OR",
        "a AND",
        "NEAR(",
        '"unterminated',
        "why did we choose numpy over sqlite-vec?",
        "100% of the time",
        "foo | bar * baz",
        "^$()[]{}",
    ],
)
def test_no_query_can_crash_fts(conn, tmp_path, query):
    project = _project(conn, tmp_path)
    # Must not raise, whatever the input.
    fts.search_memories(conn, project_id=project.id, query=query)
    fts.search_chunks(conn, project_id=project.id, query=query)


def test_build_match_quotes_every_term():
    assert fts.build_match("drift detection") == '"drift" OR "detection"'
    # Operators and punctuation become inert literals.
    assert fts.build_match("a AND b") == '"AND"'
    assert fts.build_match("sqlite-vec") == '"sqlite" OR "vec"'


def test_build_match_returns_none_when_unsearchable():
    for query in ("", "   ", "?!", "C++", "a"):
        assert fts.build_match(query) is None, query


def test_keyword_search_finds_the_right_document(conn, tmp_path):
    project = _project(conn, tmp_path)
    hits = fts.search_memories(conn, project_id=project.id, query="PostgreSQL", limit=5)
    assert hits
    titles = [
        conn.execute("SELECT title FROM memories WHERE id=?", (h.target_id,)).fetchone()[0]
        for h in hits
    ]
    assert any("PostgreSQL" in t for t in titles), titles


def test_superseded_memories_are_not_retrievable(conn, tmp_path):
    """A replaced claim must not come back as current evidence."""
    from kernote.db.repositories import memories as mrepo

    project = _project(conn, tmp_path)
    target = next(
        m
        for m in mrepo.list_for_project(conn, project.id, limit=200)
        if "PostgreSQL" in m.title
    )
    replacement = target.model_copy(
        update={"id": None, "title": "Use CockroachDB for persistence"}
    )
    from kernote.domain.models import Memory

    new_memory = Memory(
        **{
            **target.model_dump(),
            "id": "11111111-1111-1111-1111-111111111111",
            "title": "Use CockroachDB",
            "superseded_by": None,
            "supersedes": None,
        }
    )
    mrepo.supersede(conn, target.id, new_memory, reason="moved again")
    hits = fts.search_memories(conn, project_id=project.id, query="PostgreSQL", limit=20)
    assert target.id not in {h.target_id for h in hits}
    assert replacement is not None  # silence the unused local


# ============================ fusion ============================


def test_hybrid_works_without_semantic(conn, tmp_path):
    """Keyword-only is a working mode, not a degraded one (ADR-0023)."""
    project = _project(conn, tmp_path)
    embed.reset_for_tests()
    outcome = hybrid.search(conn, project_id=project.id, query="render package SVG", limit=5)
    assert outcome.results
    assert outcome.keyword_hits > 0
    if not outcome.semantic_available:
        assert outcome.note and "keyword-only" in outcome.note


def test_every_result_explains_its_rank(conn, tmp_path):
    """MEMORY_MODEL.md: retrieval must return score/reason metadata."""
    project = _project(conn, tmp_path)
    outcome = hybrid.search(conn, project_id=project.id, query="PostgreSQL", limit=5)
    assert outcome.results
    for result in outcome.results:
        assert result.why, "a result with no explanation"
        assert result.keyword_rank or result.semantic_rank


def test_fusion_does_not_crash_on_an_empty_project(conn, tmp_path):
    project = prepo.create(conn, Project(name="empty", root_path=str(tmp_path)))
    outcome = hybrid.search(conn, project_id=project.id, query="anything", limit=5)
    assert outcome.results == []


# ============================ composition ============================


def test_evidence_found_carries_citations(conn, tmp_path):
    """The question uses words the fixture actually contains.

    "which database did we choose" was the original, and it correctly returns
    `weak_evidence`: the ADR says "PostgreSQL" and "persistence" and never
    "database" or "choose". That is the honest limit of extractive matching
    with no language model, and raising the bar exposed it rather than
    breaking anything.
    """
    project = _project(conn, tmp_path)
    bundle = answer.ask(
        conn, project_id=project.id, question="why use PostgreSQL for persistence", limit=5
    )
    assert bundle.outcome == "evidence_found"
    assert bundle.evidence
    for item in bundle.evidence:
        assert item.citation and item.citation != "unknown"
        assert item.kind in ("evidence", "inference")
        assert item.matched_terms, "an item counted as support with no matched term"


def test_unanswerable_question_abstains(conn, tmp_path):
    """Abstention is a correct outcome, not a failure (CLAUDE.md)."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(
        conn,
        project_id=project.id,
        question="what is the airspeed velocity of an unladen swallow",
        limit=5,
    )
    assert bundle.outcome in ("weak_evidence", "not_found")
    assert "swallow" in " ".join(bundle.unknowns)


def test_stopwords_alone_do_not_manufacture_support(conn, tmp_path):
    """Before the stopword filter, matching "an", "is", "of" and "the" in a
    spec document reported a nonsense question as `evidence_found`."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(conn, project_id=project.id, question="what is the the of an", limit=5)
    assert bundle.outcome != "evidence_found"


def test_plural_query_matches_singular_source(conn, tmp_path):
    """An exact substring test reported "secrets" as unsupported by a document
    that says "secret", a false negative."""
    docs = {
        "SECURITY.md": "# Security\n\n## Secret handling\n\n"
        "A secret is never written to the database under any circumstance.\n"
    }
    project = _project(conn, tmp_path, docs)
    bundle = answer.ask(
        conn, project_id=project.id, question="how are secrets handled", limit=5
    )
    assert bundle.outcome == "evidence_found", bundle.statement


def test_the_same_source_is_not_cited_twice(conn, tmp_path):
    """A memory and the chunk it came from cite identical lines."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(
        conn, project_id=project.id, question="render package SVG database", limit=10
    )
    citations = [i.citation for i in bundle.evidence]
    assert len(citations) == len(set(citations)), citations


def test_interpretations_are_labelled_separately(conn, tmp_path):
    from kernote.db.repositories import memories as mrepo
    from kernote.domain.models import ClaimKind, Memory, MemoryType, SourceRef

    project = _project(conn, tmp_path)
    mrepo.create(
        conn,
        Memory(
            project_id=project.id,
            type=MemoryType.ARCHITECTURE,
            title="Rendering probably bottlenecks on SVG assembly",
            content="Rendering probably bottlenecks on SVG string assembly.",
            claim_kind=ClaimKind.INTERPRETATION,
            importance=0.6,
            importance_reason="r",
            confidence=0.4,
            confidence_reason="model-generated interpretation",
            extraction_method="model:test@1",
            source_refs=[
                SourceRef(rel_path="README.md", line_start=1, line_end=2, content_hash="h")
            ],
        ),
    )
    bundle = answer.ask(
        conn, project_id=project.id, question="bottlenecks on SVG assembly", limit=5
    )
    kinds = {i.kind for i in bundle.evidence}
    assert "inference" in kinds, [i.title for i in bundle.evidence]


def test_turn_is_persisted_with_a_trace(conn, tmp_path):
    """Session state is separate from durable memory (MEMORY_MODEL.md §8), and
    the trace is what makes a bad answer debuggable afterwards."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(conn, project_id=project.id, question="which database", limit=3)
    assert bundle.session_id and bundle.turn_id
    row = conn.execute(
        "SELECT question, answer, citations_json, trace_json FROM ask_turns WHERE id=?",
        (bundle.turn_id,),
    ).fetchone()
    assert row["question"] == "which database"
    assert row["trace_json"] and "outcome" in row["trace_json"]
    # Nothing was promoted into the vault.
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM memories WHERE content LIKE '%which database%'"
        ).fetchone()[0]
        == 0
    )


def test_followup_reuses_the_session(conn, tmp_path):
    project = _project(conn, tmp_path)
    first = answer.ask(conn, project_id=project.id, question="which database", limit=3)
    second = answer.ask(
        conn,
        project_id=project.id,
        question="why that database",
        limit=3,
        session_id=first.session_id,
    )
    assert second.session_id == first.session_id
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM ask_turns WHERE session_id=?", (first.session_id,)
        ).fetchone()[0]
        == 2
    )


# ============================ embeddings ============================


def test_status_never_touches_the_network():
    """`CLAUDE.md`: no outbound calls by default."""
    status = embed.status()
    assert status.model_id
    assert status.dim == 384
    assert isinstance(status.cached, bool)


def test_encode_refuses_to_download_without_permission(monkeypatch):
    embed.reset_for_tests()
    monkeypatch.setattr(
        embed,
        "status",
        lambda: embed.EmbedStatus(
            model_id=embed.MODEL_ID,
            dim=embed.DIM,
            cached=False,
            enabled=True,
            cache_path="/nonexistent",
            download_mb=90,
        ),
    )
    assert embed.encode(["anything"]) == []
    embed.reset_for_tests()


def test_index_build_is_skipped_when_model_unavailable(conn, tmp_path, monkeypatch):
    project = _project(conn, tmp_path)
    embed.reset_for_tests()
    monkeypatch.setattr(embed, "ensure_model", lambda **_: None)
    result = vector.build_index(conn, project_id=project.id)
    assert result.skipped
    assert result.embedded_memories == 0


@pytest.mark.skipif(not SEMANTIC_AVAILABLE, reason="embedding model not cached")
def test_semantic_index_and_search(conn, tmp_path):
    project = _project(conn, tmp_path)
    built = vector.build_index(conn, project_id=project.id)
    assert built.skipped is None
    assert built.embedded_memories > 0

    # Incremental: a second build embeds nothing new.
    again = vector.build_index(conn, project_id=project.id)
    assert again.embedded_memories == 0 and again.embedded_chunks == 0

    hits = vector.search(conn, project_id=project.id, query="relational datastore", limit=5)
    assert hits
    assert all(-1.0 <= h.similarity <= 1.0 for h in hits)


@pytest.mark.skipif(not SEMANTIC_AVAILABLE, reason="embedding model not cached")
def test_vectors_are_project_scoped(conn, tmp_path):
    """One project's vectors must never score against another's."""
    first = _project(conn, tmp_path / "a")
    second = _project(conn, tmp_path / "b")
    vector.build_index(conn, project_id=first.id)
    vector.build_index(conn, project_id=second.id)
    hits = vector.search(conn, project_id=first.id, query="database", limit=50)
    from kernote.db.repositories import memories as mrepo

    second_ids = {m.id for m in mrepo.list_for_project(conn, second.id, limit=500)}
    assert not ({h.target_id for h in hits} & second_ids)


@pytest.mark.skipif(not SEMANTIC_AVAILABLE, reason="embedding model not cached")
def test_clear_drops_vectors_and_index_rebuilds(conn, tmp_path):
    """L4 is disposable (ADR-0002)."""
    project = _project(conn, tmp_path)
    vector.build_index(conn, project_id=project.id)
    before = vector.search(conn, project_id=project.id, query="database", limit=5)
    assert vector.clear(conn, project_id=project.id) > 0
    assert vector.search(conn, project_id=project.id, query="database", limit=5) == []
    vector.build_index(conn, project_id=project.id)
    after = vector.search(conn, project_id=project.id, query="database", limit=5)
    assert [h.target_id for h in after] == [h.target_id for h in before]


# ============================ API ============================


def test_ask_endpoint(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    client.post(f"/api/v1/projects/{pid}/scan")
    res = client.post(
        f"/api/v1/projects/{pid}/ask", json={"question": "which database do we use"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["outcome"] in ("evidence_found", "weak_evidence", "not_found")
    assert "statement" in body and body["statement"]
    assert isinstance(body["evidence"], list)


def test_ask_rejects_an_empty_question(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    assert client.post(f"/api/v1/projects/{pid}/ask", json={"question": ""}).status_code == 422


def test_embedding_status_endpoint_reports_without_downloading(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    body = client.get(f"/api/v1/projects/{pid}/embeddings").json()
    assert body["model_id"] and body["dim"] == 384
    assert body["download_mb"] == 90
    assert "indexed_memories" in body


def test_ask_unknown_project_is_404(client):
    assert client.post("/api/v1/projects/nope/ask", json={"question": "x"}).status_code == 404


def test_one_coincidental_word_is_not_support(conn, tmp_path):
    """Found by the live run: "what is the airspeed velocity of an unladen
    swallow" was reported as `evidence_found` because CLAUDE.md contains "Do
    not **swallow** errors" -- one coincidental word out of four terms."""
    docs = {
        "GUIDE.md": "# Guide\n\n## Error handling\n\n"
        "Do not swallow errors; surface an actionable message instead.\n"
    }
    project = _project(conn, tmp_path, docs)
    bundle = answer.ask(
        conn,
        project_id=project.id,
        question="what is the airspeed velocity of an unladen swallow",
        limit=5,
    )
    assert bundle.outcome == "weak_evidence", bundle.statement
    assert any("airspeed" in u for u in bundle.unknowns)


def test_a_single_word_question_still_works(conn, tmp_path):
    """The support bar scales with the question: asking one word cannot
    require two matches."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(conn, project_id=project.id, question="PostgreSQL", limit=5)
    assert bundle.outcome == "evidence_found", bundle.statement


def test_two_matched_terms_are_enough(conn, tmp_path):
    project = _project(conn, tmp_path)
    bundle = answer.ask(conn, project_id=project.id, question="render package SVG", limit=5)
    assert bundle.outcome == "evidence_found"
    assert len(bundle.evidence[0].matched_terms) >= 2


def test_a_question_using_words_absent_from_the_source_abstains(conn, tmp_path):
    """The flip side, pinned deliberately: "database" is a reasonable word for
    a question about PostgreSQL, but no source says it, so Kernote abstains
    rather than guessing. This is the documented cost of ADR-0006's
    no-LLM-in-the-core-loop rule."""
    project = _project(conn, tmp_path)
    bundle = answer.ask(
        conn, project_id=project.id, question="which database did we choose", limit=5
    )
    assert bundle.outcome == "weak_evidence"


# ===================== Stage 5 defect sweep regressions =====================


def test_stemmer_does_not_match_unrelated_words():
    """Chopping a fixed two characters made "import" into "impo", a prefix of
    "important", so a question about imports was "supported" by a sentence
    about importance."""
    from kernote.retrieval.answer import _mentions, _stems_of

    assert not _mentions(_stems_of("this is important work"), "import")
    assert not _mentions(_stems_of("important"), "imports")
    assert not _mentions(_stems_of("management overhead"), "manage")
    assert not _mentions(_stems_of("a vectorise helper"), "vector")


@pytest.mark.parametrize(
    ("term", "text"),
    [
        ("secrets", "Secret refusal is two-tier"),
        ("imports", "the import statement"),
        ("dependencies", "a dependency list"),
        ("deleted", "we delete nothing"),  # silent-e
        ("caches", "a cached model"),  # silent-e
        ("severity", "drift severity bands"),
    ],
)
def test_stemmer_still_matches_real_inflections(term, text):
    from kernote.retrieval.answer import _mentions, _stems_of

    assert _mentions(_stems_of(text), term)


@pytest.mark.parametrize("acronym", ["ci", "db", "ui", "ml"])
def test_two_letter_technical_terms_are_searchable(acronym):
    """Excluding them left "what does the CI do" with no content terms at all,
    so it could only ever abstain."""
    from kernote.retrieval.answer import _content_terms

    assert acronym in _content_terms([acronym, "the", "is"])


@pytest.mark.skipif(not SEMANTIC_AVAILABLE, reason="embedding model not cached")
def test_editing_a_memory_refreshes_its_vector(conn, tmp_path):
    """The index silently diverged from the source of truth: an edited memory
    kept its old vector, so semantic search went on matching text the project
    no longer contained."""
    from kernote.db.repositories import memories as mrepo

    project = _project(
        conn,
        tmp_path,
        {"README.md": "# App\n\n## Storage\n\nWe store widgets in PostgreSQL.\n"},
    )
    vector.build_index(conn, project_id=project.id)
    memory = mrepo.list_for_project(conn, project.id, limit=10)[0]
    before = conn.execute(
        "SELECT vector FROM embeddings WHERE target_id=?", (memory.id,)
    ).fetchone()[0]

    mrepo.update(
        conn,
        memory.id,
        title="Storage uses Cassandra now",
        content="We store widgets in Cassandra for durability.",
        summary=None,
        change_reason="migrated",
    )
    result = vector.build_index(conn, project_id=project.id)
    assert result.embedded_memories >= 1, "the edited memory was not re-embedded"
    after = conn.execute(
        "SELECT vector FROM embeddings WHERE target_id=?", (memory.id,)
    ).fetchone()[0]
    assert before != after

    hits = vector.search(conn, project_id=project.id, query="Cassandra", limit=5)
    assert memory.id in {h.target_id for h in hits}


@pytest.mark.skipif(not SEMANTIC_AVAILABLE, reason="embedding model not cached")
def test_unchanged_content_is_not_re_embedded(conn, tmp_path):
    """Freshness must not cost idempotency. `updated_at` was the obvious
    alternative to a content hash and is wrong: importance refinement touches
    it without changing a word."""
    from kernote.maintain.importance import refine

    project = _project(conn, tmp_path)
    vector.build_index(conn, project_id=project.id)
    refine(conn, project_id=project.id)
    again = vector.build_index(conn, project_id=project.id)
    assert again.embedded_memories == 0
    assert again.embedded_chunks == 0


def test_deleting_a_memory_removes_its_vector(conn, tmp_path):
    """`embeddings` has a polymorphic target so it cannot carry a foreign key;
    deleting a project left its vectors behind forever (migration 0004)."""
    project = _project(conn, tmp_path)
    conn.execute(
        "INSERT INTO embeddings(target_kind,target_id,model_id,dim,vector,built_at) "
        "SELECT 'memory', id, 'test-model', 2, X'0000', '2026-01-01' "
        "FROM memories WHERE project_id=?",
        (project.id,),
    )
    seeded = conn.execute(
        "SELECT COUNT(*) FROM embeddings WHERE model_id='test-model'"
    ).fetchone()[0]
    assert seeded > 0
    conn.execute("DELETE FROM projects WHERE id=?", (project.id,))
    assert (
        conn.execute("SELECT COUNT(*) FROM embeddings WHERE model_id='test-model'").fetchone()[
            0
        ]
        == 0
    ), "orphaned vectors survived the cascade"
