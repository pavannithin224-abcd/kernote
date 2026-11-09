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

The reported figure is measured from the **finished document**, not summed from
its parts. Estimating the parts and reserving a guess for the header was wrong
by up to 4x once the "did not fit" list grew, which made the one number the
caller relies on the least trustworthy thing in the bundle.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import structlog

from ..domain.models import MemoryType
from ..retrieval import hybrid

log = structlog.get_logger(__name__)

CHARS_PER_TOKEN = 4

# How many dropped titles to list, tried in order. Listing what did not fit is
# the point, but the list itself costs tokens, so a tight budget lists fewer
# rather than overrunning. It never reaches zero: naming nothing would trade
# one dishonesty for another, and four titles plus a count still tells the
# reader what kind of thing is missing.
_DROPPED_LIST_STEPS = (40, 12, 4)

# A fixed-width placeholder so the document can be measured before the measured
# figure is written into it. Substituting the real number changes the length by
# at most a few characters, under one token.
_USED_SLOT = "######"

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
    not_considered: int = 0
    over_budget: bool = False
    note: str | None = None

    @property
    def excluded_total(self) -> int:
        """Every current memory that did not make it in — listed or not."""
        return len(self.dropped) + self.not_considered

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


def _current_total(conn: sqlite3.Connection, project_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS c FROM memories WHERE project_id=? "
        "AND status NOT IN ('superseded','archived')",
        (project_id,),
    ).fetchone()["c"]


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
        if len(body) > 1200:
            body = body[:1200].rstrip() + " […truncated]"
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

    # Memories past `max_candidates` were never weighed against the budget.
    # They are counted so the bundle can say so: claiming "113 did not fit"
    # while 260 more were never looked at is the kind of confident wrong number
    # this product exists to prevent.
    not_considered = max(0, _current_total(conn, project_id) - len(rows))

    included, dropped, markdown, used, shown = _fit(
        project["name"], project["root_path"], task, entries, token_budget, not_considered
    )

    over_budget = used > token_budget
    note = None
    if dropped or not_considered:
        total = len(dropped) + not_considered
        listed = min(len(dropped), shown)
        note = f"{total} current memory(ies) are not in this bundle"
        if listed:
            note += f"; {listed} listed by title at the end"
        if not_considered:
            note += (
                f"; {not_considered} ranked below the top {max_candidates} and were "
                "not weighed against the budget"
            )
        note += "."
    if over_budget:
        note = (
            f"This bundle is ~{used} tokens, over the {token_budget} requested: "
            "the header and the list of what did not fit cannot be made smaller. "
            "Raise the budget."
        ) + (f" {note}" if note else "")

    log.info(
        "bundle.built",
        project_id=project_id,
        task=bool(task),
        included=len(included),
        dropped=len(dropped),
        not_considered=not_considered,
        tokens=used,
        budget=token_budget,
        over_budget=over_budget,
    )
    return BundleResult(
        project_name=project["name"],
        task=task,
        token_budget=token_budget,
        tokens_used=used,
        markdown=markdown,
        included=included,
        dropped=dropped,
        not_considered=not_considered,
        over_budget=over_budget,
        note=note,
    )


def _fit(
    name: str,
    root: str,
    task: str | None,
    entries: list[BundleEntry],
    token_budget: int,
    not_considered: int,
) -> tuple[list[BundleEntry], list[BundleEntry], str, int, int]:
    """Choose what fits by measuring the rendered document.

    Packing by summing per-entry estimates and reserving a guess for the header
    was wrong by up to 4x, because the "did not fit" list grows as the budget
    shrinks — the tighter the budget, the more the footer cost, which the sum
    never saw. So the document is rendered and measured, and entries come out
    until the whole thing fits.

    The list of what did not fit competes with the memory itself for the same
    budget, and **content wins**: a bundle listing 78 titles it could not
    include and no actual memory is useless. So each listing length is costed
    and the pair that carries the most memory is chosen, preferring the longer
    listing only on a tie.

    Returns the chosen entries, what was dropped, the document, its measured
    token count and how many dropped titles that document lists.
    """

    def measure(take: int, shown: int) -> int:
        return estimate_tokens(
            _render(
                name,
                root,
                task,
                entries[:take],
                entries[take:],
                token_budget,
                _USED_SLOT,
                shown,
                not_considered,
            )
        )

    # A cheap upper bound from the per-entry estimates keeps the measured
    # search short on a large vault.
    ceiling = 0
    running = 0
    for entry in entries:
        if running + entry.tokens > token_budget:
            break
        running += entry.tokens
        ceiling += 1

    best = (-1, -1)  # (entries carried, titles listed)
    for shown in _DROPPED_LIST_STEPS:
        take = ceiling
        while take > 0 and measure(take, shown) > token_budget:
            take -= 1
        if (take, shown) > best:
            best = (take, shown)
    take, shown = best
    if take <= 0:
        # Not even one memory fits. Produce the smallest honest document there
        # is — the shortest listing — and report the overrun rather than
        # pretending the document is smaller than it is.
        take, shown = 0, 0

    included, dropped = entries[:take], entries[take:]
    used = measure(take, shown)
    # Writing the measured figure in place of the fixed-width placeholder
    # changes the document's own length, so settle on a figure that describes
    # the document actually returned.
    for _ in range(4):
        markdown = _render(
            name,
            root,
            task,
            included,
            dropped,
            token_budget,
            str(used),
            shown,
            not_considered,
        )
        settled = estimate_tokens(markdown)
        if settled == used:
            break
        used = settled
    return included, dropped, markdown, used, shown


def _render(
    name: str,
    root: str,
    task: str | None,
    included: list[BundleEntry],
    dropped: list[BundleEntry],
    budget: int,
    used_label: str,
    dropped_shown: int,
    not_considered: int,
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
        f"**Budget:** ~{used_label} of {budget} tokens (estimated at "
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

    if dropped or not_considered:
        total = len(dropped) + not_considered
        lines += [
            f"## Not included ({total})",
            "",
            "These exist in current project memory but are not above. Raise the "
            "budget or narrow the task to include them:",
            "",
        ]
        listed = dropped[:dropped_shown] if dropped_shown else []
        lines += [f"- {entry.title} — `{entry.citation}`" for entry in listed]
        rest = total - len(listed)
        if rest:
            lines.append(
                f"- …and {rest} more, not listed here"
                + (
                    " (the list was shortened to stay inside the budget)"
                    if dropped_shown < len(dropped)
                    else ""
                )
            )
        lines.append("")

    if not included:
        total_excluded = len(dropped) + not_considered
        if total_excluded:
            # Saying "no memory matches" when 380 records matched and none fit
            # would blame the vault for a budget problem.
            lines += [
                "## Nothing fitted the budget",
                "",
                f"This project has {total_excluded} current memory(ies), but the "
                f"budget of {budget} tokens does not leave room for even one of "
                "them alongside this header. Raise the budget.",
                "",
            ]
        else:
            lines += [
                "## No memory available",
                "",
                "This project has no current memories matching the request. "
                "Scan the repository first, or widen the task.",
                "",
            ]
    return "\n".join(lines)
