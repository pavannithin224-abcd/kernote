"""Safe, read-only file discovery.

This module is a safety boundary. It has no write path to the project tree.
It decides what Kernote is even allowed to read, and every refusal is recorded
with a reason so the UI can always answer "why was this file not imported".

Stage 2 enforces path-based refusal. Content-level secret detection
(detect-secrets, ADR-0013) lands in Stage 3; until then the deny-list below is
the guard, and it is deliberately broad.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

import pathspec
from identify import identify

from ..domain.models import SkipReason

# Seeded from github-linguist's vendor.yml / documentation.yml conventions
# rather than invented (ADR-0013).
EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        "out",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "vendor",
        "third_party",
        "coverage",
        ".idea",
        ".vscode",
        ".tox",
        ".eggs",
        "site-packages",
        ".terraform",
        ".cache",
    }
)

# Never read these, regardless of allowlist. Path-based first line of defence.
SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "*.jks",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "*.ppk",
    "credentials",
    "credentials.*",
    "*credentials*.json",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "*.secret",
    "secrets.*",
    ".htpasswd",
    "*.keytab",
)

# Stage 2 scope: documentation and configuration. Source files arrive Stage 3.
ALLOWED_NAMES: frozenset[str] = frozenset(
    {
        "readme",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "contributing.md",
        "changelog.md",
        "license",
        "license.md",
        "claude.md",
        "agents.md",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "tsconfig.json",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "makefile",
        "justfile",
        "procfile",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
    }
)
ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
    }
)


@dataclass(frozen=True)
class Found:
    rel_path: str
    abs_path: Path


@dataclass(frozen=True)
class Skipped:
    rel_path: str
    reason: SkipReason


def _gitignore_spec(root: Path) -> pathspec.PathSpec | None:
    """Real .gitignore semantics via pathspec: negation, **, dir-only, precedence.

    Hand-rolling this is how a scanner quietly ingests a file the user excluded.
    """
    patterns: list[str] = []
    for name in (".gitignore", ".kernoteignore"):
        f = root / name
        if f.is_file():
            try:
                patterns.extend(f.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
    if not patterns:
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _looks_secret(name: str) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatch(low, pat) for pat in SECRET_PATTERNS)


def _allowlisted(path: Path) -> bool:
    return path.name.lower() in ALLOWED_NAMES or path.suffix.lower() in ALLOWED_SUFFIXES


def walk(
    root: Path, *, max_file_bytes: int, max_files: int, respect_gitignore: bool = True
) -> tuple[list[Found], list[Skipped]]:
    root = root.resolve()
    spec = _gitignore_spec(root) if respect_gitignore else None
    found: list[Found] = []
    skipped: list[Skipped] = []

    for abs_path in sorted(root.rglob("*")):
        if len(found) >= max_files:
            break
        try:
            rel = abs_path.relative_to(root)
        except ValueError:
            continue
        # POSIX-style relative strings internally; pathlib only at the edges (R4).
        rel_str = rel.as_posix()

        if abs_path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
            continue  # not recorded: excluding build dirs wholesale is not news
        if abs_path.is_symlink():
            skipped.append(Skipped(rel_str, SkipReason.EXCLUDED))
            continue
        if _looks_secret(abs_path.name):
            # Recorded but NEVER read.
            skipped.append(Skipped(rel_str, SkipReason.SECRET_SUSPECTED))
            continue
        if spec is not None and spec.match_file(rel_str):
            skipped.append(Skipped(rel_str, SkipReason.GITIGNORED))
            continue
        if not _allowlisted(abs_path):
            skipped.append(Skipped(rel_str, SkipReason.NOT_ALLOWLISTED))
            continue
        try:
            size = abs_path.stat().st_size
        except OSError:
            skipped.append(Skipped(rel_str, SkipReason.UNREADABLE))
            continue
        if size > max_file_bytes:
            skipped.append(Skipped(rel_str, SkipReason.TOO_LARGE))
            continue
        # identify (pre-commit's library) rather than our own binary sniffing.
        try:
            tags = identify.tags_from_path(str(abs_path))
        except (OSError, ValueError):
            skipped.append(Skipped(rel_str, SkipReason.UNREADABLE))
            continue
        if "binary" in tags:
            skipped.append(Skipped(rel_str, SkipReason.BINARY))
            continue

        found.append(Found(rel_str, abs_path))

    return found, skipped
