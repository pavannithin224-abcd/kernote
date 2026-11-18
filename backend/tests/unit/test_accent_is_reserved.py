"""The accent colour fills one control per screen, and nothing else.

Reference reel 6 (`design/VISUAL_PASS.md`): *two base colours do 90% of the
work, the weird one only goes on the button you want pressed.* Before this was
enforced, `--accent` appeared in twelve places across every screen -- the
active nav item, six primary buttons, inline file paths, MCP tool names, the
type badge and a panel border. A colour doing nine jobs signals none of them;
on the Maintenance Center the accent was at once the nav state, the Analyze
button, a panel border and every citation, so nothing said "press me".

This is a repo invariant rather than a style note, for the same reason
`test_text_io_is_explicit` is: it was true once and drifted. The rule is
checkable in one grep, so it is checked.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"

# The only file allowed to paint something with the action colour.
BUTTON = SRC / "components" / "ui.tsx"


def _sources() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.tsx") if p.is_file())


# A filled accent surface, in any spacing or quoting.
FILLED = re.compile(r"background(?:-color)?\s*:\s*['\"]?\s*var\(--accent\)")

# The neon layer (2026-11-14) added an indirection: `.neon-bar` fills with
# whatever `--neon` names, so binding `--neon` to the accent fills a surface
# with it without the word "background" appearing anywhere nearby. Closing
# that hole is the point -- a guard a later refactor can walk around is worse
# than no guard, because it still reads as enforcement.
NEON_ACCENT = re.compile(r"--neon'?\s*:\s*['\"]?\s*var\(--accent\)")


def test_only_the_button_component_fills_with_the_accent_colour():
    """Re-expressed on 2026-11-14, when cyan became the brand hue too.

    The original rule was "nothing but Button may name `--accent`", which was
    right while the accent was a blue used only on buttons. In the approved
    identity cyan is also the brand colour: the `note_` of the wordmark, the
    rule beside a section heading, the line marking the active nav item. A
    blanket ban would have meant dropping either the identity or the test, and
    `design/DASHBOARD_BRIEF.md` says to do neither.

    What made the old accent useless was *filling* nine different things with
    it, so nothing read as pressable -- not naming it. That is the part worth
    keeping, now stated precisely: cyan may draw a line or set type anywhere,
    but only `Button` may fill a surface with it.
    """
    offenders = []
    for path in _sources():
        if path == BUTTON:
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FILLED.search(line) or NEON_ACCENT.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{index}")
    assert not offenders, (
        "only the Button component may fill a surface with var(--accent); a screen "
        "that needs a primary action should render <Button primary>. Offenders: "
        + ", ".join(offenders)
    )


def test_no_screen_has_two_primary_actions():
    """Two primaries is the same failure as none: nothing stands out."""
    pattern = re.compile(r"<Button\b[^>]*\bprimary\b", re.S)
    for path in sorted((SRC / "screens").glob("*.tsx")):
        count = len(pattern.findall(path.read_text(encoding="utf-8")))
        assert count <= 1, f"{path.name} has {count} primary actions"


def test_every_theme_defines_every_token():
    """A token missing from one theme is invisible until someone switches.

    `--accent-contrast` was added because white-on-accent measured 2.41:1 in
    dark mode, below even the 3:1 bar for interface elements. A token that
    exists in only one block would reintroduce exactly that.
    """
    css = (SRC / "index.css").read_text(encoding="utf-8")
    blocks = re.findall(r":root(?:\[[^\]]*\])?(?::not\([^)]*\))?\s*\{([^}]*)\}", css)
    assert len(blocks) >= 3, "expected a light block and two dark ones"
    sets = [set(re.findall(r"(--[a-z-]+)\s*:", b)) for b in blocks]
    expected = sets[0]
    assert len(expected) >= 12, "the light theme looks incomplete"
    for index, found in enumerate(sets[1:], start=1):
        missing = expected - found
        assert not missing, f"theme block {index} is missing {sorted(missing)}"
