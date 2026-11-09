"""Kernote's MCP surface: four read-only tools (ADR-0008).

Read-only is the whole design. There is no write tool in any form, so an agent
can consume the vault but cannot corrupt it — `CLAUDE.md` requires human
approval for canonical writes, and an agent writing unreviewed records is
exactly the "silent" path it forbids. If agent-proposed memories are wanted
later they arrive as `findings` for review, which is a new ADR, not a loosening
of this one.

This is a second *adapter* over the same core as the HTTP API: it calls the
same retrieval, bundle and repository functions, so the two can never disagree
about what the project knows.

Run it as the project's agent integration:

    KERNOTE_PROJECT=<id-or-path> python -m kernote.mcp.server
"""

from __future__ import annotations

import contextlib
import os
import re
import sqlite3
import sys
from pathlib import Path

import structlog

from ..apply import context_bundle
from ..config import settings
from ..db.connection import open_db
from ..db.repositories import memories as mrepo
from ..db.repositories import projects as prepo
from ..domain.models import MemoryType
from ..logging import configure_logging
from ..retrieval import answer as answer_mod
from ..retrieval.answer import _STOPWORDS

log = structlog.get_logger(__name__)

SERVER_NAME = "kernote"

MEMORY_TYPES = tuple(t.value for t in MemoryType)


def _mentions(haystack: str, subject: str) -> bool:
    """Whole-word containment, the way Stage 3 learned to do it.

    Plain `in` made `"it"` match "SQLite" and `"a"` match everything — the same
    defect as `"adr"` matching "Quadratic" in the ADR extractor. Word
    boundaries fix that; a trailing `s?` keeps plurals matching, and a
    multi-word subject is matched as a phrase.
    """
    return re.search(rf"\b{re.escape(subject)}s?\b", haystack, re.I) is not None


class ProjectNotConfigured(RuntimeError):
    pass


def _resolve_project(conn: sqlite3.Connection, hint: str | None) -> str:
    """The project this server serves.

    `KERNOTE_PROJECT` takes an id or a filesystem path. With exactly one
    project registered it is optional; with several it is required, because
    silently picking one would serve an agent another project's knowledge.
    """
    projects = prepo.list_all(conn)
    if hint:
        for project in projects:
            if project.id == hint:
                return project.id
        resolved = str(Path(hint).expanduser().resolve())
        for project in projects:
            if project.root_path == resolved:
                return project.id
        raise ProjectNotConfigured(f"no registered project matches {hint!r}")
    if len(projects) == 1:
        return projects[0].id
    if not projects:
        raise ProjectNotConfigured(
            "no projects registered; add one in Kernote before starting the MCP server"
        )
    raise ProjectNotConfigured(
        "several projects are registered; set KERNOTE_PROJECT to an id or path"
    )


def build_server(conn: sqlite3.Connection, project_id: str):
    """Register the tools. Separated from `main()` so tests can drive it."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(SERVER_NAME)

    @server.tool()
    def kernote_search_memory(
        query: str, memory_type: str | None = None, limit: int = 8
    ) -> dict:
        """Search this project's reviewed memory and return cited evidence.

        Returns records with the file and line range each claim came from, and
        says plainly when nothing supports the question rather than guessing.
        Each item is labelled `evidence` (quoted from source) or `inference`
        (derived), so you can weigh them differently.

        `memory_type` filters to one of: project_fact, architecture, decision,
        procedure, convention, gotcha, current_state.
        """
        if memory_type is not None and memory_type not in MEMORY_TYPES:
            return {
                "outcome": "invalid_request",
                "statement": (
                    f"{memory_type!r} is not a memory type. Use one of: "
                    + ", ".join(MEMORY_TYPES)
                ),
                "evidence": [],
                "not_supported_by_any_source": [],
            }
        bundle = answer_mod.ask(
            conn,
            project_id=project_id,
            question=query,
            # Over-fetch when filtering by type, or the filter can empty a
            # result set that had matches further down.
            limit=max(1, min(limit * 3 if memory_type else limit, 40)),
        )
        items = []
        for item in bundle.evidence:
            # The type lives on the memory, not on the evidence item, so it is
            # looked up rather than inferred from the title.
            actual_type = None
            if item.source == "memory":
                row = conn.execute(
                    "SELECT type FROM memories WHERE id=?", (item.target_id,)
                ).fetchone()
                actual_type = row["type"] if row else None
            if memory_type and actual_type != memory_type:
                continue
            items.append(
                {
                    "kind": item.kind,
                    "memory_type": actual_type,
                    "title": item.title,
                    "citation": item.citation,
                    "excerpt": item.excerpt,
                    "matched_terms": item.matched_terms,
                    "confidence": item.confidence,
                }
            )
        items = items[: max(1, min(limit, 20))]
        outcome, statement = bundle.outcome, bundle.statement
        if memory_type and not items:
            # The composed statement counts what retrieval found, which is a
            # lie once the type filter has emptied the list: an agent must not
            # read "19 supporting records" beside zero records.
            outcome = "evidence_not_found"
            statement = (
                f"Records matched {query!r}, but none of them are of type "
                f"{memory_type!r}. Evidence was not found for that type — this "
                "is not the same as there being none in the project."
            )
        return {
            "outcome": outcome,
            "statement": statement,
            "evidence": items,
            "not_supported_by_any_source": bundle.unknowns,
        }

    @server.tool()
    def kernote_project_summary() -> dict:
        """Orient yourself in this project: stack, layout, key decisions, state.

        Drawn from reviewed memory, not generated. Every item carries a
        citation.
        """
        project = prepo.get(conn, project_id)
        counts = prepo.counts(conn, project_id)

        def top(memory_type: str, limit: int = 6) -> list[dict]:
            return [
                {
                    "title": memory.title,
                    "summary": (memory.summary or memory.content)[:300],
                    "citation": (
                        memory.source_refs[0].citation if memory.source_refs else "none"
                    ),
                    "claim": memory.claim_kind.value,
                }
                for memory in mrepo.list_for_project(
                    conn, project_id, type_=memory_type, limit=limit
                )
            ]

        return {
            "project": project.name if project else "unknown",
            "root_path": project.root_path if project else None,
            "is_git_repo": project.is_git_repo if project else False,
            "counts": counts,
            "project_facts": top("project_fact"),
            "architecture": top("architecture"),
            "decisions": top("decision"),
            "procedures": top("procedure"),
            "current_state": top("current_state", 4),
            "gotchas": top("gotcha", 4),
            "note": (
                "Superseded and archived records are excluded, so nothing here "
                "has been replaced by a newer claim."
            ),
        }

    @server.tool()
    def kernote_get_decision(subject: str) -> dict:
        """Find why a decision was made: the option chosen, what was rejected,
        its status and date, and the source it came from.

        If the document did not state the chosen option in a parseable form,
        `chosen` is absent rather than guessed — Kernote never invents a
        rationale.
        """
        needle = subject.strip()
        if needle.lower() in _STOPWORDS:
            # "a" and "it" are whole words in nearly every decision document,
            # so they match everything and mean nothing. Short subjects that
            # carry meaning — ML, UI, DB, Go — are not stopwords, so length is
            # the wrong filter here.
            return {
                "found": False,
                "statement": (
                    f"{subject!r} is too common a word to search decisions by. "
                    "Name a technology, component or constraint."
                ),
                "decisions": [],
            }
        if not needle:
            # An empty subject used to fall through the filter and return ten
            # arbitrary decisions as though they matched.
            return {
                "found": False,
                "statement": (
                    "No subject given. Name what the decision is about — a "
                    "technology, a component or a constraint."
                ),
                "decisions": [],
            }
        decisions = mrepo.list_for_project(conn, project_id, type_="decision", limit=200)
        matches = []
        for memory in decisions:
            payload = memory.decision or {}
            haystack = " ".join(
                [
                    memory.title,
                    memory.summary or "",
                    str(payload.get("chosen") or ""),
                    " ".join(str(a) for a in payload.get("alternatives", []) or []),
                ]
            )
            if not _mentions(haystack, needle):
                continue
            matches.append(
                {
                    "title": memory.title,
                    "chosen": payload.get("chosen"),
                    "alternatives": payload.get("alternatives", []),
                    "status": payload.get("status"),
                    "decided_on": payload.get("decided_on"),
                    "valid_from": memory.valid_from,
                    "superseded": memory.superseded_by is not None,
                    "citation": (
                        memory.source_refs[0].citation if memory.source_refs else "none"
                    ),
                    "body": memory.content[:800],
                }
            )
        if not matches:
            return {
                "found": False,
                "statement": (
                    f"No decision record mentions {subject!r}. Evidence was not "
                    "found — this is not the same as there being no decision."
                ),
                "decisions": [],
            }
        return {
            "found": True,
            "statement": f"{len(matches)} decision(s) match.",
            "decisions": matches[:10],
        }

    @server.tool()
    def kernote_build_context(task: str | None = None, token_budget: int = 4000) -> dict:
        """Package approved project memory for a task, inside a token budget.

        The bundle states its token estimate and lists what it dropped, so a
        truncated context is visible rather than silent. Pass a `task` to rank
        by relevance; omit it for the project's most important memory.
        """
        result = context_bundle.build(
            conn,
            project_id=project_id,
            task=task,
            token_budget=max(200, min(token_budget, 32000)),
        )
        return {
            "markdown": result.markdown,
            "token_budget": result.token_budget,
            "tokens_used": result.tokens_used,
            "included": len(result.included),
            "dropped": [entry.title for entry in result.dropped[:40]],
            "note": result.note,
        }

    return server


def tool_manifest(conn: sqlite3.Connection, project_id: str) -> list[dict[str, str]]:
    """The tools this server really advertises, name and one-line purpose.

    The Agent Integrations screen used to carry its own hand-written copy of
    this list, which would quietly start lying the moment a tool was renamed —
    two sources of truth for the same fact, in a product built to catch exactly
    that. It is derived from the live registry instead.
    """
    tools = build_server(conn, project_id)._tool_manager.list_tools()
    manifest = []
    for tool in tools:
        first = (tool.description or "").strip().split("\n\n")[0]
        manifest.append({"name": tool.name, "description": " ".join(first.split())})
    return sorted(manifest, key=lambda t: t["name"])


def _force_utf8_stdio() -> None:
    """JSON-RPC over stdio is UTF-8; the locale does not get a vote.

    On Windows `sys.stdout` defaults to the *locale* encoding -- cp1252 on the
    machine this was found on. The first tool response containing an em-dash
    was therefore written as cp1252 and the client, decoding UTF-8, died with
    `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97`. Our own memory
    content is full of em-dashes, so the agent surface was effectively unusable
    on Windows for any real project (ADR-0009a).

    `reconfigure` is guarded because under pytest's capture these streams are
    not always `TextIOWrapper`.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8", newline="")


def main() -> None:
    # Both must come before anything that might log or write: on stdio, stdout
    # is the JSON-RPC transport -- one stray log line hangs the client, and one
    # mis-encoded byte kills it.
    _force_utf8_stdio()
    configure_logging()
    conn = open_db(settings.db_path)
    project_id = _resolve_project(conn, os.environ.get("KERNOTE_PROJECT"))
    project = prepo.get(conn, project_id)
    log.info(
        "mcp.start",
        project=project.name if project else project_id,
        db=str(settings.db_path),
        tools=4,
        writable=False,
    )
    build_server(conn, project_id).run()


if __name__ == "__main__":
    main()
