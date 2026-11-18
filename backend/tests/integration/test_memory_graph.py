"""The graph draws relationships that exist, and no others.

The brief for Memory Pulse said: do not generate fake relationships. That is
easy to honour by accident on a rich project and easy to violate by accident
on a sparse one, because a graph with no edges looks broken and the temptation
is to loosen something until edges appear.

The threshold is where that pressure lands. Entity co-occurrence is the only
signal dense enough to draw a network from, and raising `SPREAD_MAX` is the
one-character change that turns a sparse honest graph into a dense meaningless
one -- on this repository the entity `docs` alone would contribute 7,503 edges
that say only "both mention documentation".
"""

from __future__ import annotations

import sqlite3

import pytest

from kernote.db.repositories import graph as graph_repo
from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import (
    ClaimKind,
    Finding,
    FindingKind,
    Memory,
    MemoryType,
    Project,
    Severity,
    SourceRef,
    new_id,
)
from kernote.maintain.findings import record


def _memory(conn: sqlite3.Connection, project_id: str, title: str) -> Memory:
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


def _entity(conn: sqlite3.Connection, name: str, memory_ids: list[str]) -> None:
    entity_id = new_id()
    conn.execute(
        "INSERT INTO entities(id, project_id, kind, name) "
        "SELECT ?, project_id, 'file', ? FROM memories WHERE id=?",
        (entity_id, name, memory_ids[0]),
    )
    for mid in memory_ids:
        conn.execute(
            "INSERT OR IGNORE INTO memory_entities(memory_id, entity_id) VALUES(?,?)",
            (mid, entity_id),
        )
    conn.commit()


@pytest.fixture
def project(conn):
    return prepo.create(conn, Project(name="g", root_path="/tmp/g"))


def test_memories_with_nothing_in_common_produce_no_edges(conn, project):
    """A sparse graph is the correct answer, not a reason to loosen a rule."""
    for i in range(5):
        _memory(conn, project.id, f"Unrelated {i}")

    g = graph_repo.build(conn, project.id)
    assert len(g.nodes) == 5
    assert g.edges == [], "edges appeared where no relationship was recorded"
    assert g.totals["connected_memories"] == 0


def test_a_shared_entity_creates_one_edge(conn, project):
    a = _memory(conn, project.id, "Uses Redis")
    b = _memory(conn, project.id, "Redis eviction policy")
    _entity(conn, "redis.conf", [a.id, b.id])

    g = graph_repo.build(conn, project.id)
    assert len(g.edges) == 1
    edge = g.edges[0]
    assert edge["kind"] == "shares"
    assert "redis.conf" in edge["reason"], "an edge must say why it exists"
    assert {edge["src"], edge["dst"]} == {a.id, b.id}


def test_a_ubiquitous_entity_creates_no_edges(conn, project):
    """The threshold, stated as a test.

    An entity attached to more memories than `SPREAD_MAX` describes a topic,
    not a relationship. Without this cut the graph fills with edges that are
    individually true and collectively meaningless.
    """
    ids = [
        _memory(conn, project.id, f"Doc note {i}").id for i in range(graph_repo.SPREAD_MAX + 1)
    ]
    _entity(conn, "docs", ids)

    g = graph_repo.build(conn, project.id)
    assert g.edges == []
    assert g.limits["entities_too_common"] == 1, "the omission must be reported, not hidden"


def test_a_rarer_entity_outweighs_a_commoner_one(conn, project):
    """Weight is specificity: two memories sharing something rare say more."""
    rare_a = _memory(conn, project.id, "Rare A")
    rare_b = _memory(conn, project.id, "Rare B")
    _entity(conn, "unusual.py", [rare_a.id, rare_b.id])

    common = [_memory(conn, project.id, f"Common {i}") for i in range(graph_repo.SPREAD_MAX)]
    _entity(conn, "common.py", [m.id for m in common])

    g = graph_repo.build(conn, project.id)
    weights = {e["reason"]: e["weight"] for e in g.edges}
    rare = next(w for r, w in weights.items() if "unusual.py" in r)
    commons = [w for r, w in weights.items() if "common.py" in r]
    assert rare == 1.0
    assert all(c < rare for c in commons), "a widely shared entity must weigh less"


def test_an_open_conflict_survives_the_node_cap(conn, project, monkeypatch):
    """Regression: the most interesting edge was being dropped silently.

    Conflicted memories have the *lowest* degree -- two claims that disagree
    usually share nothing else -- so ranking nodes by connectivity alone
    evicted them, and the conflict edge went with them. Caught by reading the
    real response and noticing every edge was a `shares`.
    """
    monkeypatch.setattr(graph_repo, "NODE_LIMIT", 6)

    # A dense cluster that will dominate any degree-based ranking.
    cluster = [_memory(conn, project.id, f"Cluster {i}") for i in range(6)]
    _entity(conn, "hub.py", [m.id for m in cluster])

    # Two lonely memories that disagree with each other.
    a = _memory(conn, project.id, "Deploy with make")
    b = _memory(conn, project.id, "Deploy with just")
    record(
        conn,
        project.id,
        Finding(
            kind=FindingKind.CONFLICT,
            severity=Severity.HIGH,
            detector="test",
            memory_id=a.id,
            other_id=b.id,
            explanation="Two sources give different deploy commands.",
            evidence={"dedupe_key": "test:conflict"},
        ),
    )
    conn.commit()

    g = graph_repo.build(conn, project.id)
    kinds = {e["kind"] for e in g.edges}
    assert "conflict" in kinds, (
        "the conflict edge was evicted by the node cap; flagged memories must "
        "outrank well-connected ones"
    )
    ids = {n["id"] for n in g.nodes}
    assert a.id in ids and b.id in ids


def test_a_rejected_duplicate_is_not_a_relationship(conn, project):
    """A human said these are not duplicates. The graph must not claim they are."""
    a = _memory(conn, project.id, "Claim A")
    b = _memory(conn, project.id, "Claim B")
    record(
        conn,
        project.id,
        Finding(
            kind=FindingKind.DUPLICATE,
            severity=Severity.LOW,
            detector="test",
            memory_id=a.id,
            other_id=b.id,
            explanation="Possible duplicate.",
            evidence={"dedupe_key": "test:dup"},
        ),
    )
    conn.execute("UPDATE findings SET status='rejected' WHERE project_id=?", (project.id,))
    conn.commit()

    g = graph_repo.build(conn, project.id)
    assert all(
        e["kind"] != "duplicate" for e in g.edges
    ), "a rejected finding is a human saying no; it cannot become an edge"


def test_truncation_is_reported(conn, project, monkeypatch):
    monkeypatch.setattr(graph_repo, "NODE_LIMIT", 3)
    for i in range(10):
        _memory(conn, project.id, f"Note {i}")

    g = graph_repo.build(conn, project.id)
    assert len(g.nodes) == 3
    assert g.totals["memories"] == 10
    assert g.limits["omitted_memories"] == 7, "a truncated graph must say how much it hid"
