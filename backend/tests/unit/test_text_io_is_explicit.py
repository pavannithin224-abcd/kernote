"""Every text read and write names its encoding.

Found by the first native-Windows run. Python defaults `open` and
`Path.read_text` to the *locale* encoding, which on this Windows machine is
cp1252 — so reading our own `docs/ARCHITECTURE.md` raised
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x90`, because the file
contains box-drawing characters. Em-dashes, accented names, `µm` and `log₁₀`
all do the same thing, and our documentation and fixtures are full of them.

Worse than the error is the near miss: a byte that cp1252 *can* map decodes
silently into mojibake, so a migration comment or an extracted memory would be
quietly wrong rather than loudly broken.

The scan path itself was already safe — `capture.py` reads bytes and decodes
UTF-8 explicitly — so this never corrupted a user's content. It broke our own
files.

Ruff's `PLW1514` covers this but is preview-only, so this test stands in for
it: deterministic, and it fails with the offending location rather than a rule
code.
"""

from __future__ import annotations

import re
from pathlib import Path

# The repository root, so `scripts/` is covered too and not just the package.
ROOT = Path(__file__).resolve().parents[3]
CALL = re.compile(r"\.(read_text|write_text)\(")


def _call_args(source: str, open_paren: int) -> str:
    """The text between a call's parentheses, skipping nested ones."""
    depth, index, in_string, quote = 1, open_paren, False, ""
    while index < len(source) and depth:
        char = source[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                in_string = False
        elif char in "\"'":
            in_string, quote = True, char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return source[open_paren : index - 1]


def test_no_text_io_relies_on_the_locale_encoding():
    offenders: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        if ".venv" in path.parts or "node_modules" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for match in CALL.finditer(source):
            if "encoding=" in _call_args(source, match.end()):
                continue
            line = source[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert not offenders, (
        "these read or write text using the locale encoding, which is cp1252 on "
        "Windows and breaks on any character outside it: " + ", ".join(offenders)
    )
