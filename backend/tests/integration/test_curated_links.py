"""Confirming and dismissing relationships.

The graph suggests edges from entity co-occurrence. This is where a
suggestion becomes a judgement, and the thing most worth protecting is that
the two kinds stay distinguishable: a link a person confirmed is not the
same as one a merge left behind, and a dismissal must actually stop the
suggestion recurring rather than hiding it until the next reload.
"""

from __future__ import annotations

import pytest

from kernote.db.repositories import graph as graph_repo
from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import ClaimKind, Memory, MemoryType, Project, SourceRef, new_id
from kernote.maintain import links


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
def suggested(conn):
    """Two memories the graph suggests are related."""
    project = prepo.create(conn, Project(name="l", root_path="/tmp/l"))
    a = _memory(conn, project.id, "Uses Redis")
    b = _memory(conn, project.id, "Redis eviction")
    _entity(conn, "redis.conf", [a.id, b.id])
    g = graph_repo.build(conn, project.id)
    assert [e["kind"] for e in g.edges] == ["shares"]
    assert g.edges[0]["origin"] == "suggested"
    return project, a, b


def test_confirming_makes_the_relationship_durable(suggested, conn):
    project, a, b = suggested
    links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id)

    g = graph_repo.build(conn, project.id)
    edge = g.edges[0]
    assert edge["kind"] == "relates_to"
    assert edge["origin"] == "user", "a confirmed link must be distinguishable from a merge's"

    # Durable: it is a row, not a re-derivation.
    assert conn.execute("SELECT COUNT(*) FROM memory_links").fetchone()[0] == 1


def test_a_dismissed_suggestion_stops_coming_back(suggested, conn):
    """Otherwise 'dismiss' means 'hide until reload', which is not a decision."""
    project, a, b = suggested
    links.dismiss(conn, project_id=project.id, src_id=a.id, dst_id=b.id, note="unrelated")

    g = graph_repo.build(conn, project.id)
    assert g.edges == []


def test_the_pair_is_the_same_whichever_way_round(suggested, conn):
    project, a, b = suggested
    links.dismiss(conn, project_id=project.id, src_id=b.id, dst_id=a.id)
    assert graph_repo.build(conn, project.id).edges == []


def test_confirming_overrides_an_earlier_dismissal(suggested, conn):
    project, a, b = suggested
    links.dismiss(conn, project_id=project.id, src_id=a.id, dst_id=b.id)
    links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id)

    g = graph_repo.build(conn, project.id)
    assert len(g.edges) == 1 and g.edges[0]["origin"] == "user"
    assert conn.execute("SELECT COUNT(*) FROM link_rejections").fetchone()[0] == 0


def test_a_recorded_link_cannot_be_dismissed_as_if_it_were_a_suggestion(suggested, conn):
    project, a, b = suggested
    links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id)
    with pytest.raises(ValueError, match="recorded, not suggested"):
        links.dismiss(conn, project_id=project.id, src_id=a.id, dst_id=b.id)


def test_a_confirmed_link_can_be_withdrawn(suggested, conn):
    project, a, b = suggested
    links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id)
    assert links.remove(conn, project_id=project.id, src_id=a.id, dst_id=b.id) is True
    # Back to a suggestion, not gone: nothing said it was wrong.
    assert graph_repo.build(conn, project.id).edges[0]["origin"] == "suggested"


def test_a_merge_link_is_not_withdrawable_here(conn, tmp_path):
    """It is a consequence of a consolidation, undone by undoing that."""
    project = prepo.create(conn, Project(name="m", root_path=str(tmp_path)))
    a = _memory(conn, project.id, "Keeper")
    b = _memory(conn, project.id, "Absorbed")
    mrepo.supersede_into(
        conn, absorb_id=b.id, keep_id=a.id, merged_content="merged", reason="test"
    )
    with pytest.raises(ValueError, match="undo the consolidation"):
        links.remove(conn, project_id=project.id, src_id=a.id, dst_id=b.id)


def test_only_relationship_kinds_a_person_asserts_are_allowed(suggested, conn):
    """`supersedes` and `duplicate_of` change what the vault serves.

    Those belong to the consolidation flow, with its preview, approval and
    undo -- not to a button on a graph.
    """
    project, a, b = suggested
    for kind in ("supersedes", "duplicate_of"):
        with pytest.raises(ValueError, match="not a relationship a person asserts"):
            links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=b.id, kind=kind)


def test_a_memory_cannot_be_related_to_itself(suggested, conn):
    project, a, _ = suggested
    with pytest.raises(ValueError, match="itself"):
        links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=a.id)


def test_cross_project_links_are_refused(suggested, conn):
    project, a, _ = suggested
    other = prepo.create(conn, Project(name="other", root_path="/tmp/other"))
    stranger = _memory(conn, other.id, "Elsewhere")
    with pytest.raises(ValueError, match="another project"):
        links.confirm(conn, project_id=project.id, src_id=a.id, dst_id=stranger.id)


def test_over_http(client, tmp_path):
    (tmp_path / "README.md").write_text("# A\n\n## Setup\n\nRun make.\n", encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "h", "root_path": str(tmp_path)}
    ).json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    graph = client.get(f"/api/v1/projects/{pid}/graph").json()
    if not graph["edges"]:
        pytest.skip("this corpus produced no suggestions")

    edge = graph["edges"][0]
    ok = client.post(
        f"/api/v1/memories/{edge['src']}/links?project_id={pid}",
        json={"other_id": edge["dst"], "kind": "relates_to"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["origin"] == "user"

    bad = client.post(
        f"/api/v1/memories/{edge['src']}/links?project_id={pid}",
        json={"other_id": edge["dst"], "kind": "supersedes"},
    )
    assert bad.status_code == 422
