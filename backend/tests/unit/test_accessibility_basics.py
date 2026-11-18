"""Two accessibility invariants that are cheap to check, so they are checked.

The audit found 18 aria attributes in the whole UI and six of eight screens
with none. Most of that was not a hard problem -- it was eight form controls
nobody had named and two screens with no heading, each of which takes one
line to fix and no time at all to reintroduce.

Deliberately narrow. This does not attempt to measure "accessible": it pins
the two defects that were actually present and would actually recur, in the
style of `test_shortcuts_are_real` and `test_accent_is_reserved`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"

CONTROL = re.compile(r"<(input|select|textarea)\b")


def _sources() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.tsx") if p.is_file())


def _tag_end(text: str, start: int) -> int:
    """Index just past the control's opening tag.

    Scanning to the next `>` is wrong, because inline arrow handlers
    (`onChange={(e) => ...}`) contain one. A fixed-size window is wrong too,
    and worse: it reaches into the *next* control and finds that one's
    `aria-label`, so the check silently passes on an unlabelled field. Both
    mistakes were made writing this file; the second was only caught by
    replanting a real defect and watching the test not fail.

    So: walk the characters, tracking brace depth and quotes, and stop at the
    first `>` that is genuinely at the end of the tag.
    """
    depth = 0
    quote = ""
    i = start
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = ""
        elif ch in "\"'`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0:
            return i + 1
        i += 1
    return len(text)


def _is_labelled(text: str, start: int) -> bool:
    """A control is named by its own aria-label, or by a <label> wrapping it."""
    tag = text[start : _tag_end(text, start)]
    if "aria-label" in tag or "aria-labelledby" in tag:
        return True
    before = text[max(0, start - 400) : start]
    return before.rfind("<label") > before.rfind("</label>")


def test_every_form_control_has_an_accessible_name():
    offenders = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for match in CONTROL.finditer(text):
            if not _is_labelled(text, match.start()):
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert not offenders, (
        "these controls have no accessible name -- add aria-label, or wrap "
        "them in a <label>: " + ", ".join(offenders)
    )


def test_screen_header_renders_a_real_heading():
    """The shared header is where most screens get their <h1>, so it must have one."""
    ui = (SRC / "components" / "ui.tsx").read_text(encoding="utf-8")
    header = ui[ui.index("export function ScreenHeader") :]
    # The function ends at a line that is exactly `}`. Searching for "\n}"
    # instead matches the `}) {` of the signature and truncates the body
    # before the heading, which made this test fail against correct code.
    body = header[: header.index("\n}\n")]
    assert "<h1" in body, "ScreenHeader renders no <h1>"


def test_every_screen_has_a_heading():
    """Screen readers navigate by heading; a screen without one has no entry point.

    Two ways to satisfy it, both real: a literal `<h1>` -- `sr-only` counts,
    since the Dashboard and the Knowledge Graph show their title in a panel
    header and the heading is the structure underneath -- or `ScreenHeader`,
    which renders one (pinned by the test above).
    """
    missing = [
        path.name
        for path in sorted((SRC / "screens").glob("*.tsx"))
        if not any(
            token in path.read_text(encoding="utf-8") for token in ("<h1", "<ScreenHeader")
        )
    ]
    assert not missing, f"screens with no heading: {', '.join(missing)}"


def test_focus_is_visible():
    """Nothing defined a focus ring, so keyboard users got the browser's --
    a thin dark outline on a near-black panel, effectively invisible."""
    css = (SRC / "index.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css, "no visible focus style is defined"
    assert ".skip-link" in css, "no skip link style is defined"
