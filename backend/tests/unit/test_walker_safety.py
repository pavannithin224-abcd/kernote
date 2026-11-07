"""The scanner is a safety boundary. These tests are about refusal.

Invariant 7: scanning a directory containing a .env and a private key imports
neither. These exercise our *wiring* of pathspec and identify, not a
reimplementation of them (ADR-0013).
"""

from kernote.domain.models import SkipReason
from kernote.ingest.walker import walk


def _walk(root):
    return walk(root, max_file_bytes=1_000_000, max_files=5000)


def test_invariant_7_secrets_are_never_read(hostile_repo):
    found, skipped = _walk(hostile_repo)
    found_names = {f.rel_path for f in found}
    for secret in (".env", "server.pem", "id_rsa", "credentials.json"):
        assert secret not in found_names, f"{secret} was going to be READ"

    refused = {s.rel_path for s in skipped if s.reason is SkipReason.SECRET_SUSPECTED}
    assert {".env", "server.pem", "id_rsa", "credentials.json"} <= refused


def test_gitignored_files_are_excluded_with_a_reason(hostile_repo):
    found, skipped = _walk(hostile_repo)
    assert "ignored.md" not in {f.rel_path for f in found}
    assert "ignored.md" in {s.rel_path for s in skipped if s.reason is SkipReason.GITIGNORED}


def test_binary_and_oversized_are_skipped(hostile_repo):
    _, skipped = _walk(hostile_repo)
    by_reason: dict[str, set[str]] = {}
    for s in skipped:
        by_reason.setdefault(s.reason.value, set()).add(s.rel_path)
    binary_or_unlisted = by_reason.get("binary", set()) | by_reason.get(
        "not_allowlisted", set()
    )
    assert "logo.png" in binary_or_unlisted
    assert "big.md" in by_reason.get("too_large", set())


def test_build_dirs_are_not_walked(hostile_repo):
    found, _ = _walk(hostile_repo)
    assert not any(f.rel_path.startswith("node_modules/") for f in found)


def test_crlf_file_is_readable(hostile_repo):
    """Windows line endings must not make a file unreadable (risk R5)."""
    found, _ = _walk(hostile_repo)
    assert "crlf.md" in {f.rel_path for f in found}


def test_every_refusal_has_a_reason(hostile_repo):
    _, skipped = _walk(hostile_repo)
    assert skipped, "nothing was skipped in the hostile fixture"
    assert all(isinstance(s.reason, SkipReason) for s in skipped)


def test_walker_does_not_write_to_the_project(hostile_repo):
    before = {p.name: p.stat().st_mtime_ns for p in hostile_repo.rglob("*") if p.is_file()}
    _walk(hostile_repo)
    after = {p.name: p.stat().st_mtime_ns for p in hostile_repo.rglob("*") if p.is_file()}
    assert before == after, "scanning modified the project tree"
