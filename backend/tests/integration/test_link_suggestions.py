"""Ranked suggestions and batch answers.

Two things matter here. The ranking has to be *better* than the graph's
per-entity weight, or it is not worth a second code path. And the batch
endpoint must not become a way around the guards the single-pair endpoints
enforce -- a convenience for a human answering many questions is not the
same as a bulk writer.
"""

from __future__ import annotations

import pytest

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
from kernote.maintain import links, suggestions
from kernote.maintain.findings import record


def _memory(conn, project_id: str, title: str) -> Memory:
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
            importance_reason="t",
            confidence=0.5,
            confidence_reason="t",
            source_refs=[SourceRef(user_note="t")],
        ),
        change_reason="t",
        actor="user",
    )


def _entity(conn, name: str, memory_ids: list[str]) -> None:
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
    return prepo.create(conn, Project(name="s", root_path="/tmp/s"))


def test_repeated_overlap_outranks_a_single_share(project, conn):
    """The reason this exists rather than reusing the graph's weight.

    The graph scores each shared entity separately and keeps the best, so a
    pair sharing three rare files looks identical to one sharing one. That
    is backwards: repeated specific overlap is the strongest evidence here.
    """
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    for name in ("one.py", "two.py", "three.py"):
        _entity(conn, name, [a.id, b.id])

    c, d = _memory(conn, project.id, "C"), _memory(conn, project.id, "D")
    _entity(conn, "solo.py", [c.id, d.id])

    top = suggestions.ranked(conn, project.id)
    assert {top[0].src_id, top[0].dst_id} == {a.id, b.id}
    assert top[0].score > top[1].score
    assert len(top[0].shared) == 3


def test_a_rarer_entity_outranks_a_commoner_one(project, conn):
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "rare.py", [a.id, b.id])

    crowd = [_memory(conn, project.id, f"C{i}") for i in range(6)]
    _entity(conn, "common.py", [m.id for m in crowd])

    top = suggestions.ranked(conn, project.id)
    assert {top[0].src_id, top[0].dst_id} == {a.id, b.id}


def test_settled_questions_are_not_asked_again(project, conn):
    """A triage list that keeps showing answered pairs is one nobody finishes."""
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "shared.py", [a.id, b.id])
    assert len(suggestions.ranked(conn, project.id)) == 1

    links.dismiss(conn, project_id=project.id, src_id=a.id, dst_id=b.id)
    assert suggestions.ranked(conn, project.id) == []


def test_a_confirmed_pair_drops_off_the_list(project, conn):
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "shared.py", [a.id, b.id])
    links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id)
    assert suggestions.ranked(conn, project.id) == []


def test_pairs_the_review_queue_owns_are_left_to_it(project, conn):
    """An open duplicate finding has a better answer waiting than "related"."""
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "shared.py", [a.id, b.id])
    record(
        conn,
        project.id,
        Finding(
            kind=FindingKind.DUPLICATE,
            severity=Severity.LOW,
            detector="test",
            memory_id=a.id,
            other_id=b.id,
            explanation="possible duplicate",
            evidence={"dedupe_key": "k"},
        ),
    )
    conn.commit()
    assert suggestions.ranked(conn, project.id) == []


def test_identical_titles_are_flagged_not_hidden(project, conn):
    """ "Related" is probably the wrong answer; the user should know that."""
    a = _memory(conn, project.id, "Run the tests")
    b = _memory(conn, project.id, "Run the tests")
    _entity(conn, "shared.py", [a.id, b.id])

    top = suggestions.ranked(conn, project.id)
    assert len(top) == 1, "it must still be listed"
    assert top[0].same_title is True


def test_a_batch_applies_both_verdicts(project, conn):
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    c, d = _memory(conn, project.id, "C"), _memory(conn, project.id, "D")
    _entity(conn, "one.py", [a.id, b.id])
    _entity(conn, "two.py", [c.id, d.id])

    result = suggestions.apply_batch(
        conn,
        project_id=project.id,
        decisions=[
            {"src_id": a.id, "dst_id": b.id, "verdict": "confirm"},
            {"src_id": c.id, "dst_id": d.id, "verdict": "dismiss"},
        ],
    )
    assert (result.confirmed, result.dismissed, result.failed) == (1, 1, [])
    assert suggestions.ranked(conn, project.id) == []


def test_a_batch_cannot_bypass_the_guards(project, conn):
    """A convenience for answering many questions, not a bulk writer."""
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "one.py", [a.id, b.id])

    result = suggestions.apply_batch(
        conn,
        project_id=project.id,
        decisions=[
            {"src_id": a.id, "dst_id": b.id, "verdict": "confirm", "kind": "supersedes"}
        ],
    )
    assert result.confirmed == 0
    assert "not a relationship a person asserts" in result.failed[0]["error"]


def test_one_bad_decision_does_not_discard_the_rest(project, conn):
    """Forty answers where three are stale should apply thirty-seven."""
    a, b = _memory(conn, project.id, "A"), _memory(conn, project.id, "B")
    _entity(conn, "one.py", [a.id, b.id])

    result = suggestions.apply_batch(
        conn,
        project_id=project.id,
        decisions=[
            {"src_id": a.id, "dst_id": "ghost", "verdict": "confirm"},
            {"src_id": a.id, "dst_id": b.id, "verdict": "confirm"},
        ],
    )
    assert result.confirmed == 1
    assert len(result.failed) == 1
    assert "ghost" in result.failed[0]["dst_id"]


def test_over_http(client, tmp_path):
    (tmp_path / "README.md").write_text("# A\n\n## Setup\n\nRun make.\n", encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "h", "root_path": str(tmp_path)}
    ).json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")

    listed = client.get(f"/api/v1/projects/{pid}/links/suggestions?limit=5")
    assert listed.status_code == 200
    rows = listed.json()
    if not rows:
        pytest.skip("this corpus produced no suggestions")
    assert rows == sorted(rows, key=lambda r: -r["score"]), "not ranked"

    applied = client.post(
        f"/api/v1/projects/{pid}/links/batch",
        json={
            "decisions": [
                {"src_id": rows[0]["src_id"], "dst_id": rows[0]["dst_id"], "verdict": "confirm"}
            ]
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["confirmed"] == 1


def test_an_unknown_verdict_is_refused_by_the_schema(client, tmp_path):
    pid = client.post(
        "/api/v1/projects", json={"name": "v", "root_path": str(tmp_path)}
    ).json()["id"]
    r = client.post(
        f"/api/v1/projects/{pid}/links/batch",
        json={"decisions": [{"src_id": "a", "dst_id": "b", "verdict": "delete_everything"}]},
    )
    assert r.status_code == 422
