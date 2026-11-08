"""Line anchors are provenance. An off-by-one here corrupts every citation."""

import pytest

from kernote.ingest.normalize import split_markdown

DOC = """# Title

Intro paragraph.

## Setup

Install it:

```bash
pip install thing
```

## Notes

Last section.
"""


def test_line_ranges_point_at_their_own_heading():
    lines = DOC.splitlines()
    for section in split_markdown(DOC):
        if section.heading is None:
            continue
        actual = lines[section.line_start - 1]
        assert section.heading in actual, (
            f"section {section.heading!r} claims line {section.line_start} "
            f"but that line is {actual!r}"
        )


def test_ranges_are_within_the_document_and_ordered():
    total = len(DOC.splitlines())
    sections = split_markdown(DOC)
    assert sections
    for s in sections:
        assert 1 <= s.line_start <= s.line_end <= total
    starts = [s.line_start for s in sections]
    assert starts == sorted(starts)


def test_heading_path_is_hierarchical():
    paths = {s.heading: s.heading_path for s in split_markdown(DOC)}
    assert paths["Setup"] == "Title > Setup"


def test_code_fence_line_range_is_the_fence():
    setup = next(s for s in split_markdown(DOC) if s.heading == "Setup")
    assert setup.code_blocks, "fenced block not captured"
    lang, code, start, end = setup.code_blocks[0]
    assert lang == "bash"
    assert "pip install thing" in code
    lines = DOC.splitlines()
    assert lines[start - 1].startswith("```")


def test_empty_and_headingless_documents_do_not_crash():
    assert split_markdown("") == []
    assert len(split_markdown("Just a sentence, no headings.\n")) == 1


def test_crlf_document_keeps_correct_line_numbers():
    crlf = DOC.replace("\n", "\r\n")
    for section in split_markdown(crlf):
        if section.heading:
            assert section.heading in crlf.splitlines()[section.line_start - 1]


# ------------------------------------------- classifier word boundaries


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        # These three contain the letters a-d-r and were classified as
        # decisions by substring matching. Found by dogfooding.
        ("Quadratic scoring", "project_fact"),
        ("Squadron layout", "architecture"),
        # "Padre" must not trigger the a-d-r decision words; "configuration"
        # legitimately makes this a procedure.
        ("Padre configuration", "procedure"),
        ("Padre notes", "project_fact"),
        # Plurals must still match: a bare word boundary broke these.
        ("Conventions", "convention"),
        ("Decisions", "decision"),
        ("Gotchas", "gotcha"),
        # Genuine signals must still work.
        ("ADR-0015 applied", "decision"),
        ("Decision: use Postgres", "decision"),
        ("Setup", "procedure"),
        ("Architecture", "architecture"),
        ("Known gotcha", "gotcha"),
        ("Conventions", "convention"),
        ("Overview of parts", "architecture"),
    ],
)
def test_heading_classification_uses_word_boundaries(heading, expected):
    from kernote.ingest.extract.markdown import _classify

    assert _classify(heading).value == expected
