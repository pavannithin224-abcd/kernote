"""Architecture Decision Record extraction (ADR-0006, ADR-0012 sibling).

Decisions are the memory type developers most often need and least often find,
and until this existed the decision-conflict detector had nothing real to work
on -- only hand-written memories carried a decision payload.

Deterministic and conservative. Three conventions are recognised:

* `adr-tools` / MADR files -- `docs/adr/0001-use-postgres.md`, with a
  `## Status` / `## Context` / `## Decision` / `## Consequences` body.
* A combined decision log -- `## ADR-0007 - Title` sections inside one file,
  with a `**Status:**` line. (Kernote's own `docs/DECISIONS.md` is this shape,
  which makes it a useful real fixture rather than a synthetic one.)
* A plain `## Decision: ...` heading anywhere.

`chosen` and `alternatives` are only populated when a pattern actually matches.
Guessing them would feed the conflict detector fabricated options, and a wrong
conflict finding is worse than a missing one.
"""

from __future__ import annotations

import re

from ...domain.models import ClaimKind, Memory, MemoryType, SourceRef
from ...domain.scoring import score_confidence, score_importance
from ..normalize import Section

METHOD = "rule:adr"

# Headings that mark a decision record on their own, anywhere: "ADR-7 - Title"
# or "Decision: Title".
_ADR_HEADING_STRONG = re.compile(
    r"^\s*(?:adr[-\s]?(\d+)\s*[-–—:.]?\s*|decision\s*[:\-–—]\s*)(?P<rest>.+)$",
    re.IGNORECASE,
)
# A bare "4. Title" is the adr-tools convention, but it is also how ordinary
# numbered documentation is written. Dogfooding Kernote on its own repository
# showed this form alone misreading "## 1. Shape" and "## 2. Repository
# structure" in ARCHITECTURE.md as decisions -- 44 false records out of 66. It
# now only counts inside a path that already looks like a decision document.
_ADR_HEADING_NUMBERED = re.compile(r"^\s*(\d{1,4})\.\s+(?P<rest>.+)$")
# Paths that mark a decision document.
_ADR_PATH = re.compile(
    r"(^|/)(adrs?|decisions?|decision[-_]records?)(/|\.md$|s\.md$)|(^|/)\d{3,4}-[a-z0-9-]+\.md$",
    re.IGNORECASE,
)

_STATUS = re.compile(
    r"\**status\**\s*[:\-–—]?\s*\**\s*(accepted|proposed|rejected|superseded|deprecated|draft)\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# "**Decision.**" / "## Decision" / "Decision Outcome"
_DECISION_BLOCK = re.compile(
    r"(?:^|\n)\s*(?:#+\s*|\*\*)decision(?:\s+outcome)?[.:]?\**\s*(?P<body>.+?)(?=\n\s*(?:#+\s|\*\*[A-Z])|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_ALT_BLOCK = re.compile(
    r"(?:^|\n)\s*(?:#+\s*|\*\*)(?:alternatives?|considered\s+options?|options?\s+considered)"
    r"(?:\s+considered)?[.:]?\**\s*(?P<body>.+?)(?=\n\s*(?:#+\s|\*\*[A-Z])|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Within a decision body: the chosen thing.
# A chosen option is a short noun phrase. These patterns deliberately cap
# length and stop at punctuation: matching a whole sentence would hand the
# conflict detector prose instead of an option name, and a fabricated option
# produces a fabricated conflict.
_OPTION = r"[`*\w][^.,;:\n]{1,44}"
_CHOSEN_PATTERNS = (
    re.compile(
        r"\bwe\s+(?:will\s+|have\s+)?(?:use|chose|choose|chosen|select(?:ed)?|"
        r"adopt(?:ed)?|go\s+with|stay\s+on)\s+(?:the\s+|a\s+|an\s+)?(?P<v>" + _OPTION + r")",
        re.I,
    ),
    re.compile(r"\bdecision\s*(?:is|was|:)\s*(?:to\s+use\s+)?(?P<v>" + _OPTION + r")", re.I),
    re.compile(r"^\s*(?:use|adopt|keep)\s+(?P<v>" + _OPTION + r")", re.I | re.MULTILINE),
    re.compile(r"^\s*(?P<v>" + _OPTION + r"?)\s+over\s+" + _OPTION, re.I),
    # MADR states it plainly: "Chosen option: Tailwind CSS, because ..."
    re.compile(r"\bchosen\s+option\s*[:\-–—]\s*(?P<v>" + _OPTION + r")", re.I),
)
# Option names inside an alternatives block: *italic*, `code`, or a list item
# up to its dash.
_ALT_NAME = re.compile(r"[*_`]{1,2}(?P<v>[^*_`\n]{2,60})[*_`]{1,2}")
_ALT_LIST_ITEM = re.compile(r"^\s*[-*+]\s+(?P<v>[^—–\-:\n]{2,60}?)\s*[—–:\-]", re.MULTILINE)

_TRIM = re.compile(r"^[\s\"'(\[]+|[\s\"')\].,;:]+$")
# Option names are compared against each other by the conflict detector, so
# they must be bare: markdown emphasis stripped, and cut at the connective
# that starts the justification. "PostgreSQL as the primary datastore" has to
# reduce to "PostgreSQL", or it will never match another ADR's "SQLite" vs
# "PostgreSQL" alternatives list.
_OPTION_MARKUP = re.compile(r"^[\s*_`]+|[\s*_`]+$")
_CONNECTIVE = re.compile(
    r"\s+(?:as|for|because|since|which|that|and|plus|over|instead|rather)\b.*$",
    re.IGNORECASE,
)


def _clean_option(value: str) -> str:
    value = _OPTION_MARKUP.sub("", " ".join(value.split()))
    value = _CONNECTIVE.sub("", value)
    return _OPTION_MARKUP.sub("", value).rstrip(".,;:")


def _clean(value: str) -> str:
    return _TRIM.sub("", " ".join(value.split()))


def _heading_match(heading: str, *, in_adr_path: bool):
    """A decision heading, or None.

    The numbered form is only trusted inside a decision document, because
    numbered headings are ordinary in documentation.
    """
    strong = _ADR_HEADING_STRONG.match(heading)
    if strong:
        return strong
    return _ADR_HEADING_NUMBERED.match(heading) if in_adr_path else None


def looks_like_adr(rel_path: str, sections: list[Section]) -> bool:
    if _ADR_PATH.search(rel_path):
        return True
    return any(s.heading and _heading_match(s.heading, in_adr_path=False) for s in sections)


def _status_of(text: str) -> str | None:
    m = _STATUS.search(text)
    return m.group(1).lower() if m else None


def _decided_on(text: str) -> str | None:
    """The first ISO date, which in every supported convention is the decision
    date on or next to the status line."""
    m = _ISO_DATE.search(text)
    return m.group(1) if m else None


def _chosen_of(text: str) -> str | None:
    block = _DECISION_BLOCK.search(text)
    body = block.group("body") if block else text
    for pattern in _CHOSEN_PATTERNS:
        m = pattern.search(body)
        if m:
            value = _clean_option(m.group("v"))
            if value and len(value) > 1:
                return value
    return None


def _alternatives_of(text: str) -> list[str]:
    block = _ALT_BLOCK.search(text)
    if not block:
        return []
    body = block.group("body")
    names: list[str] = []
    for pattern in (_ALT_NAME, _ALT_LIST_ITEM):
        for m in pattern.finditer(body):
            value = _clean_option(m.group("v"))
            if value and len(value) > 1 and value.lower() not in {n.lower() for n in names}:
                names.append(value)
    return names[:8]


def _title_of(heading: str, *, in_adr_path: bool = True) -> str:
    m = _heading_match(heading, in_adr_path=in_adr_path)
    return _clean(m.group("rest")) if m else _clean(heading)


def _build(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    title: str,
    body: str,
    line_start: int,
    line_end: int,
    level: int,
    git_blob_hash: str | None,
    git_commit: str | None,
) -> Memory:
    payload: dict[str, object] = {}
    status = _status_of(body)
    if status:
        payload["status"] = status
    chosen = _chosen_of(body)
    if chosen:
        payload["chosen"] = chosen
    alternatives = _alternatives_of(body)
    if alternatives:
        payload["alternatives"] = alternatives
    decided_on = _decided_on(body)
    if decided_on:
        payload["decided_on"] = decided_on

    imp, imp_why = score_importance(
        memory_type=MemoryType.DECISION, rel_path=rel_path, heading_depth=max(1, level)
    )
    conf, conf_why = score_confidence(
        claim_kind=ClaimKind.SOURCE_FACT, extraction_method=METHOD, has_line_range=True
    )
    return Memory(
        project_id=project_id,
        type=MemoryType.DECISION,
        title=title[:200],
        content=body[:8000],
        summary=(
            f"{payload.get('status', 'status unknown')}"
            + (f"; chose {chosen}" if chosen else "")
            + (f"; considered {', '.join(alternatives[:3])}" if alternatives else "")
        )[:240],
        claim_kind=ClaimKind.SOURCE_FACT,
        importance=imp,
        importance_reason=imp_why,
        confidence=conf,
        confidence_reason=conf_why,
        extraction_method=METHOD,
        # The decision date is when the claim became true of the project, which
        # is exactly what valid_from means (ADR-0017).
        valid_from=decided_on,
        decision=payload or None,
        source_refs=[
            SourceRef(
                rel_path=rel_path,
                line_start=line_start,
                line_end=line_end,
                content_hash=content_hash,
                git_blob_hash=git_blob_hash,
                git_commit=git_commit,
            )
        ],
    )


def _whole_document(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    text: str,
    sections: list[Section],
    git_blob_hash: str | None,
    git_commit: str | None,
) -> Memory | None:
    """One decision spanning the whole file."""
    if len(text.strip()) < 40:
        return None
    heading = next((s.heading for s in sections if s.heading), None)
    title = _title_of(heading) if heading else rel_path.rsplit("/", 1)[-1]
    total = len(text.splitlines()) or 1
    return _build(
        project_id=project_id,
        rel_path=rel_path,
        content_hash=content_hash,
        title=title,
        body=text,
        line_start=1,
        line_end=total,
        level=1,
        git_blob_hash=git_blob_hash,
        git_commit=git_commit,
    )


def extract(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    text: str,
    sections: list[Section],
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> list[Memory]:
    """Decision memories from an ADR document.

    Two document shapes, which must be handled differently:

    * **One decision per file** (`adr-tools`, MADR): the decision is the whole
      document and `## Status` / `## Decision` / `## Considered Options` are its
      sub-sections. Treating each sub-section as its own ADR -- the first thing
      I wrote -- produced nothing at all, because no sub-section carries both a
      decision heading and a body long enough to matter.
    * **One combined log** (Kernote's own `docs/DECISIONS.md`): each `## ADR-N`
      section is a separate decision.
    """
    if not looks_like_adr(rel_path, sections):
        return []

    in_adr_path = bool(_ADR_PATH.search(rel_path))
    adr_headings = [
        s for s in sections if s.heading and _heading_match(s.heading, in_adr_path=in_adr_path)
    ]
    if len(adr_headings) <= 1:
        memory = _whole_document(
            project_id=project_id,
            rel_path=rel_path,
            content_hash=content_hash,
            text=text,
            sections=sections,
            git_blob_hash=git_blob_hash,
            git_commit=git_commit,
        )
        return [memory] if memory else []

    out: list[Memory] = []
    for section in sections:
        if section.heading is None or len(section.text) < 40:
            continue
        # A section is a decision if its own heading says so, or the file is a
        # decision document and the section carries a status line.
        heading_says = bool(_heading_match(section.heading, in_adr_path=in_adr_path))
        if not heading_says and not (_status_of(section.text) and _ADR_PATH.search(rel_path)):
            continue
        out.append(
            _build(
                project_id=project_id,
                rel_path=rel_path,
                content_hash=content_hash,
                title=_title_of(section.heading),
                body=section.text,
                line_start=section.line_start,
                line_end=section.line_end,
                level=section.level,
                git_blob_hash=git_blob_hash,
                git_commit=git_commit,
            )
        )
    return out
