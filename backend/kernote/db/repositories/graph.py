"""The memory graph: nodes and edges that already exist in the database.

Nothing here infers a relationship. Every edge is a row somebody or something
wrote down, and every edge carries the reason it exists so the UI can say what
it is looking at:

    conflict / duplicate   a finding that names two memories (`findings.other_id`)
    supersedes / refines   an explicit link (`memory_links`)
    shares                 two memories annotated with the same entity

**The `shares` edge needs a threshold, and the threshold is the whole idea.**
Entity co-occurrence is the only signal dense enough to make a graph out of,
and it is also the easiest way to accidentally invent meaning. On this
repository the entity `docs` is attached to 123 memories: drawing that as a
relationship would produce 7,503 edges that say nothing except "both of these
mention documentation". A *rare* shared entity is informative in exactly the
way a common one is not -- the same reasoning as IDF, which the retrieval side
already relies on.

So an entity is only allowed to create edges when it appears in at most
`SPREAD_MAX` memories, and the edge's weight is its specificity. The cutoff is
reported in the response rather than hidden, because a graph that silently
drops most of the data is lying by omission.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ...maintain import links as link_repo

# An entity shared by more than this many memories is a topic, not a link.
# Measured on this repository: a cap of 8 keeps 86 entities and yields ~695
# candidate edges; raising it to 20 adds 1,670 edges and no information.
SPREAD_MAX = 8

# Hard ceilings so one enormous project cannot hand the browser a graph it
# cannot draw. Both are reported when they bite.
NODE_LIMIT = 160
EDGE_LIMIT = 400


@dataclass
class Graph:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    totals: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)


def _explicit_edges(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    """Links somebody recorded deliberately, and findings naming two memories.

    These are never dropped by a threshold. A conflict between two claims is
    the single most interesting thing the graph can show, and there are only
    ever a handful of them.
    """
    edges: list[dict] = []

    for row in conn.execute(
        "SELECT l.src_id, l.dst_id, l.kind, l.reason, l.origin FROM memory_links l "
        "JOIN memories m ON m.id = l.src_id WHERE m.project_id = ?",
        (project_id,),
    ):
        edges.append(
            {
                "src": row["src_id"],
                "dst": row["dst_id"],
                "kind": row["kind"],
                "reason": row["reason"] or row["kind"].replace("_", " "),
                "weight": 1.0,
                # 'user' is a judgement somebody made; 'merge' is a
                # mechanical consequence of a consolidation. The graph shows
                # both, and the inspector offers to withdraw only the first.
                "origin": row["origin"] or "merge",
            }
        )

    for row in conn.execute(
        "SELECT memory_id, other_id, kind, explanation FROM findings "
        "WHERE project_id = ? AND other_id IS NOT NULL AND status = 'open' "
        "AND kind IN ('conflict','duplicate')",
        (project_id,),
    ):
        edges.append(
            {
                "src": row["memory_id"],
                "dst": row["other_id"],
                "kind": row["kind"],
                "reason": row["explanation"],
                "weight": 1.0,
                "origin": "finding",
            }
        )
    return edges


def _shared_entity_edges(conn: sqlite3.Connection, project_id: str) -> tuple[list[dict], int]:
    """Pairs of memories annotated with the same sufficiently rare entity.

    Returns the edges and the number of entities excluded for being too
    common, so the caller can say so out loud.
    """
    rows = conn.execute(
        "SELECT me.entity_id, me.memory_id, e.name, e.kind "
        "FROM memory_entities me "
        "JOIN memories m ON m.id = me.memory_id "
        "JOIN entities e ON e.id = me.entity_id "
        "WHERE m.project_id = ? AND m.status IN ('active','needs_review')",
        (project_id,),
    ).fetchall()

    by_entity: dict[str, list[str]] = {}
    names: dict[str, tuple[str, str]] = {}
    for r in rows:
        by_entity.setdefault(r["entity_id"], []).append(r["memory_id"])
        names[r["entity_id"]] = (r["name"], r["kind"])

    # A pair a human has already said no to must not be suggested again.
    # Without this, "dismiss" could only mean "hide until the next reload".
    rejected = link_repo.rejected_pairs(conn, project_id)

    edges: list[dict] = []
    too_common = 0
    for entity_id, members in by_entity.items():
        unique = sorted(set(members))
        if len(unique) < 2:
            continue
        if len(unique) > SPREAD_MAX:
            too_common += 1
            continue
        name, kind = names[entity_id]
        # Specificity: a pair sharing an entity seen in two memories is a much
        # stronger statement than one sharing an entity seen in eight.
        weight = 1.0 / (len(unique) - 1)
        for i, a in enumerate(unique):
            for b in unique[i + 1 :]:
                if (a, b) in rejected:
                    continue
                edges.append(
                    {
                        "src": a,
                        "dst": b,
                        "kind": "shares",
                        "reason": f"both reference {kind} {name}",
                        "weight": round(weight, 4),
                        # Not yet agreed with by anyone. The inspector offers
                        # confirm or dismiss on exactly these.
                        "origin": "suggested",
                    }
                )
    return edges, too_common


def _rank(edge: dict) -> tuple[int, float]:
    """How much a candidate edge deserves to be the one kept for a pair.

    An explicit link or a finding always beats "these mention the same
    thing"; between two shared entities, the rarer one wins.
    """
    return (0 if edge["kind"] == "shares" else 1, edge["weight"])


def build(conn: sqlite3.Connection, project_id: str) -> Graph:
    """The graph for one project, with every omission accounted for."""
    total_memories = int(
        conn.execute(
            "SELECT COUNT(*) FROM memories WHERE project_id=? "
            "AND status IN ('active','needs_review')",
            (project_id,),
        ).fetchone()[0]
    )

    explicit = _explicit_edges(conn, project_id)
    shared, too_common = _shared_entity_edges(conn, project_id)

    # Collapse duplicates, keeping the most meaningful kind for a pair: an
    # explicit link or a finding outranks "these mention the same thing".
    best: dict[tuple[str, str], dict] = {}
    for e in explicit + shared:
        if e["src"] == e["dst"]:
            continue
        key = (e["src"], e["dst"]) if e["src"] < e["dst"] else (e["dst"], e["src"])
        current = best.get(key)
        if current is None or _rank(e) > _rank(current):
            best[key] = e
    considered = len(best)

    ranked = sorted(
        best.values(),
        key=lambda e: (e["kind"] == "shares", -e["weight"]),
    )

    # Endpoints of every edge considered, before the caps below. Counting
    # from the capped list instead reported a memory whose only relationships
    # fell outside the cap as unconnected, understating a figure that sits in
    # `totals` and reads as ground truth. Narrowed to live memories further
    # down: `_explicit_edges` does not filter status, so a `supersedes` link
    # would otherwise count the absorbed record and report "2 of 1 connected".
    endpoints = {end for e in ranked for end in (e["src"], e["dst"])}

    edges = ranked[:EDGE_LIMIT]

    degree: dict[str, int] = {}
    # Memories named by a finding or an explicit link. These must survive the
    # node cap: a conflict between two claims is the most interesting thing
    # this graph can show, and it is also the *least* connected -- the two
    # memories in the one open conflict on this repository have degree 1 each,
    # so ranking nodes by degree alone quietly deleted the only edge worth
    # looking at. Found by reading the real output and noticing the kind
    # histogram said `shares` 338 and nothing else.
    flagged: set[str] = set()
    for e in edges:
        degree[e["src"]] = degree.get(e["src"], 0) + 1
        degree[e["dst"]] = degree.get(e["dst"], 0) + 1
        if e["kind"] != "shares":
            flagged.add(e["src"])
            flagged.add(e["dst"])

    # Connected memories first -- an isolated node teaches nothing about a
    # network -- then by importance, so a truncated graph keeps the records
    # that matter rather than an arbitrary slice.
    rows = conn.execute(
        "SELECT id, title, type, status, importance FROM memories "
        "WHERE project_id=? AND status IN ('active','needs_review')",
        (project_id,),
    ).fetchall()
    nodes_all = [
        {
            "id": r["id"],
            "title": r["title"],
            "type": r["type"],
            "status": r["status"],
            "importance": r["importance"],
            "degree": degree.get(r["id"], 0),
            "flagged": r["id"] in flagged,
        }
        for r in rows
    ]
    connected = sum(1 for n in nodes_all if n["id"] in endpoints)
    nodes_all.sort(key=lambda n: (not n["flagged"], -n["degree"], -(n["importance"] or 0)))
    nodes = nodes_all[:NODE_LIMIT]

    kept = {n["id"] for n in nodes}
    edges = [e for e in edges if e["src"] in kept and e["dst"] in kept]

    return Graph(
        nodes=nodes,
        edges=edges,
        totals={
            "memories": total_memories,
            "edges_considered": considered,
            "connected_memories": connected,
        },
        limits={
            "node_limit": NODE_LIMIT,
            "edge_limit": EDGE_LIMIT,
            "entity_spread_max": SPREAD_MAX,
            "omitted_memories": max(0, total_memories - len(nodes)),
            "omitted_edges": max(0, considered - len(edges)),
            "entities_too_common": too_common,
        },
    )
