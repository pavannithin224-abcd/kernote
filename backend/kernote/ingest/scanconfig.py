"""What a project wants scanned, and what it does not (the project contract).

Three layers, merged in this order, each recorded so the effective result can
be explained rather than merely obeyed:

1. **Built-in defaults** — the allowlist in `walker.py`.
2. **`.kernote.toml` in the repository root** — the project's declared intent,
   versioned with the code and reviewable in a pull request. Kernote only ever
   *reads* it; scanning stays read-only and nothing here writes to a user's
   repository.
3. **A per-project override stored in Kernote** — a local adjustment, the way
   `.git/info/exclude` is local next to a shared `.gitignore`. Editable from
   Settings, so trying an exclusion does not require a commit.

`.kernoteignore` is also read, as a list of exclude patterns, because the
walker already honoured that file before this module existed.

**Precedence, and what configuration cannot do.** Exclude always beats include:
the safe direction wins when a path matches both. Include widens *only* the
allowlist decision — the question "is this a kind of file Kernote reads?" It
cannot override:

* a **secret** refusal, by filename or by content;
* **`.gitignore`**, which the project contract requires be respected, so there is
  deliberately no option to disable it;
* the **size** limit or the **binary** check.

That ordering is the whole point: a configuration file in a repository is
untrusted input, and it must not be able to talk Kernote into reading a private
key.
"""

from __future__ import annotations

import json
import sqlite3
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pathspec
import structlog

log = structlog.get_logger(__name__)

CONFIG_FILENAME = ".kernote.toml"
IGNORE_FILENAME = ".kernoteignore"

# A pattern list long enough to be a mistake rather than an intention.
_MAX_PATTERNS = 500


class ScanConfigError(ValueError):
    """Malformed configuration. Raised, never swallowed: a config the user
    believes is in force but which failed to parse is worse than an error."""


@dataclass(frozen=True)
class ScanConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    """Where each layer came from, for display: a path, or "project override"."""

    notes: tuple[str, ...] = field(default=())
    """Anything the user should know, such as a config file that was ignored."""

    @property
    def include_spec(self) -> pathspec.PathSpec | None:
        return _spec(self.include)

    @property
    def exclude_spec(self) -> pathspec.PathSpec | None:
        return _spec(self.exclude)

    def matches_include(self, rel_path: str) -> bool:
        spec = self.include_spec
        return bool(spec and spec.match_file(rel_path))

    def matches_exclude(self, rel_path: str) -> bool:
        spec = self.exclude_spec
        return bool(spec and spec.match_file(rel_path))

    def to_dict(self) -> dict:
        return {
            "include": list(self.include),
            "exclude": list(self.exclude),
            "sources": list(self.sources),
            "notes": list(self.notes),
        }


def _spec(patterns: tuple[str, ...]) -> pathspec.PathSpec | None:
    if not patterns:
        return None
    # gitwildmatch so `docs/**/*.json`, `!keep.json` and directory patterns mean
    # what a developer already expects them to mean.
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _clean(values: object, *, where: str, key: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ScanConfigError(f"{where}: [scan] {key} must be a list of strings")
    out = tuple(v.strip() for v in values if v and v.strip())
    if len(out) > _MAX_PATTERNS:
        raise ScanConfigError(
            f"{where}: [scan] {key} has {len(out)} patterns, over the {_MAX_PATTERNS} limit"
        )
    return out


def from_file(root: Path) -> ScanConfig:
    """Read `.kernote.toml` and `.kernoteignore` from a repository root."""
    include: list[str] = []
    exclude: list[str] = []
    sources: list[str] = []
    notes: list[str] = []

    config_path = root / CONFIG_FILENAME
    if config_path.is_file():
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ScanConfigError(f"{CONFIG_FILENAME} could not be parsed: {exc}") from exc
        scan = data.get("scan", {})
        if not isinstance(scan, dict):
            raise ScanConfigError(f"{CONFIG_FILENAME}: [scan] must be a table")
        include += _clean(scan.get("include"), where=CONFIG_FILENAME, key="include")
        exclude += _clean(scan.get("exclude"), where=CONFIG_FILENAME, key="exclude")
        sources.append(CONFIG_FILENAME)
        unknown = sorted(set(scan) - {"include", "exclude"})
        if unknown:
            # Named rather than ignored, so a typo does not look like it worked.
            notes.append(
                f"{CONFIG_FILENAME}: ignored unknown [scan] key(s) {', '.join(unknown)}"
            )

    ignore_path = root / IGNORE_FILENAME
    if ignore_path.is_file():
        try:
            lines = ignore_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ScanConfigError(f"{IGNORE_FILENAME} could not be read: {exc}") from exc
        patterns = [
            line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
        ]
        if patterns:
            exclude += patterns
            sources.append(IGNORE_FILENAME)

    return ScanConfig(
        include=tuple(include),
        exclude=tuple(exclude),
        sources=tuple(sources),
        notes=tuple(notes),
    )


def load_override(conn: sqlite3.Connection, project_id: str) -> ScanConfig:
    row = conn.execute(
        "SELECT include_json, exclude_json FROM project_scan_config WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if row is None:
        return ScanConfig()
    return ScanConfig(
        include=tuple(json.loads(row["include_json"])),
        exclude=tuple(json.loads(row["exclude_json"])),
        sources=("project override",),
    )


def save_override(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    include: list[str],
    exclude: list[str],
) -> ScanConfig:
    """Store the local adjustment. Validated first; a bad pattern is refused."""
    checked_include = _clean(include, where="project override", key="include")
    checked_exclude = _clean(exclude, where="project override", key="exclude")
    for patterns, key in ((checked_include, "include"), (checked_exclude, "exclude")):
        try:
            _spec(patterns)
        except Exception as exc:  # noqa: BLE001 - pathspec raises assorted types
            raise ScanConfigError(
                f"project override: {key} is not a valid pattern: {exc}"
            ) from exc

    from ..db.connection import transaction
    from ..domain.models import utc_now

    with transaction(conn):
        conn.execute(
            "INSERT INTO project_scan_config(project_id,include_json,exclude_json,updated_at) "
            "VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET "
            "include_json=excluded.include_json, exclude_json=excluded.exclude_json, "
            "updated_at=excluded.updated_at",
            (
                project_id,
                json.dumps(list(checked_include)),
                json.dumps(list(checked_exclude)),
                utc_now(),
            ),
        )
    return ScanConfig(
        include=checked_include, exclude=checked_exclude, sources=("project override",)
    )


def effective(
    conn: sqlite3.Connection | None, project_id: str | None, root: Path
) -> ScanConfig:
    """The configuration a scan will actually use, with its provenance."""
    from_repo = from_file(root)
    override = (
        load_override(conn, project_id) if conn is not None and project_id else ScanConfig()
    )
    merged = ScanConfig(
        include=from_repo.include + override.include,
        exclude=from_repo.exclude + override.exclude,
        sources=from_repo.sources + override.sources,
        notes=from_repo.notes + override.notes,
    )
    log.info(
        "scanconfig.effective",
        project_id=project_id,
        include=len(merged.include),
        exclude=len(merged.exclude),
        sources=list(merged.sources),
    )
    return merged
