"""Ranked relationship suggestions, for triage rather than exploration.

The knowledge graph can show a suggested edge, and `maintain/links.py` can
record the answer, but confirming 967 suggestions one at a time by clicking
nodes is not a workflow. This produces an ordered list with enough context
to judge a pair without opening the graph at all.

**The ranking is the feature.** The graph scores each shared entity
separately and keeps the best one per pair, so two memories sharing *three*
rare files look exactly like two sharing one. That is backwards: repeated
specific overlap is the strongest evidence available here. The score is
therefore the **sum** of the specificity of everything a pair shares, so
three rare entities outrank one, and a single very rare entity still beats
several vague ones.

Nothing here decides anything. It orders questions.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..db.repositories.graph import SPREAD_MAX
from . import links as link_repo


@dataclass
class Suggestion:
    src_id: str
    dst_id: str
    src_title: str
    dst_title: str
    src_type: str
    dst_type: str
    score: float
    shared: list[str] = field(default_factory=list)
    # Two memories with the same title that the duplicate detector did not
    # flag. Shown, not hidden: "related" is probably the wrong answer for
    # these, and the user is better served knowing that than being quietly
    # steered. Deciding for them is what this module refuses to do.
    same_title: bool = False

    def as_dict(self) -> dict:
        return {
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "src_title": self.src_title,
            "dst_title": self.dst_title,
            "src_type": self.src_type,
            "dst_type": self.dst_type,
            "score": round(self.score, 4),
            "shared": self.shared,
            "same_title": self.same_title,
        }


def ranked(conn: sqlite3.Connection, project_id: str, limit: int = 50) -> list[Suggestion]:
    """Unanswered suggestions, strongest first.

    Excludes pairs that already have a recorded link and pairs somebody has
    dismissed -- a triage list that keeps showing settled questions is a
    list nobody finishes.
    """
    rows = conn.execute(
        "SELECT me.entity_id, me.memory_id, e.name, e.kind, m.title, m.type "
        "FROM memory_entities me "
        "JOIN memories m ON m.id = me.memory_id "
        "JOIN entities e ON e.id = me.entity_id "
        "WHERE m.project_id = ? AND m.status IN ('active','needs_review')",
        (project_id,),
    ).fetchall()

    by_entity: dict[str, list[str]] = {}
    entity_label: dict[str, str] = {}
    memory: dict[str, tuple[str, str]] = {}
    for row in rows:
        by_entity.setdefault(row["entity_id"], []).append(row["memory_id"])
        entity_label[row["entity_id"]] = f"{row['kind']} {row['name']}"
        memory[row["memory_id"]] = (row["title"], row["type"])

    linked = {
        tuple(sorted((r["src_id"], r["dst_id"])))
        for r in conn.execute(
            "SELECT l.src_id, l.dst_id FROM memory_links l "
            "JOIN memories m ON m.id = l.src_id WHERE m.project_id = ?",
            (project_id,),
        )
    }
    rejected = link_repo.rejected_pairs(conn, project_id)

    # Pairs the review queue is already asking about. A pair with an open
    # duplicate or conflict finding has a better answer waiting than
    # "related": merge them, or resolve the contradiction. Listing them here
    # too would be a second queue competing for the same decision -- and the
    # ranking surfaces them first, because near-identical memories share the
    # most entities.
    in_review = {
        tuple(sorted((r["memory_id"], r["other_id"])))
        for r in conn.execute(
            "SELECT memory_id, other_id FROM findings "
            "WHERE project_id=? AND other_id IS NOT NULL AND status='open'",
            (project_id,),
        )
    }

    scores: dict[tuple[str, str], float] = {}
    shared: dict[tuple[str, str], list[str]] = {}
    for entity_id, members in by_entity.items():
        unique = sorted(set(members))
        if len(unique) < 2 or len(unique) > SPREAD_MAX:
            continue
        # Specificity: an entity in two memories says far more than one in
        # eight. Summed per pair below, so repeated overlap accumulates.
        weight = 1.0 / (len(unique) - 1)
        for i, a in enumerate(unique):
            for b in unique[i + 1 :]:
                key = (a, b)
                if key in linked or key in rejected or key in in_review:
                    continue
                scores[key] = scores.get(key, 0.0) + weight
                shared.setdefault(key, []).append(entity_label[entity_id])

    out = []
    for (a, b), score in scores.items():
        if a not in memory or b not in memory:  # pragma: no cover - defensive
            continue
        a_title, a_type = memory[a]
        b_title, b_type = memory[b]
        out.append(
            Suggestion(
                src_id=a,
                dst_id=b,
                src_title=a_title,
                dst_title=b_title,
                src_type=a_type,
                dst_type=b_type,
                score=score,
                # Most specific first, so the reason shown is the best one.
                shared=sorted(set(shared[(a, b)]))[:4],
                same_title=a_title.strip() == b_title.strip(),
            )
        )

    out.sort(key=lambda s: (-s.score, s.src_id))
    return out[:limit]


@dataclass
class BatchResult:
    confirmed: int = 0
    dismissed: int = 0
    failed: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "confirmed": self.confirmed,
            "dismissed": self.dismissed,
            "failed": self.failed,
        }


def apply_batch(
    conn: sqlite3.Connection, *, project_id: str, decisions: list[dict]
) -> BatchResult:
    """Apply several answers, reporting the ones that could not be applied.

    Each decision goes through `links.confirm` / `links.dismiss`, so every
    guard they enforce still holds -- a batch is a convenience for a human
    answering many questions, not a side door around the rules.

    One bad decision does not discard the rest. A batch of forty where three
    refer to a memory somebody archived meanwhile should apply thirty-seven
    and say which three it could not, rather than failing wholesale and
    making the user find them.
    """
    result = BatchResult()
    for decision in decisions:
        src = decision.get("src_id")
        dst = decision.get("dst_id")
        verdict = decision.get("verdict")
        try:
            if verdict == "confirm":
                link_repo.confirm(
                    conn,
                    project_id=project_id,
                    src_id=src,
                    dst_id=dst,
                    kind=decision.get("kind") or "relates_to",
                )
                result.confirmed += 1
            elif verdict == "dismiss":
                link_repo.dismiss(conn, project_id=project_id, src_id=src, dst_id=dst)
                result.dismissed += 1
            else:
                raise ValueError(f"unknown verdict: {verdict!r}")
        except ValueError as exc:
            result.failed.append({"src_id": src, "dst_id": dst, "error": str(exc)})
    return result
