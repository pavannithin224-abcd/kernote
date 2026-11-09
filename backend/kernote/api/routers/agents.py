"""Agent delivery (F7, F9): the context bundle and MCP connection details."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...apply import context_bundle
from ...config import settings
from ...db.repositories import projects as project_repo
from ...mcp.server import SERVER_NAME, tool_manifest
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["agents"])


class BundleRequest(BaseModel):
    task: str | None = Field(default=None, max_length=500)
    token_budget: int = Field(default=4000, ge=200, le=32000)


class McpInfo(BaseModel):
    server_name: str
    transport: str
    command: str
    env: dict[str, str]
    tools: list[dict[str, str]]
    writable: bool
    claude_code_snippet: str
    note: str


@router.post("/projects/{project_id}/context")
def build_context(project_id: str, body: BundleRequest) -> dict:
    """A budgeted Markdown bundle of approved memory, with citations.

    The response reports what was dropped: a silently truncated context is
    worse than a short one, because the reader cannot tell which they have.
    """
    conn = db()
    if project_repo.get(conn, project_id) is None:
        raise HTTPException(404, "project not found")
    result = context_bundle.build(
        conn, project_id=project_id, task=body.task, token_budget=body.token_budget
    )
    return {
        "markdown": result.markdown,
        "task": result.task,
        "token_budget": result.token_budget,
        "tokens_used": result.tokens_used,
        "included": len(result.included),
        "dropped": [
            {"title": entry.title, "citation": entry.citation} for entry in result.dropped
        ],
        # Memories ranked below the candidate cut-off were never weighed
        # against the budget. Reporting only `dropped` would understate what
        # the bundle leaves out.
        "not_considered": result.not_considered,
        "excluded_total": result.excluded_total,
        "over_budget": result.over_budget,
        "note": result.note,
    }


@router.get("/projects/{project_id}/mcp", response_model=McpInfo)
def mcp_info(project_id: str) -> McpInfo:
    """How to connect an agent, and exactly what it would be able to do."""
    conn = db()
    project = project_repo.get(conn, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    interpreter = sys.executable
    backend_dir = str(Path(__file__).resolve().parents[3])
    command = f"{interpreter} -m kernote.mcp.server"
    env = {
        "PYTHONPATH": backend_dir,
        "KERNOTE_PROJECT": project.id,
        "KERNOTE_DATA_DIR": str(settings.data_dir),
    }
    env_flags = " ".join(f"--env {k}={shlex.quote(v)}" for k, v in env.items())
    snippet = f"claude mcp add {SERVER_NAME} {env_flags} -- {command}"
    return McpInfo(
        server_name=SERVER_NAME,
        transport="stdio",
        command=command,
        env=env,
        tools=tool_manifest(conn, project_id),
        claude_code_snippet=snippet,
        writable=False,
        note=(
            "Read-only by design (ADR-0008). There is no write tool in any form, "
            "so a connected agent can consume this project's memory but cannot "
            "change it. Writes stay behind human approval in Kernote."
        ),
    )
