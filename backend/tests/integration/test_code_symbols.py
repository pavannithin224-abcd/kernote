"""tree-sitter symbol extraction (Stage 3, ADR-0012).

A language is supported only when `queries/<lang>/tags.scm` exists and has a
passing test here. That is how `CLAUDE.md`'s rule against claiming untested
language support becomes structural.
"""

import pytest
import tree_sitter_language_pack as pack

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.extract import code_symbols as cs
from kernote.ingest.pipeline import scan_project

PY_SRC = '''"""Module docstring."""


class Widget:
    """A widget that renders."""

    def __init__(self, size):
        self.size = size

    def render(self, scale):
        """Render at a scale."""
        return self.size * scale

    def _private_helper(self):
        return 1


def build(config):
    """Build a widget from config."""
    return Widget(config["size"])


def _internal():
    return None
'''

TS_SRC = """export interface WidgetProps {
  size: number;
}

export type Scale = number;

export class Renderer {
  render(props: WidgetProps): string {
    return String(props.size);
  }
}

export function build(size: number): Renderer {
  return new Renderer();
}

export const useWidget = (size: number) => {
  return { size };
};
"""


# ----------------------------------------------- the native dependency (R11)


def test_grammars_load():
    """Risk R11: tree-sitter is a native wheel. If this fails, the degradation
    path matters more than the feature."""
    assert pack.get_parser("python") is not None
    assert pack.get_language("typescript") is not None


@pytest.mark.parametrize("language", ["python", "typescript", "tsx", "javascript"])
def test_every_shipped_query_compiles(language):
    scm = cs.QUERIES_DIR / language / "tags.scm"
    assert scm.is_file(), f"no tags.scm for {language}"
    query = pack.get_language(language).query(scm.read_text(encoding="utf-8"))
    assert query.pattern_count > 0


def test_supported_languages_are_exactly_those_with_queries():
    assert cs.supported_languages() == ["javascript", "python", "tsx", "typescript"]


def test_unsupported_language_is_skipped_not_guessed():
    """Only tested languages are claimed. A .rs file yields nothing rather than
    a half-parsed guess."""
    assert cs.language_for("src/main.rs") is None
    assert (
        cs.extract(
            project_id="p", rel_path="src/main.rs", content_hash="h", text="fn main() {}"
        )
        == []
    )


# ------------------------------------------------------------- extraction


def test_python_symbols_with_exact_line_ranges():
    mems = cs.extract(project_id="p", rel_path="widget.py", content_hash="h", text=PY_SRC)
    titles = [m.title for m in mems]
    assert "class Widget" in titles
    assert "method Widget.render" in titles, "methods must be qualified by their class"
    assert "function build" in titles
    # Private helpers are noise in a module-shape memory; dunders are kept.
    assert "function _internal" not in titles
    assert not any("_private_helper" in t for t in titles)
    assert "method Widget.__init__" in titles

    render = next(m for m in mems if m.title == "method Widget.render")
    lines = PY_SRC.splitlines()
    ref = render.source_refs[0]
    assert "def render" in lines[ref.line_start - 1], "line range does not point at the def"
    assert render.summary == "Render at a scale.", "docstring not captured"


def test_typescript_declarations():
    mems = cs.extract(project_id="p", rel_path="widget.ts", content_hash="h", text=TS_SRC)
    titles = [m.title for m in mems]
    for expected in (
        "interface WidgetProps",
        "type Scale",
        "class Renderer",
        "method Renderer.render",
        "function build",
    ):
        assert expected in titles, f"{expected} missing from {titles}"
    # Arrow-function consts are how most components and hooks are declared.
    assert "function useWidget" in titles


def test_tsx_components_are_found():
    tsx = "export default function Panel() {\n  return <div>hi</div>;\n}\n"
    mems = cs.extract(project_id="p", rel_path="Panel.tsx", content_hash="h", text=tsx)
    assert [m.title for m in mems] == ["function Panel"]


def test_qualified_names_prevent_collisions():
    """Every class has an __init__; unqualified titles would collide and be
    unreadable."""
    src = (
        "class A:\n    def go(self):\n        pass\n\n\n"
        "class B:\n    def go(self):\n        pass\n"
    )
    titles = [
        m.title for m in cs.extract(project_id="p", rel_path="x.py", content_hash="h", text=src)
    ]
    assert "method A.go" in titles and "method B.go" in titles


def test_syntax_error_does_not_raise():
    broken = "class Widget(:\n    def \n"
    assert isinstance(
        cs.extract(project_id="p", rel_path="b.py", content_hash="h", text=broken), list
    )


def test_every_symbol_carries_provenance():
    for m in cs.extract(project_id="p", rel_path="w.py", content_hash="abc", text=PY_SRC):
        ref = m.source_refs[0]
        assert ref.content_hash == "abc"
        assert ref.line_start and ref.line_end and ref.line_end >= ref.line_start
        assert m.extraction_method == "rule:code_symbols"


# ----------------------------------------------------------- test exclusion


@pytest.mark.parametrize(
    "path",
    [
        "backend/tests/test_thing.py",
        "tests/unit/test_a.py",
        "src/__tests__/a.ts",
        "src/widget.test.ts",
        "src/widget.spec.tsx",
        "backend/thing_test.py",
    ],
)
def test_test_files_do_not_produce_architecture_memories(path):
    """Dogfooding produced 19 architecture memories from one integration test
    file. Tests describe behaviour, not a module's shape."""
    assert cs.is_test_path(path), path
    assert cs.language_for(path) is None


@pytest.mark.parametrize("path", ["src/latest.py", "src/protest.ts", "src/contest/a.py"])
def test_non_test_paths_are_not_excluded(path):
    """ "latest" and "protest" contain "test"; they are not test files."""
    assert not cs.is_test_path(path), path
    assert cs.language_for(path) is not None


# ----------------------------------------------------------- end to end


def test_scan_extracts_symbols_and_chunks(conn, tmp_path):
    (tmp_path / "widget.py").write_text(PY_SRC, encoding="utf-8")
    (tmp_path / "widget.ts").write_text(TS_SRC, encoding="utf-8")
    project = prepo.create(conn, Project(name="s", root_path=str(tmp_path)))
    scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=500
    )

    symbols = [
        m
        for m in mrepo.list_for_project(conn, project.id, limit=500)
        if m.extraction_method == "rule:code_symbols"
    ]
    assert len(symbols) >= 8
    assert all(m.type.value == "architecture" for m in symbols)

    # Source files are chunked by symbol, so each chunk has a real line range
    # and a name -- which is what makes it citable once retrieval lands.
    chunks = conn.execute(
        "SELECT heading_path, line_start, line_end FROM chunks ORDER BY ordinal"
    ).fetchall()
    assert chunks, "source file produced no chunks"
    assert all(c["line_start"] >= 1 and c["line_end"] >= c["line_start"] for c in chunks)
    assert any("Widget" in (c["heading_path"] or "") for c in chunks)
