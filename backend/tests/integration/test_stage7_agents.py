"""Stage 7: context bundles and the read-only MCP surface.

The MCP tests drive a real server over stdio rather than calling the tool
functions directly. That distinction matters: calling the functions would never
have revealed that logging to stdout corrupts the JSON-RPC stream, which is the
bug this stage actually had.
"""

import asyncio
import json
import os
import sys

import pytest

from kernote.apply import context_bundle
from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project

DOCS = {
    "README.md": """# Widgetly

## Architecture

The render package turns widget definitions into SVG and must stay free of
database imports.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```
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


def _project(conn, tmp_path):
    for name, text in DOCS.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    project = prepo.create(conn, Project(name="Widgetly", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=100
    )
    return project


# ===================== the bundle =====================


def test_bundle_cites_every_claim(conn, tmp_path):
    project = _project(conn, tmp_path)
    result = context_bundle.build(conn, project_id=project.id, token_budget=4000)
    assert result.included
    for entry in result.included:
        assert entry.citation and entry.citation != "no source recorded"
        assert f"`{entry.citation}`" in result.markdown


def test_bundle_respects_its_budget_and_says_what_it_dropped(conn, tmp_path):
    """A silently truncated context is worse than a short one: the reader
    cannot tell which they have.

    Needs a corpus larger than the budget: the two-document fixture is only
    ~277 tokens, so no budget would ever drop anything and the test would pass
    without exercising the code.
    """
    for index in range(25):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\n## Subsystem {index}\n\n"
            f"Subsystem {index} handles a distinct concern and is described at "
            f"length here so the entry costs a meaningful number of tokens.\n",
            encoding="utf-8",
        )
    project = _project(conn, tmp_path)
    big = context_bundle.build(conn, project_id=project.id, token_budget=8000)
    small = context_bundle.build(conn, project_id=project.id, token_budget=400)

    assert small.tokens_used <= 400
    assert len(small.included) < len(big.included)
    assert small.dropped, "a tight budget dropped nothing"
    assert not small.over_budget
    assert small.note and str(len(small.dropped)) in small.note
    assert "Not included" in small.markdown
    # Dropped entries are named, not merely counted.
    assert small.dropped[0].title in small.markdown


@pytest.mark.parametrize("budget", [200, 400, 700, 1500, 8000])
def test_bundle_token_count_describes_the_whole_document(conn, tmp_path, budget):
    """The stated figure must measure the document returned, not its parts.

    Summing per-entry estimates and reserving a guess for the header was wrong
    by up to 4x: the list of what did not fit *grows* as the budget shrinks, so
    the tighter the budget, the larger the unmeasured footer. A bundle asked
    for 200 tokens came back at 792 and said 187.
    """
    for index in range(40):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\n## Subsystem {index}\n\nSubsystem {index} "
            "handles a distinct concern, described at length so the entry "
            "costs a meaningful number of tokens rather than a handful.\n",
            encoding="utf-8",
        )
    project = _project(conn, tmp_path)
    result = context_bundle.build(conn, project_id=project.id, token_budget=budget)

    assert result.tokens_used == context_bundle.estimate_tokens(result.markdown)
    if result.over_budget:
        # Allowed only when even the smallest honest document overruns, and it
        # must say so rather than understating itself.
        assert not result.included
        assert result.note and "over the" in result.note
    else:
        assert result.tokens_used <= budget


def test_bundle_counts_memories_it_never_weighed(conn, tmp_path):
    """Claiming "113 did not fit" while 260 more were never looked at is the
    kind of confident wrong number this product exists to prevent."""
    for index in range(30):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\nSubsystem {index} is described here.\n", encoding="utf-8"
        )
    project = _project(conn, tmp_path)
    total = context_bundle._current_total(conn, project.id)
    result = context_bundle.build(
        conn, project_id=project.id, token_budget=600, max_candidates=5
    )

    assert result.not_considered > 0, "the cut-off left nothing out; raise the corpus"
    assert len(result.included) + result.excluded_total == total
    assert str(result.excluded_total) in result.markdown
    assert "not weighed against the budget" in (result.note or "")


def test_bundle_blames_the_budget_not_the_vault(conn, tmp_path):
    """ "No memory matches" is false when records matched and none fitted."""
    for index in range(12):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\nSubsystem {index} is described at some length "
            "here, long enough that it cannot fit a minimal budget.\n",
            encoding="utf-8",
        )
    project = _project(conn, tmp_path)
    # Below the header's own cost, so nothing can fit however small the entry.
    result = context_bundle.build(conn, project_id=project.id, token_budget=120)

    assert not result.included
    assert "Nothing fitted the budget" in result.markdown
    assert "No memory available" not in result.markdown


def test_bundle_marks_a_truncated_body(conn, tmp_path):
    """A body cut at the per-entry cap must say it was cut.

    Driven through a stored memory rather than a scanned file: extraction fills
    `summary`, which the bundle prefers, and a summary is never long enough to
    reach the cap — so a file fixture would assert nothing.
    """
    from kernote.db.repositories import memories as repo
    from kernote.domain.models import Memory, SourceRef

    project = _project(conn, tmp_path)
    repo.create(
        conn,
        Memory(
            project_id=project.id,
            type="gotcha",
            title="A very long gotcha",
            content="This sentence is repeated to exceed the per-entry cap. " * 40,
            summary=None,
            claim_kind="source_fact",
            importance=0.99,
            importance_reason="fixture",
            confidence=0.9,
            confidence_reason="fixture",
            extraction_method="manual",
            source_refs=[SourceRef(rel_path="LONG.md", user_note="fixture")],
        ),
    )
    result = context_bundle.build(conn, project_id=project.id, token_budget=8000)
    cut = [e for e in result.included if e.body.endswith("[…truncated]")]
    assert cut, "nothing was long enough to truncate"
    assert len(cut[0].body) < 1300


def test_bundle_excludes_superseded_memories(conn, tmp_path):
    """A replaced decision must never travel as current advice."""
    project = _project(conn, tmp_path)
    target = mrepo.list_for_project(conn, project.id, limit=50)[0]
    from kernote.domain.models import Memory

    replacement = Memory(
        **{
            **target.model_dump(),
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Replaced claim",
            "superseded_by": None,
            "supersedes": None,
        }
    )
    mrepo.supersede(conn, target.id, replacement, reason="moved on")

    result = context_bundle.build(conn, project_id=project.id, token_budget=8000)
    assert target.id not in {entry.memory_id for entry in result.included}
    # Assert on the body, not the title: generic titles like "Architecture"
    # also appear as section headings in the rendered bundle.
    distinctive = target.content.split()[:6]
    if len(distinctive) >= 4:
        assert " ".join(distinctive) not in result.markdown


def test_bundle_marks_interpretations(conn, tmp_path):
    from kernote.domain.models import ClaimKind, Memory, MemoryType, SourceRef

    project = _project(conn, tmp_path)
    mrepo.create(
        conn,
        Memory(
            project_id=project.id,
            type=MemoryType.ARCHITECTURE,
            title="Rendering probably bottlenecks on string assembly",
            content="Rendering probably bottlenecks on SVG string assembly.",
            claim_kind=ClaimKind.INTERPRETATION,
            importance=0.95,
            importance_reason="high so it lands in the bundle",
            confidence=0.4,
            confidence_reason="derived, not quoted",
            extraction_method="model:test@1",
            source_refs=[
                SourceRef(rel_path="README.md", line_start=1, line_end=2, content_hash="h")
            ],
        ),
    )
    result = context_bundle.build(conn, project_id=project.id, token_budget=8000)
    assert "*(interpretation)*" in result.markdown


def test_bundle_with_a_task_ranks_by_relevance(conn, tmp_path):
    """The task must use words the corpus contains.

    "which database and why" was the original and it correctly ranks the
    README's Architecture section first, because that section says "must stay
    free of **database** imports" while the ADR says "PostgreSQL" and
    "persistence" and never "database". Same limitation pinned in Stage 5: with
    no language model, relevance is term overlap.
    """
    project = _project(conn, tmp_path)
    task = "why PostgreSQL for persistence"
    targeted = context_bundle.build(conn, project_id=project.id, task=task, token_budget=600)
    assert targeted.task == task
    titles = " ".join(entry.title for entry in targeted.included)
    assert "PostgreSQL" in titles, titles


def test_bundle_on_an_empty_project_says_so(conn, tmp_path):
    project = prepo.create(conn, Project(name="empty", root_path=str(tmp_path)))
    result = context_bundle.build(conn, project_id=project.id, token_budget=1000)
    assert result.included == []
    assert "No memory available" in result.markdown


def test_bundle_states_that_tokens_are_an_estimate(conn, tmp_path):
    """Claiming precision the method does not have would be dishonest."""
    project = _project(conn, tmp_path)
    result = context_bundle.build(conn, project_id=project.id, token_budget=2000)
    assert "not a tokenizer" in result.markdown


# ===================== logging must not touch stdout =====================


def test_logging_goes_to_stderr_not_stdout(capsys):
    """For stdio MCP, stdout *is* the JSON-RPC transport. One log line written
    there corrupts the protocol and the client hangs with no error."""
    import structlog

    from kernote.logging import configure_logging

    # No `force`, and no stream argument: the sink resolves sys.stderr at write
    # time, so capsys sees it without the configuration being rebound. Passing
    # capsys's stream here is what poisoned the rest of the suite, because the
    # logger then held a file that capsys later closed.
    configure_logging()
    structlog.get_logger("test").info("a_diagnostic_line")
    captured = capsys.readouterr()
    assert "a_diagnostic_line" not in captured.out, "a log line reached stdout"
    assert "a_diagnostic_line" in captured.err


# ===================== MCP over real stdio =====================


def _run_mcp_client(data_dir, coro_body):
    """Drive the server as a subprocess over stdio."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["PYTHONPATH"] = str(__import__("pathlib").Path(__file__).resolve().parents[2])
    env["KERNOTE_DATA_DIR"] = str(data_dir)

    async def main():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "kernote.mcp.server"], env=env
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            return await coro_body(session)

    return asyncio.run(asyncio.wait_for(main(), timeout=90))


@pytest.fixture
def mcp_project(tmp_data_dir, tmp_path):
    """A project in a data dir the MCP subprocess can also see."""
    from kernote.db.connection import open_db

    conn = open_db(tmp_data_dir / "kernote.db")
    project = _project(conn, tmp_path)
    conn.close()
    return tmp_data_dir, project


def test_mcp_exposes_exactly_four_read_only_tools(mcp_project):
    """ADR-0008: no write tool in any form, so an agent can consume the vault
    but cannot corrupt it."""
    data_dir, _ = mcp_project

    async def body(session):
        listed = await session.list_tools()
        return [tool.name for tool in listed.tools]

    names = _run_mcp_client(data_dir, body)
    assert sorted(names) == [
        "kernote_build_context",
        "kernote_get_decision",
        "kernote_project_summary",
        "kernote_search_memory",
    ]
    forbidden = ("write", "create", "update", "delete", "archive", "merge", "approve")
    assert not [n for n in names if any(word in n.lower() for word in forbidden)]


def test_mcp_tools_return_cited_answers(mcp_project):
    data_dir, _ = mcp_project

    async def body(session):
        out = {}
        result = await session.call_tool(
            "kernote_search_memory", {"query": "which database do we use", "limit": 4}
        )
        out["search"] = json.loads(result.content[0].text)
        result = await session.call_tool("kernote_project_summary", {})
        out["summary"] = json.loads(result.content[0].text)
        result = await session.call_tool("kernote_get_decision", {"subject": "PostgreSQL"})
        out["decision"] = json.loads(result.content[0].text)
        result = await session.call_tool(
            "kernote_get_decision", {"subject": "quantum teleportation"}
        )
        out["absent"] = json.loads(result.content[0].text)
        result = await session.call_tool(
            "kernote_build_context", {"task": "set up the project", "token_budget": 800}
        )
        out["bundle"] = json.loads(result.content[0].text)
        return out

    out = _run_mcp_client(data_dir, body)

    assert out["search"]["outcome"] in ("evidence_found", "weak_evidence", "not_found")
    assert out["summary"]["counts"]["memories"] > 0
    assert out["summary"]["decisions"]

    assert out["decision"]["found"] is True
    assert out["decision"]["decisions"][0]["citation"]

    # Absent subject: an explicit "evidence was not found", never a guess.
    assert out["absent"]["found"] is False
    assert "not found" in out["absent"]["statement"].lower()

    assert out["bundle"]["tokens_used"] <= 800
    assert "`" in out["bundle"]["markdown"], "bundle lost its citations"


def test_mcp_memory_type_filter_actually_filters(mcp_project):
    """The parameter originally had an `or True` in its predicate, so it
    silently did nothing — worse than not offering it."""
    data_dir, _ = mcp_project

    async def body(session):
        result = await session.call_tool(
            "kernote_search_memory",
            {"query": "database persistence", "memory_type": "decision", "limit": 5},
        )
        return json.loads(result.content[0].text)

    out = _run_mcp_client(data_dir, body)
    types = {item["memory_type"] for item in out["evidence"]}
    assert types <= {"decision"}, types


# ===================== API =====================


def test_context_endpoint(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    client.post(f"/api/v1/projects/{pid}/scan")
    res = client.post(
        f"/api/v1/projects/{pid}/context", json={"task": "run the tests", "token_budget": 600}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tokens_used"] <= 600
    assert "# Project context" in body["markdown"]
    assert isinstance(body["dropped"], list)


def test_context_endpoint_rejects_an_absurd_budget(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    assert (
        client.post(f"/api/v1/projects/{pid}/context", json={"token_budget": 10}).status_code
        == 422
    )


def test_mcp_info_endpoint_states_it_is_read_only(client, demo_repo):
    pid = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo}).json()[
        "id"
    ]
    body = client.get(f"/api/v1/projects/{pid}/mcp").json()
    assert body["writable"] is False
    assert len(body["tools"]) == 4
    assert body["transport"] == "stdio"
    assert "KERNOTE_PROJECT" in body["env"]
    assert body["claude_code_snippet"].startswith("claude mcp add kernote")


# ─── the MCP tools' own contracts ──────────────────────────────────────────


def _tools(conn, project_id):
    from kernote.mcp import server as mcp_server

    srv = mcp_server.build_server(conn, project_id)
    return {t.name: t.fn for t in srv._tool_manager.list_tools()}


def test_get_decision_matches_whole_words_only(conn, tmp_path):
    """The Stage 3 `"adr"` matching "Quadratic" defect, reintroduced here.

    Plain substring containment made `"it"` match "SQLite" and `"a"` match
    every decision in the project.
    """
    (tmp_path / "ADR-001-sqlite.md").write_text(
        "# ADR-001: Storage\n\nStatus: accepted\n\n"
        "## Decision\n\nWe will use SQLite for local storage.\n",
        encoding="utf-8",
    )
    project = _project(conn, tmp_path)
    get_decision = _tools(conn, project.id)["kernote_get_decision"]

    assert get_decision(subject="SQLite")["found"], "a real subject must match"
    # "it" is a whole word inside no decision here, and is not a substring hit
    # on "SQLite" any more.
    assert not get_decision(subject="it")["found"]


def test_get_decision_refuses_an_empty_or_too_common_subject(conn, tmp_path):
    """An empty subject used to fall through the filter and return ten
    arbitrary decisions as though they matched it."""
    project = _project(conn, tmp_path)
    get_decision = _tools(conn, project.id)["kernote_get_decision"]

    for subject in ("", "   ", "a", "the", "it"):
        result = get_decision(subject=subject)
        assert result["found"] is False
        assert result["decisions"] == []


def test_search_memory_rejects_an_unknown_type(conn, tmp_path):
    project = _project(conn, tmp_path)
    search = _tools(conn, project.id)["kernote_search_memory"]

    result = search(query="architecture", memory_type="not_a_real_type")
    assert result["outcome"] == "invalid_request"
    assert result["evidence"] == []
    assert "project_fact" in result["statement"], "it must name the valid types"


def test_search_memory_does_not_claim_records_its_filter_removed(conn, tmp_path):
    """The composed statement counts what retrieval found, which becomes a lie
    once the type filter empties the list: an agent must never read
    "19 supporting records" beside zero records."""
    project = _project(conn, tmp_path)
    search = _tools(conn, project.id)["kernote_search_memory"]

    result = search(query="architecture", memory_type="procedure", limit=8)
    if not result["evidence"]:
        assert result["outcome"] == "evidence_not_found"
        assert "none of them are of type" in result["statement"]


def test_mcp_info_tool_list_comes_from_the_live_registry(conn, tmp_path):
    """Two hand-maintained copies of the same fact is the drift this product
    exists to catch, so the screen derives its list from the real server."""
    from kernote.mcp.server import tool_manifest

    project = _project(conn, tmp_path)
    advertised = {t["name"] for t in tool_manifest(conn, project.id)}
    assert advertised == set(_tools(conn, project.id))
    assert all(t["description"] for t in tool_manifest(conn, project.id))
