"""Git metadata via the Git CLI.

CLAUDE.md requires the Git CLI and stable hashes. subprocess is invoked with an
argument list, never a shell string, and never with arguments derived from
scanned content or model output.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)
_TIMEOUT = 20


def _git(root: Path, *args: str) -> str | None:
    try:
        # S603/S607: using the Git CLI is a CLAUDE.md requirement. Arguments
        # are a fixed list, never a shell string, and `args` is only ever
        # literals from this module plus a path -- never scanned content or
        # model output. PATH lookup of "git" is intentional and portable.
        out = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *args],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("git.failed", args=args, error=str(exc))
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def is_repo(root: Path) -> bool:
    return _git(root, "rev-parse", "--is-inside-work-tree") == "true"


def head_commit(root: Path) -> str | None:
    return _git(root, "rev-parse", "HEAD")


def blob_hashes(root: Path) -> dict[str, str]:
    """rel_path -> git blob hash for tracked files. Empty outside a repo.

    Untracked files simply have no entry, which is exactly why content_hash and
    not the blob hash is the primary fingerprint (ADR-0005).
    """
    out = _git(root, "ls-files", "-s")
    if not out:
        return {}
    mapping: dict[str, str] = {}
    for line in out.splitlines():
        # <mode> <blob> <stage>\t<path>
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 2 and path:
            mapping[path] = parts[1]
    return mapping
