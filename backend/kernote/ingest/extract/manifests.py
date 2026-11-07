"""Dependency manifests -> stack and dependency facts (ADR-0006)."""

from __future__ import annotations

import json
import tomllib

from ...domain.models import ClaimKind, Memory, MemoryType, SourceRef
from ...domain.scoring import score_confidence, score_importance

METHOD = "rule:manifests"


def _make(
    project_id: str,
    rel_path: str,
    content_hash: str,
    title: str,
    content: str,
    summary: str,
    git_blob_hash: str | None,
    git_commit: str | None,
) -> Memory:
    imp, imp_why = score_importance(
        memory_type=MemoryType.PROJECT_FACT, rel_path=rel_path, heading_depth=1
    )
    conf, conf_why = score_confidence(
        claim_kind=ClaimKind.SOURCE_FACT, extraction_method=METHOD, has_line_range=False
    )
    return Memory(
        project_id=project_id,
        type=MemoryType.PROJECT_FACT,
        title=title[:200],
        content=content[:8000],
        summary=summary[:240],
        claim_kind=ClaimKind.SOURCE_FACT,
        importance=imp,
        importance_reason=imp_why,
        confidence=conf,
        confidence_reason=conf_why,
        extraction_method=METHOD,
        source_refs=[
            SourceRef(
                rel_path=rel_path,
                content_hash=content_hash,
                git_blob_hash=git_blob_hash,
                git_commit=git_commit,
            )
        ],
    )


def extract(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    text: str,
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> list[Memory]:
    name = rel_path.rsplit("/", 1)[-1].lower()
    try:
        if name == "pyproject.toml":
            return _pyproject(
                project_id, rel_path, content_hash, text, git_blob_hash, git_commit
            )
        if name == "package.json":
            return _package_json(
                project_id, rel_path, content_hash, text, git_blob_hash, git_commit
            )
        if name.startswith("requirements") and name.endswith(".txt"):
            return _requirements(
                project_id, rel_path, content_hash, text, git_blob_hash, git_commit
            )
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, ValueError, KeyError):
        # A malformed manifest is the project's business, not a scan failure.
        return []
    return []


def _pyproject(pid, rel, h, text, blob, commit) -> list[Memory]:
    data = tomllib.loads(text)
    proj = data.get("project", {})
    deps = proj.get("dependencies", []) or []
    out = [
        _make(
            pid,
            rel,
            h,
            f"Python project: {proj.get('name', 'unnamed')}",
            f"name: {proj.get('name', 'unnamed')}\n"
            f"version: {proj.get('version', 'unspecified')}\n"
            f"requires-python: {proj.get('requires-python', 'unspecified')}\n"
            f"description: {proj.get('description', '')}",
            f"Python project declared in {rel}",
            blob,
            commit,
        )
    ]
    if deps:
        out.append(
            _make(
                pid,
                rel,
                h,
                f"Python dependencies ({len(deps)})",
                "\n".join(str(d) for d in deps),
                f"{len(deps)} runtime dependencies from {rel}",
                blob,
                commit,
            )
        )
    return out


def _package_json(pid, rel, h, text, blob, commit) -> list[Memory]:
    data = json.loads(text)
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    out = [
        _make(
            pid,
            rel,
            h,
            f"Node project: {data.get('name', 'unnamed')}",
            f"name: {data.get('name', 'unnamed')}\n"
            f"version: {data.get('version', 'unspecified')}\n"
            f"type: {data.get('type', 'commonjs')}",
            f"Node project declared in {rel}",
            blob,
            commit,
        )
    ]
    scripts = data.get("scripts", {})
    if scripts:
        out.append(
            _make(
                pid,
                rel,
                h,
                "npm scripts",
                "\n".join(f"{k}: {v}" for k, v in scripts.items()),
                f"{len(scripts)} npm script(s) from {rel}",
                blob,
                commit,
            )
        )
    if deps:
        out.append(
            _make(
                pid,
                rel,
                h,
                f"Node dependencies ({len(deps)})",
                "\n".join(f"{k} {v}" for k, v in sorted(deps.items())),
                f"{len(deps)} dependencies from {rel}",
                blob,
                commit,
            )
        )
    return out


def _requirements(pid, rel, h, text, blob, commit) -> list[Memory]:
    pins = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith(("#", "-r ", "--"))
    ]
    if not pins:
        return []
    return [
        _make(
            pid,
            rel,
            h,
            f"Python requirements ({len(pins)}) — {rel}",
            "\n".join(pins),
            f"{len(pins)} pinned requirement(s) from {rel}",
            blob,
            commit,
        )
    ]
