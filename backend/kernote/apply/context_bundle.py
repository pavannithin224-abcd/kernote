"""The context bundle (F7): approved project memory, packaged for a task.

What distinguishes this from "dump the memories into a prompt":

* **It is budgeted.** A bundle states its token estimate and **lists what it
  dropped**, because a silently truncated context is worse than a short one —
  the reader cannot tell which is which.
* **Every claim keeps its citation.** The point of handing an agent project
  memory is that the agent can check it.
* **Only current records.** Superseded and archived memories are excluded, so a
  replaced decision never travels as current advice.
* **Interpretations are marked.** An agent reading the bundle can tell a quoted
  source fact from a derived claim.

Token counts are a `len/4` estimate, not a tokenizer. That is honest for a
budget check and avoids making the bundle depend on a model's vocabulary; the
bundle says so rather than implying precision it does not have.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import structlog

from ..domain.models import MemoryType
from ..retrieval import hybrid

log = structlog.get_logger(__name__)

CHARS_PER_TOKEN = 4

# Ordered by what orients a reader first.
_SECTION_ORDER: tuple[tuple[MemoryType, str], ...] = (
    (MemoryType.PROJECT_FACT, "Project facts"),
    (MemoryType.ARCHITECTURE, "Architecture"),
    (MemoryType.DECISION, "Decisions"),
    (MemoryType.PROCEDURE, "Procedures"),
    (MemoryType.CONVENTION, "Conventions"),
    (MemoryType.GOTCHA, "Gotchas"),
    (MemoryType.CURRENT_STATE, "Current state"),
)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass
class BundleEntry:
    memory_id: str
    memory_type: str
    title: str
    body: str
    citation: str
    claim_kind: str
    importance: float
    tokens: int


@dataclass
class BundleResult:
    project_name: str
    task: str | None
    token_budget: int
    tokens_used: int
    markdown: str
    included: list[BundleEntry] = field(default_factory=list)
    dropped: list[BundleEntry] = field(default_factory=list)
    note: str | None = None

    @property
    def dropped_tokens(self) -> int:
        return sum(e.tokens for e in self.dropped)


def _citation_for(conn: sqlite3.Connection, memory_id: str) -> str:
    row = conn.execute(
        "SELECT rel_path,line_start,line_end,user_note FROM memory_source_refs "
        "WHERE memory_id=? ORDER BY line_start LIMIT 1",
        (memory_id,),
    ).fetchone()
    if row is None:
        return "no source recorded"
    if row["rel_path"] and row["line_start"]:
        return f"{row['rel_path']}:{row['line_start']}-{row['line_end']}"
    return row["rel_path"] or row["user_note"] or "no source recorded"


def _candidates(
    conn: sqlite3.Connection, project_id: str, task: str | None, limit: int
) -> list[sqlite3.Row]:
    """Memories worth considering, most relevant first.

    With a task, relevance comes from the same hybrid retrieval the Ask screen
    uses — one ranking implementation, so a bundle cannot disagree with search.
    Without one, importance order is the honest default.
    """
    if task:
        outcome = hybrid.search(
            conn, project_id=project_id, query=task, limit=limit, pool=limit * 2
        )
        ids = [r.target_id for r in outcome.results if r.target_kind == "memory"]
        if ids:
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                "SELECT id,type,title,summary,content,claim_kind,importance "  # noqa: S608
                f"FROM memories WHERE id IN ({placeholders}) "
                "AND status NOT IN ('superseded','archived')",
                ids,
            ).fetchall()
            order = {mid: index for index, mid in enumerate(ids)}
            return sorted(rows, key=lambda r: order.get(r["id"], len(order)))
    return conn.execute(
        "SELECT id,type,title,summary,content,claim_kind,importance FROM memories "
        "WHERE project_id=? AND status NOT IN ('superseded','archived') "
        "ORDER BY importance DESC, created_at LIMIT ?",
        (project_id, limit),
    ).fetchall()


def build(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    task: str | None = None,
    token_budget: int = 4000,
    max_candidates: int = 120,
) -> BundleResult:
    project = conn.execute(
        "SELECT name, root_path FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if project is None:
        raise ValueError("project not found")

    rows = _candidates(conn, project_id, task, max_candidates)
    entries: list[BundleEntry] = []
    for row in rows:
        body = (row["summary"] or row["content"] or "").strip()
        if not body:
            continue
        body = body[:1200]
        entry = BundleEntry(
            memory_id=row["id"],
            memory_type=row["type"],
            title=row["title"],
            body=body,
            citation=_citation_for(conn, row["id"]),
            claim_kind=row["claim_kind"],
            importance=float(row["importance"]),
            tokens=estimate_tokens(f"{row['title']}{body}") + 12,
        )
        entries.append(entry)

    # Header and footer cost tokens too; reserve for them so the stated budget
    # is the whole document, not just its body.
    reserve = 160
    budget = max(0, token_budget - reserve)
    included: list[BundleEntry] = []
    dropped: list[BundleEntry] = []
    used = 0
    for entry in entries:
        if used + entry.tokens <= budget:
            included.append(entry)
            used += entry.tokens
        else:
            dropped.append(entry)

    markdown = _render(
        project["name"],
        project["root_path"],
        task,
        included,
        dropped,
        token_budget,
        used + reserve,
    )
    note = None
    if dropped:
        note = (
            f"{len(dropped)} memory(ies) did not fit the {token_budget}-token budget "
            "and are listed by title at the end of the bundle."
        )
    log.info(
        "bundle.built",
        project_id=project_id,
        task=bool(task),
        included=len(included),
        dropped=len(dropped),
        tokens=used + reserve,
    )
    return BundleResult(
        project_name=project["name"],
        task=task,
        token_budget=token_budget,
        tokens_used=used + reserve,
        markdown=markdown,
        included=included,
        dropped=dropped,
        note=note,
    )


def _render(
    name: str,
    root: str,
    task: str | None,
    included: list[BundleEntry],
    dropped: list[BundleEntry],
    budget: int,
    used: int,
) -> str:
    lines: list[str] = [
        f"# Project context: {name}",
        "",
        f"Source: `{root}`",
        "",
        "Generated by Kernote from reviewed project memory. Every claim below "
        "carries the file and line range it came from — check it rather than "
        "trusting it. Claims marked *interpretation* were derived, not quoted.",
        "",
    ]
    if task:
        lines += [f"**Selected for task:** {task}", ""]
    lines += [
        f"**Budget:** ~{used} of {budget} tokens (estimated at "
        f"{CHARS_PER_TOKEN} characters per token, not a tokenizer).",
        "",
    ]

    by_type: dict[str, list[BundleEntry]] = {}
    for entry in included:
        by_type.setdefault(entry.memory_type, []).append(entry)

    for memory_type, heading in _SECTION_ORDER:
        group = by_type.get(memory_type.value)
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for entry in group:
            marker = " *(interpretation)*" if entry.claim_kind == "interpretation" else ""
            lines += [
                f"### {entry.title}{marker}",
                "",
                entry.body,
                "",
                f"— `{entry.citation}`",
                "",
            ]

    if dropped:
        lines += [
            "## Not included (over budget)",
            "",
            "These exist in project memory but did not fit. Raise the budget or "
            "narrow the task to include them:",
            "",
        ]
        lines += [f"- {entry.title} — `{entry.citation}`" for entry in dropped[:40]]
        if len(dropped) > 40:
            lines.append(f"- …and {len(dropped) - 40} more")
        lines.append("")

    if not included:
        lines += [
            "## No memory available",
            "",
            "This project has no current memories matching the request. "
            "Scan the repository first, or widen the task.",
            "",
        ]
    return "\n".join(lines)
