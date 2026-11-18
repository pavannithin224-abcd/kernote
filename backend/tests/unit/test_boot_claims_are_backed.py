"""The startup screen may not claim a service is ready without checking it.

`design/STARTUP_ANIMATION_BRIEF.md` asked for five status lines and forbade
showing OK before the corresponding service is ready. Three of the five had
nothing behind them: there is no memory-engine *process* (it is library code
in the same process), "local services" is the API that already answered, and
"retrieval index" conflates FTS5 -- which exists as soon as the schema does --
with semantic search, which is opt-in and legitimately absent.

So the screen prints the lines that have a real signal. These tests exist
because the tempting edit is to add the missing three back as decoration: five
green ticks look better than three honest ones, and nothing in a type checker
objects. Same reasoning as `test_accent_is_reserved`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOOT = ROOT / "frontend" / "src" / "components" / "Boot.tsx"
MAIN = ROOT / "frontend" / "src" / "main.tsx"

# Labels with no readiness signal behind them in this architecture.
UNBACKED = ("MEMORY ENGINE", "LOCAL SERVICES", "RETRIEVAL INDEX")


def test_the_boot_screen_names_no_unbacked_service():
    source = BOOT.read_text(encoding="utf-8")
    # Only what is rendered counts; the module docstring discusses these by
    # name precisely to explain why they are absent.
    body = re.sub(r"/\*\*.*?\*/", "", source, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    for label in UNBACKED:
        assert label not in body, (
            f"{label!r} is rendered by the boot screen, but nothing checks it. "
            "Either give it a real signal or leave it out."
        )


def test_the_semantic_line_is_gated_on_usable():
    """`off` is a correct state, not a failure -- and not an OK either."""
    body = BOOT.read_text(encoding="utf-8")
    assert "e.usable" in body, (
        "the semantic index line must branch on the embedding status's "
        "`usable` flag; printing OK regardless is the dishonesty the product "
        "argues against"
    )
    assert "'off'" in body, "there must be a non-OK state for a disabled index"


def test_the_reveal_cannot_run_on_navigation():
    """It sits above the router, so a route change cannot remount it.

    This is the whole mechanism for "startup or reload only" -- there is no
    flag and no sessionStorage to inspect. If Boot is ever moved inside the
    router, it would replay on every internal navigation.
    """
    main = MAIN.read_text(encoding="utf-8")
    assert "<Boot" in main, "Boot is not mounted in main.tsx"
    boot_at = main.index("<Boot")
    router_at = main.index("<BrowserRouter")
    assert boot_at < router_at, (
        "Boot must be mounted above <BrowserRouter>; inside the router it "
        "would replay on internal navigation"
    )


def test_reduced_motion_gets_the_end_frame():
    """The repo's rule: finished state is the base state.

    The graph is the only part that cannot be shown statically, so it is the
    only part withheld. The wordmark and the status lines must render either
    way -- never a blank frame waiting for an animation that will not play.
    """
    body = BOOT.read_text(encoding="utf-8")
    assert "{!reducedMotion && (" in body, "the graph should be withheld under reduced motion"
    # The wordmark and lines render unconditionally, with the animation class
    # applied only when motion is allowed.
    assert "reducedMotion ? 'boot-word' : 'boot-word boot-word-in'" in body
    assert "reducedMotion ? 'boot-lines' : 'boot-lines boot-lines-in'" in body

    css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    block = css[css.index("@media (prefers-reduced-motion: no-preference)") :]
    for keyframe in ("boot-node-in", "boot-draw", "boot-word-in"):
        assert keyframe in block, f"{keyframe} must only apply under no-preference"
