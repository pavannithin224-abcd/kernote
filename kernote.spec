# PyInstaller spec for a self-contained Kernote.
#
# Build with:  backend/.venv/bin/pyinstaller kernote.spec
#
# Three things make this more than the default template.
#
# **Data files.** Five paths are read relative to the source tree at runtime
# (migrations, the built UI, tree-sitter queries, the evaluation question
# set). They are bundled here and resolved through `kernote/resources.py`,
# which knows about `sys._MEIPASS`. Without that pairing the bundle starts,
# cannot find its migrations, and dies with a traceback the user cannot act
# on.
#
# **Native packages.** `onnxruntime` and `tree_sitter_language_pack` ship
# compiled libraries that PyInstaller's import analysis does not see,
# because they are loaded by path at runtime rather than imported.
# `collect_all` takes the whole package.
#
# **What is deliberately absent.** The embedding model is a ~90 MB download
# that is opt-in (ADR-0023); bundling it would treble the installer and
# switch on by default a feature the product keeps off. It is fetched at
# first use into the user's cache, exactly as from source.

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("backend/kernote/db/migrations", "kernote/db/migrations"),
    ("backend/kernote/ingest/extract/queries", "kernote/ingest/extract/queries"),
    ("frontend/dist", "frontend/dist"),
    ("eval/questions.json", "eval"),
]
binaries = []
hiddenimports = [
    # uvicorn resolves these by name at runtime, so nothing imports them
    # statically and the analysis misses them.
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]
hiddenimports += collect_submodules("kernote")
# FastMCP is imported by name inside build_server(), so analysis cannot see it.
hiddenimports += collect_submodules("mcp")

# pywebview picks its platform backend by name at runtime, so it has to be
# collected whole or the packaged app silently falls back to "no window".
for package in (
    "onnxruntime",
    "tree_sitter_language_pack",
    "tree_sitter",
    "fastembed",
    "webview",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # noqa: BLE001 - an absent optional package is not fatal
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

_EXCLUDES = [
    # Test and build machinery has no business in a shipped binary.
    "pytest",
    "ruff",
    "PyInstaller",
    # Pulled in by the MCP SDK's OAuth modules, which the stdio transport never
    # reaches. ~10 MB. (PIL looks equally unused but cannot go: fastembed
    # imports it unconditionally, so excluding it breaks `import fastembed`.)
    "cryptography",
    # Pillow's AVIF codec: 7.9 MB, loaded lazily and optionally by
    # Image.init(), and nothing here opens an image. Verified that
    # `import fastembed` is unaffected.
    "PIL.AvifImagePlugin",
    "PIL._avif",
]


def _analysis(entry):
    return Analysis(
        [entry],
        pathex=["backend"],
        binaries=binaries,
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        excludes=_EXCLUDES,
        noarchive=False,
    )


# Two programs, one set of libraries.
#
#   kernote.exe      the app. Windowed: no black terminal behind it.
#   kernote-mcp.exe  what a coding agent launches. It MUST be a console
#                    program: MCP over stdio *is* stdin/stdout, and a windowed
#                    Windows process has neither, so the app itself cannot be
#                    the server.
#
# MERGE makes the second analysis reference the first's libraries instead of
# copying them, so the helper costs kilobytes rather than another bundle.
a = _analysis("backend/kernote/__main__.py")
m = _analysis("backend/kernote_mcp_entry.py")
MERGE((a, "kernote", "kernote"), (m, "kernote-mcp", "kernote-mcp"))

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="kernote",
    # Failures that used to be printed now reach the user through a dialog and
    # <data_dir>/logs (see desktop._say and logging._fallback_log_file).
    # `KERNOTE_CONSOLE=1` builds a console variant for debugging a bad bundle.
    console=bool(os.environ.get("KERNOTE_CONSOLE")),
    icon="packaging/kernote.ico",
    version="packaging/version_info.txt",
    disable_windowed_traceback=False,
)

pyz_mcp = PYZ(m.pure)
exe_mcp = EXE(
    pyz_mcp,
    m.scripts,
    [],
    exclude_binaries=True,
    name="kernote-mcp",
    console=True,
    icon="packaging/kernote.ico",
    version="packaging/version_info.txt",
)

coll = COLLECT(
    exe,
    exe_mcp,
    a.binaries,
    a.datas,
    m.binaries,
    m.datas,
    strip=False,
    upx=False,
    name="kernote",
)
