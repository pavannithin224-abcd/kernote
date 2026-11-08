"""Deterministic Markdown extractors (ADR-0006).

No model is involved. Output is reproducible, fast to test, and every record
carries the exact line range it came from. Recall is lower than an LLM
pipeline would give; that trade is stated in the README.
"""

from __future__ import annotations

import re

from ...domain.models import ClaimKind, Memory, MemoryType, SourceRef
from ...domain.scoring import score_confidence, score_importance
from ..normalize import Section

# Heading words that mean "this section tells you how to do something".
_PROCEDURE_WORDS = (
    "install",
    "setup",
    "set up",
    "getting started",
    "quick start",
    "quickstart",
    "build",
    "run",
    "running",
    "test",
    "testing",
    "deploy",
    "deployment",
    "development",
    "usage",
    "configure",
    "configuration",
    "troubleshoot",
)
_ARCHITECTURE_WORDS = (
    "architecture",
    "design",
    "structure",
    "overview",
    "components",
    "modules",
    "layout",
    "how it works",
    "data model",
    "schema",
    "pipeline",
)
_GOTCHA_WORDS = ("gotcha", "caveat", "known issue", "limitation", "warning", "pitfall")
_CONVENTION_WORDS = ("convention", "style", "guideline", "standard", "contributing")
_DECISION_WORDS = ("decision", "adr", "rationale", "why we", "trade-off", "tradeoff")


def _matches(heading: str, words: tuple[str, ...]) -> bool:
    """Word-boundary match, not substring.

    Plain `"adr" in heading` classifies "Quadratic scoring" and "Squadron
    layout" as decisions, because they contain the letters a-d-r. Found while
    dogfooding Kernote on its own repository.

    The optional trailing `s` matters: a bare `\b` boundary stops "Conventions"
    from matching "convention", which substring matching had handled by
    accident. Tightening without it traded one bug for another.
    """
    return any(re.search(rf"\b{re.escape(w)}s?\b", heading) for w in words)


def _classify(heading: str | None) -> MemoryType:
    h = (heading or "").lower()
    for words, mtype in (
        (_DECISION_WORDS, MemoryType.DECISION),
        (_PROCEDURE_WORDS, MemoryType.PROCEDURE),
        (_ARCHITECTURE_WORDS, MemoryType.ARCHITECTURE),
        (_GOTCHA_WORDS, MemoryType.GOTCHA),
        (_CONVENTION_WORDS, MemoryType.CONVENTION),
    ):
        if _matches(h, words):
            return mtype
    return MemoryType.PROJECT_FACT


def _summarise(text: str, limit: int = 240) -> str:
    """First sentence-ish of the section. Extractive: never invents wording."""
    body = " ".join(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "```", "|", "-", "*", ">"))
    )
    if not body:
        body = " ".join(text.split())
    return body[:limit].strip() or text[:limit].strip()


def extract_sections(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    sections: list[Section],
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> list[Memory]:
    """One memory per meaningful section, typed by its heading."""
    out: list[Memory] = []
    method = "rule:markdown_sections"

    for s in sections:
        if s.heading is None or len(s.text) < 40:
            continue
        mtype = _classify(s.heading)
        ref = SourceRef(
            rel_path=rel_path,
            line_start=s.line_start,
            line_end=s.line_end,
            content_hash=content_hash,
            git_blob_hash=git_blob_hash,
            git_commit=git_commit,
        )
        imp, imp_why = score_importance(
            memory_type=mtype, rel_path=rel_path, heading_depth=max(1, s.level)
        )
        conf, conf_why = score_confidence(
            claim_kind=ClaimKind.SOURCE_FACT, extraction_method=method, has_line_range=True
        )
        out.append(
            Memory(
                project_id=project_id,
                type=mtype,
                title=s.heading[:200],
                content=s.text[:8000],
                summary=_summarise(s.text),
                claim_kind=ClaimKind.SOURCE_FACT,
                importance=imp,
                importance_reason=imp_why,
                confidence=conf,
                confidence_reason=conf_why,
                extraction_method=method,
                source_refs=[ref],
            )
        )
    return out


def extract_commands(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    sections: list[Section],
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> list[Memory]:
    """Shell blocks under a how-to heading become `procedure` memories."""
    out: list[Memory] = []
    method = "rule:markdown_commands"
    shell_langs = {"", "sh", "bash", "shell", "zsh", "console", "powershell", "ps1"}

    for s in sections:
        heading_low = (s.heading or "").lower()
        if not any(w in heading_low for w in _PROCEDURE_WORDS):
            continue
        for lang, code, fs, fe in s.code_blocks:
            if lang.lower() not in shell_langs:
                continue
            cmds = [
                ln.strip()
                for ln in code.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if not cmds:
                continue
            ref = SourceRef(
                rel_path=rel_path,
                line_start=fs,
                line_end=fe,
                content_hash=content_hash,
                git_blob_hash=git_blob_hash,
                git_commit=git_commit,
            )
            imp, imp_why = score_importance(
                memory_type=MemoryType.PROCEDURE,
                rel_path=rel_path,
                heading_depth=max(1, s.level),
            )
            conf, conf_why = score_confidence(
                claim_kind=ClaimKind.SOURCE_FACT, extraction_method=method, has_line_range=True
            )
            out.append(
                Memory(
                    project_id=project_id,
                    type=MemoryType.PROCEDURE,
                    title=f"{s.heading}: commands"[:200],
                    content="\n".join(cmds)[:4000],
                    summary=f"{len(cmds)} command(s) from “{s.heading}”",
                    claim_kind=ClaimKind.SOURCE_FACT,
                    importance=imp,
                    importance_reason=imp_why,
                    confidence=conf,
                    confidence_reason=conf_why,
                    extraction_method=method,
                    source_refs=[ref],
                )
            )
    return out
