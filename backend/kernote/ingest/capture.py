"""Content-addressed capture of raw bytes (L1).

content_hash is SHA-256 over raw bytes, always present. It is the stable key
across Windows and Linux even when git's autocrlf would change a blob hash
(ADR-0005), and it is what makes a repeat scan a no-op.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from identify import identify


@dataclass(frozen=True)
class Capture:
    content_hash: str
    text: str | None
    byte_size: int
    encoding: str
    language: str | None


def capture_file(abs_path: Path) -> Capture:
    raw = abs_path.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()
    try:
        text: str | None = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            text, encoding = None, "binary"
    tags = identify.tags_from_path(str(abs_path))
    language = next(
        (
            t
            for t in sorted(tags)
            if t not in {"file", "text", "binary", "non-executable", "executable", "symlink"}
        ),
        None,
    )
    return Capture(content_hash, text, len(raw), encoding, language)
