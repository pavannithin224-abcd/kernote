"""Entity derivation and linking (L3).

`entities` and `memory_entities` were created in migration 0001 and never
written to. They are what make two other features possible:

* **Duplicate candidates** -- two memories about the same file, dependency or
  command are worth comparing; two unrelated memories are not, and comparing
  every pair is O(n^2) on hundreds of records.
* **Importance fan-in** -- a module many memories refer to matters more than
  one nothing refers to.

Derivation is deterministic and comes from data already extracted: the source
ref's path, the manifest's package names, the first word of a command. Nothing
is inferred by a model.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import PurePosixPath

from ..domain.models import Memory, MemoryType, new_id

# A shell line's command is its first bare word, skipping env assignments and
# `sudo`. `VAR=1 sudo npm run build` -> `npm`.
_ENV_ASSIGN = re.compile(r"^[A-Z_][A-Z0-9_]*=")
_SKIP_WORDS = {"sudo", "env", "exec", "time", "nohup"}
# Fence markers are not commands, belt-and-braces alongside the extractor gate.
_FENCE = re.compile(r"^\s*(?:```|~~~)")
# Package names from a requirements/dependency line: `fastapi>=0.110` -> fastapi
_PACKAGE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,80})")


def _command_of(line: str) -> str | None:
    if _FENCE.match(line):
        return None
    for token in line.strip().split():
        if _ENV_ASSIGN.match(token) or token in _SKIP_WORDS:
            continue
        if token.startswith("-"):
            return None
        return token
    return None


def derive(memory: Memory) -> list[tuple[str, str]]:
    """(kind, name) pairs for a memory. Deterministic, order-stable."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, name: str) -> None:
        name = name.strip()
        if not name or len(name) > 120:
            return
        key = (kind, name)
        if key not in seen:
            seen.add(key)
            out.append(key)

    for ref in memory.source_refs:
        if not ref.rel_path:
            continue
        add("file", ref.rel_path)
        path = PurePosixPath(ref.rel_path)
        # The module is the directory a file lives in: the unit memories
        # cluster around.
        if str(path.parent) not in (".", ""):
            add("module", str(path.parent))

    # Only the command extractor produces an actual command list. A
    # section-derived procedure memory contains prose and fence markers, and
    # deriving commands from it yielded entities called "```" and "```bash".
    if memory.type is MemoryType.PROCEDURE and memory.extraction_method in (
        "rule:markdown_commands",
        "manual",
    ):
        for line in memory.content.splitlines():
            command = _command_of(line)
            if command:
                add("command", command)

    if memory.extraction_method == "rule:manifests" and "dependencies" in (
        memory.title.lower()
    ):
        for line in memory.content.splitlines():
            match = _PACKAGE.match(line.strip())
            if match:
                add("dependency", match.group(1))

    if memory.type is MemoryType.DECISION and memory.decision:
        chosen = memory.decision.get("chosen")
        if isinstance(chosen, str):
            add("decision", chosen)
        for alternative in memory.decision.get("alternatives", []) or []:
            if isinstance(alternative, str):
                add("decision", alternative)

    return out


def link(conn: sqlite3.Connection, project_id: str, memory: Memory) -> int:
    """Upsert a memory's entities and its links to them. Returns link count."""
    pairs = derive(memory)
    for kind, name in pairs:
        row = conn.execute(
            "SELECT id FROM entities WHERE project_id=? AND kind=? AND name=?",
            (project_id, kind, name),
        ).fetchone()
        if row is None:
            entity_id = new_id()
            conn.execute(
                "INSERT INTO entities(id,project_id,kind,name) VALUES(?,?,?,?)",
                (entity_id, project_id, kind, name),
            )
        else:
            entity_id = row["id"]
        conn.execute(
            "INSERT OR IGNORE INTO memory_entities(memory_id,entity_id,role) " "VALUES(?,?,?)",
            (memory.id, entity_id, kind),
        )
    return len(pairs)


def fan_in(conn: sqlite3.Connection, project_id: str) -> dict[str, int]:
    """entity_id -> how many memories reference it.

    This is the raw signal behind importance fan-in. A PageRank over the symbol
    graph (ADR-0012a, the Aider approach) is the refinement; a reference count
    is the honest first version, and it is explainable in one sentence, which
    importance scoring requires.
    """
    rows = conn.execute(
        "SELECT e.id, COUNT(DISTINCT me.memory_id) AS n "
        "FROM entities e JOIN memory_entities me ON me.entity_id = e.id "
        "WHERE e.project_id=? GROUP BY e.id",
        (project_id,),
    ).fetchall()
    return {r["id"]: int(r["n"]) for r in rows}
