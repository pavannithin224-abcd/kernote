"""A keyboard hint drawn on screen must correspond to a key that works.

The sidebar shipped a `⌘1` badge that nothing handled: decoration shaped
like a feature, in a product whose whole argument is that it does not do
that. It survived a redesign, a review and a visual sign-off, because a
plausible-looking affordance is exactly the thing nobody checks.

Same family as `test_accent_is_reserved` and `test_boot_claims_are_backed`:
cheap to check, so it is checked.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"

# A rendered key hint: ⌘K, ⌃K, Ctrl+K and friends, inside JSX text.
HINT = re.compile(r"[⌘⌃]([A-Za-z0-9])|Ctrl\+([A-Za-z0-9])")


def _tsx() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.tsx") if p.is_file())


BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)


def _without_comments(text: str) -> str:
    """Comments explain history; they are not drawn on screen.

    Both forms have to go, and the JSX one is the reason this exists: a
    `{/* ... ⌘1 ... */}` note explaining why that hint was removed read as a
    live hint and failed this test against correct code.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))


def _rendered_hints() -> dict[str, list[str]]:
    """Key letters that appear as on-screen hints, by file."""
    found: dict[str, list[str]] = {}
    for path in _tsx():
        body = _without_comments(path.read_text(encoding="utf-8"))
        for match in HINT.finditer(body):
            key = (match.group(1) or match.group(2)).lower()
            found.setdefault(key, []).append(f"{path.relative_to(ROOT)}")
    return found


def _handled_keys() -> set[str]:
    """Keys some handler actually inspects."""
    keys: set[str] = set()
    for path in [*_tsx(), *sorted(SRC.rglob("*.ts"))]:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"key\.toLowerCase\(\)\s*===\s*'([a-z0-9])'", text):
            keys.add(match.group(1))
        for match in re.finditer(r"\.key\s*===\s*'([A-Za-z0-9])'", text):
            keys.add(match.group(1).lower())
    return keys


def test_every_rendered_shortcut_hint_has_a_handler():
    hints = _rendered_hints()
    handled = _handled_keys()
    dangling = {key: files for key, files in hints.items() if key not in handled}
    assert not dangling, (
        "these keyboard hints are drawn but nothing handles them: "
        + "; ".join(f"{k} in {', '.join(sorted(set(v)))}" for k, v in dangling.items())
    )


def test_no_hint_claims_a_browser_tab_shortcut():
    """⌘1-⌘9 switch tabs in a browser.

    Kernote runs in a browser for most people today, so claiming those keys
    would either not work or would steal something the user expects. The
    palette uses ⌘K, which collides with nothing.
    """
    offenders = [
        f"{key}: {', '.join(sorted(set(files)))}"
        for key, files in _rendered_hints().items()
        if key.isdigit()
    ]
    assert not offenders, "numeric shortcut hints found: " + "; ".join(offenders)
