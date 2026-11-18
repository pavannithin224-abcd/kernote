"""Where the application's own data files live, frozen or not.

A PyInstaller build unpacks its bundled data into a temporary directory and
points `sys._MEIPASS` at it. Anything found with `Path(__file__).parent`
therefore resolves to the wrong place -- or to nothing -- inside a packaged
app, which is how a bundle starts, fails to find its migrations, and exits
with a traceback the user cannot act on.

Five places read data relative to the source tree: the migrations, the
built frontend, the tree-sitter query files, the evaluation question set and
the repository root used by the agent integrations screen. All of them go
through here.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path | None:
    """The unpacked bundle directory, or None when running from source."""
    if not is_frozen():
        return None
    return Path(sys._MEIPASS)  # type: ignore[attr-defined]


def package_dir(relative: str) -> Path:
    """A directory shipped *inside* the `kernote` package.

    Migrations and tree-sitter queries sit beside the code they belong to,
    so the spec file bundles them under `kernote/...` and this resolves to
    the same place either way.
    """
    root = bundle_root()
    if root is not None:
        return root / "kernote" / relative
    return Path(__file__).resolve().parent / relative


def project_file(relative: str) -> Path:
    """A file shipped from the repository root, beside the package.

    The built frontend and the evaluation question set are not part of the
    Python package; they are bundled at the top of the archive.
    """
    root = bundle_root()
    if root is not None:
        return root / relative
    return Path(__file__).resolve().parents[2] / relative
