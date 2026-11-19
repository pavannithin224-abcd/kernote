"""Code symbol extraction with tree-sitter (ADR-0012).

One `architecture` memory per top-level definition, carrying its signature,
its docstring and the exact line range of the definition. Line ranges come
from the parser, which is the point: regex-based symbol extraction is
permanently approximate, and provenance that is approximate is not provenance.

A language exists here only when `queries/<lang>/tags.scm` exists and has a
passing test. That is how the project contract's rule against claiming untested
language support is enforced structurally rather than remembered.
"""

from __future__ import annotations

import functools
import pathlib
import re

import structlog

from ... import resources
from ...domain.models import ClaimKind, Memory, MemoryType, SourceRef
from ...domain.scoring import score_confidence, score_importance

log = structlog.get_logger(__name__)

METHOD = "rule:code_symbols"
QUERIES_DIR = resources.package_dir("ingest/extract/queries")

# Extension -> language name used by both tree_sitter_language_pack and the
# queries directory. Only languages with a query file are listed.
LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
}

_MAX_SYMBOLS_PER_FILE = 120
_SIGNATURE_LINES = 3


def supported_languages() -> list[str]:
    """Languages with both a query file and a suffix mapping."""
    return sorted(
        {
            lang
            for lang in LANGUAGE_BY_SUFFIX.values()
            if (QUERIES_DIR / lang / "tags.scm").is_file()
        }
    )


_TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)(test_[^/]+|[^/]+_test)\.pyi?$"
    r"|\.(test|spec)\.[jt]sx?$",
    re.IGNORECASE,
)


def is_test_path(rel_path: str) -> bool:
    """Tests describe behaviour, not a module's shape.

    Dogfooding produced 19 `architecture` memories from one integration test
    file, which is noise in a module-shape memory. Test *coverage* is a
    different question and a different memory type, for later.
    """
    return bool(_TEST_PATH.search(rel_path))


def language_for(rel_path: str) -> str | None:
    if is_test_path(rel_path):
        return None
    return LANGUAGE_BY_SUFFIX.get(pathlib.Path(rel_path).suffix.lower())


@functools.lru_cache(maxsize=32)
def _query(language: str):
    """Compiled query for a language, or None if unavailable.

    Cached because compiling a query per file is wasteful, and returning None
    rather than raising means an unsupported or broken grammar degrades to
    "skip this language" instead of failing the whole scan (risk R11).
    """
    scm = QUERIES_DIR / language / "tags.scm"
    if not scm.is_file():
        return None
    try:
        import tree_sitter_language_pack as pack

        return pack.get_language(language).query(scm.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - a bad grammar must not stop a scan
        log.warning("code_symbols.query_unavailable", language=language, error=str(exc))
        return None


@functools.lru_cache(maxsize=32)
def _parser(language: str):
    try:
        import tree_sitter_language_pack as pack

        return pack.get_parser(language)
    except Exception as exc:  # noqa: BLE001
        log.warning("code_symbols.parser_unavailable", language=language, error=str(exc))
        return None


_CONTAINER_TYPES = {
    "class_definition",  # python
    "class_declaration",  # ts / js
    "interface_declaration",
    "abstract_class_declaration",
}


def _enclosing_path(node, source: bytes) -> list[str]:
    """Names of the classes or interfaces enclosing a definition.

    Without this, every `__init__` and every `render` in a codebase becomes a
    separate memory called "function __init__", which collide on title and are
    useless to read. `Hunk.overlaps` is a usable fact; `overlaps` is not.
    """
    names: list[str] = []
    current = node.parent
    while current is not None:
        if current.type in _CONTAINER_TYPES:
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                names.append(
                    source[name_node.start_byte : name_node.end_byte].decode("utf-8", "replace")
                )
        current = current.parent
    return list(reversed(names))


_PY_DOCSTRING = re.compile(r'^\s*(?:"""|\'\'\')(?P<body>.*?)(?:"""|\'\'\')', re.DOTALL)
_JS_DOC = re.compile(r"/\*\*(?P<body>.*?)\*/", re.DOTALL)


def _docstring(lines: list[str], def_start: int, def_end: int, language: str) -> str:
    """The definition's own docstring, if it has one."""
    body = "\n".join(lines[def_start : min(def_end, def_start + 12)])
    if language == "python":
        # Skip the signature line(s), then look for a leading string literal.
        after_sig = "\n".join(lines[def_start + 1 : min(def_end, def_start + 12)])
        m = _PY_DOCSTRING.match(after_sig)
        if m:
            return " ".join(m.group("body").split())[:400]
        return ""
    m = _JS_DOC.search(body)
    if m:
        cleaned = re.sub(r"^\s*\*\s?", "", m.group("body"), flags=re.MULTILINE)
        return " ".join(cleaned.split())[:400]
    return ""


def _signature(lines: list[str], def_start: int) -> str:
    """The first few lines of the definition, which carry the signature."""
    chunk = [ln.rstrip() for ln in lines[def_start : def_start + _SIGNATURE_LINES]]
    while chunk and not chunk[-1]:
        chunk.pop()
    return "\n".join(chunk)[:600]


def extract(
    *,
    project_id: str,
    rel_path: str,
    content_hash: str,
    text: str,
    git_blob_hash: str | None = None,
    git_commit: str | None = None,
) -> list[Memory]:
    language = language_for(rel_path)
    if language is None:
        return []
    query, parser = _query(language), _parser(language)
    if query is None or parser is None:
        return []

    source = text.encode("utf-8")
    try:
        tree = parser.parse(source)
    except Exception as exc:  # noqa: BLE001 - never fail a scan on one file
        log.warning("code_symbols.parse_failed", rel_path=rel_path, error=str(exc))
        return []

    lines = text.splitlines()
    out: list[Memory] = []
    seen: set[tuple[str, int]] = set()

    # matches() pairs each @definition with its own @name; captures() returns
    # them as separate lists that would have to be re-correlated by position.
    for _pattern_index, captures in query.matches(tree.root_node):
        name_nodes = captures.get("name") or []
        def_nodes = [
            n for key, v in captures.items() if key.startswith("definition.") for n in v
        ]
        kind = next(
            (key.split(".", 1)[1] for key in captures if key.startswith("definition.")),
            "symbol",
        )
        if not name_nodes or not def_nodes:
            continue
        name = source[name_nodes[0].start_byte : name_nodes[0].end_byte].decode(
            "utf-8", "replace"
        )
        node = def_nodes[0]
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        enclosing = _enclosing_path(node, source)
        qualified = ".".join([*enclosing, name])
        # A function inside a class is a method, whatever the grammar calls the
        # node. Saying "function" there would be wrong in the memory title.
        if enclosing and kind in {"function", "symbol"}:
            kind = "method"

        # Private helpers are noise in a module-shape memory. `__init__` and
        # other dunders are kept because they are part of the public contract.
        if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
            continue
        if (qualified, line_start) in seen:
            continue
        seen.add((qualified, line_start))
        if len(out) >= _MAX_SYMBOLS_PER_FILE:
            log.warning(
                "code_symbols.truncated", rel_path=rel_path, limit=_MAX_SYMBOLS_PER_FILE
            )
            break

        doc = _docstring(lines, line_start - 1, line_end, language)
        signature = _signature(lines, line_start - 1)
        # The claim is a source fact (the signature is quoted verbatim); only
        # the *selection* is ours.
        content = signature + (f"\n\n{doc}" if doc else "")

        ref = SourceRef(
            rel_path=rel_path,
            line_start=line_start,
            line_end=line_end,
            content_hash=content_hash,
            git_blob_hash=git_blob_hash,
            git_commit=git_commit,
        )
        imp, imp_why = score_importance(
            memory_type=MemoryType.ARCHITECTURE, rel_path=rel_path, heading_depth=1
        )
        conf, conf_why = score_confidence(
            claim_kind=ClaimKind.SOURCE_FACT,
            extraction_method=METHOD,
            has_line_range=True,
        )
        out.append(
            Memory(
                project_id=project_id,
                type=MemoryType.ARCHITECTURE,
                title=f"{kind} {qualified}"[:200],
                content=content[:8000],
                summary=(doc or f"{kind} {qualified} in {rel_path}")[:240],
                claim_kind=ClaimKind.SOURCE_FACT,
                importance=imp,
                importance_reason=imp_why,
                confidence=conf,
                confidence_reason=conf_why,
                extraction_method=METHOD,
                source_refs=[ref],
            )
        )
    return out
