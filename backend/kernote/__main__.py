"""Entry point for `python -m kernote` and for the packaged binary.

Starts the desktop window when one can be opened and serves in the terminal
when it cannot (ADR-0042), which is the same behaviour either way -- a
packaged build on a headless machine should still run, and say where.
"""

from __future__ import annotations

import sys

# Absolute, not relative: as a PyInstaller entry script this module runs as
# `__main__` with no package context, and a relative import fails outright
# with "attempted relative import with no known parent package". The
# absolute form works both frozen and under `python -m kernote`.
from kernote.desktop import main

if __name__ == "__main__":
    sys.exit(main())
