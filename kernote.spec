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

for package in ("onnxruntime", "tree_sitter_language_pack", "tree_sitter", "fastembed"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # noqa: BLE001 - an absent optional package is not fatal
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["backend/kernote/__main__.py"],
    pathex=["backend"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[
        # Test and build machinery has no business in a shipped binary.
        "pytest",
        "ruff",
        "PyInstaller",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="kernote",
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="kernote",
)
