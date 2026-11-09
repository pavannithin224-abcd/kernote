"""Regression tests for the Stage 3 defect sweep.

Each test corresponds to a bug confirmed by probing before it was fixed.
"""

import pytest

from kernote.db.repositories import memories as mrepo
from kernote.db.repositories import projects as prepo
from kernote.domain.models import ClaimKind, Memory, MemoryType, Project, SourceRef
from kernote.ingest.secrets import (
    SecretHit,
    classify,
    key_names_a_credential,
    read_lines,
    scan_path,
    scanning_session,
    value_looks_like_credential,
)


def _memory(project_id: str, **over) -> Memory:
    base = {
        "project_id": project_id,
        "type": MemoryType.DECISION,
        "title": "T",
        "content": "C",
        "claim_kind": ClaimKind.SOURCE_FACT,
        "importance": 0.5,
        "importance_reason": "r",
        "confidence": 0.5,
        "confidence_reason": "r",
        "extraction_method": "manual",
        "source_refs": [SourceRef(user_note="n")],
    }
    base.update(over)
    return Memory(**base)


# ------------------- a real credential must not be stored with a warning


@pytest.mark.parametrize(
    "line",
    [
        'DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"',
        'API_SECRET = "9f8e7d6c5b4a3f2e1d0c"',
        'secret_key = "a3f9e2b7c1d4e6f8a0b2c4d6e8f0a2b4"',
        "password: 'Xk92Lm04Qp77Zr'",
    ],
)
def test_credential_shaped_values_are_detected(line):
    assert value_looks_like_credential(line), line


@pytest.mark.parametrize(
    "line",
    [
        # Kernote's own vocabulary, which the keyword detector flags.
        'SECRET_SUSPECTED = "secret_suspected"',
        "secret_reason = 'refused as possible secret never read'",
        # Placeholders and templates.
        'API_KEY = "your-api-key-here"',
        'TOKEN = "example-token-value"',
        'PASSWORD = "${DB_PASSWORD}"',
        'PASSWORD = "<your-password>"',
        'TOKEN = "changeme"',
        # Too short, or no literal at all.
        'PASSWORD = "abc"',
        'PASSWORD = os.environ["DB_PASSWORD"]',
    ],
)
def test_non_credential_values_are_not_flagged(line):
    assert not value_looks_like_credential(line), line


def test_real_password_file_is_refused_not_merely_warned(conn, tmp_path):
    """The gap this closes: a keyword hit alone only warned, so a genuine
    `DB_PASSWORD = "..."` was imported into the vault."""
    from kernote.ingest.pipeline import scan_project

    (tmp_path / "config.py").write_text('DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"\n')
    project = prepo.create(conn, Project(name="s", root_path=str(tmp_path)))
    result = scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    assert [s.rel_path for s in result.skipped if s.reason.value == "secret_suspected"] == [
        "config.py"
    ]
    leaked = conn.execute(
        "SELECT COUNT(*) FROM source_captures WHERE text LIKE '%Tr0ub4dor%'"
    ).fetchone()[0]
    assert leaked == 0


def test_our_own_vocabulary_file_is_still_imported(conn, tmp_path):
    """The other direction: the fix must not re-break what two-tier solved."""
    from kernote.ingest.pipeline import scan_project

    (tmp_path / "models.py").write_text(
        'SECRET_SUSPECTED = "secret_suspected"\n\n\ndef classify(v):\n    return v\n'
    )
    project = prepo.create(conn, Project(name="s", root_path=str(tmp_path)))
    result = scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    assert not [s for s in result.skipped if s.reason.value == "secret_suspected"]
    assert "models.py" in {w.rel_path for w in result.secret_warnings}


def test_classify_without_source_lines_still_refuses_formats(tmp_path):
    """`lines` is optional; rule 1 must work without it."""
    f = tmp_path / "x.md"
    f.write_text("# D\n\n    ghp_16C7e42F292c6912E7710c838347Ae178B4a\n")
    with scanning_session():
        hits = scan_path(f)
        refuse_no_lines, _ = classify(hits)
        refuse_lines, _ = classify(hits, read_lines(f))
    assert refuse_no_lines and refuse_lines


# ------------------- superseded records are not served as current


def test_superseded_memories_are_hidden_from_listings(conn):
    """MEMORY_MODEL.md: a replaced claim served next to its replacement is
    misleading. It stays fetchable by id (invariant 5)."""
    project = prepo.create(conn, Project(name="p", root_path="/tmp/kernote-sup"))
    old = mrepo.create(conn, _memory(project.id, title="Use SQLite"))
    _, new = mrepo.supersede(
        conn, old.id, _memory(project.id, title="Use Postgres"), reason="contention"
    )

    listed = {m.id for m in mrepo.list_for_project(conn, project.id)}
    assert new.id in listed
    assert old.id not in listed, "a superseded claim was served as current"

    # Still reachable three ways.
    assert mrepo.get(conn, old.id) is not None
    assert old.id in {
        m.id for m in mrepo.list_for_project(conn, project.id, include_inactive=True)
    }
    assert old.id in {
        m.id for m in mrepo.list_for_project(conn, project.id, status="superseded")
    }


def test_archived_memories_are_hidden_but_reachable(conn):
    project = prepo.create(conn, Project(name="p", root_path="/tmp/kernote-arch"))
    memory = mrepo.create(conn, _memory(project.id, title="Temporary note"))
    mrepo.archive(conn, memory.id)
    assert memory.id not in {m.id for m in mrepo.list_for_project(conn, project.id)}
    assert memory.id in {
        m.id for m in mrepo.list_for_project(conn, project.id, include_inactive=True)
    }
    assert mrepo.get(conn, memory.id) is not None


def test_api_include_inactive(client, demo_repo):
    r = client.post("/api/v1/projects", json={"name": "d", "root_path": demo_repo})
    pid = r.json()["id"]
    client.post(f"/api/v1/projects/{pid}/scan")
    mid = client.get(f"/api/v1/projects/{pid}/memories").json()[0]["id"]
    client.post(f"/api/v1/memories/{mid}/archive")

    default = {m["id"] for m in client.get(f"/api/v1/projects/{pid}/memories").json()}
    assert mid not in default
    with_inactive = {
        m["id"]
        for m in client.get(f"/api/v1/projects/{pid}/memories?include_inactive=true").json()
    }
    assert mid in with_inactive


# ------------------- prose is not a command list


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("pytest -q\nruff check .", True),
        ("make build\nmake test\nmake deploy", True),
        ("We decided to use Postgres.\nIt handles concurrent writes.", False),
        ("This is one long explanatory sentence about the setup process.", False),
        ("", False),
    ],
)
def test_command_shape_gate(content, expected):
    """A `manual` procedure memory is free text; comparing prose line-by-line
    as commands produced nonsense command sets."""
    from kernote.maintain.conflicts import _looks_like_commands

    assert _looks_like_commands(content) is expected


# ------- prose about credentials is not a credential (self-reference guard)


@pytest.mark.parametrize(
    "line",
    [
        # These are lines from Kernote's own docs and comments. The first
        # strict version of the value-shape heuristic refused
        # `docs/DECISIONS.md` for them, costing 23 decision memories -- and it
        # would cost the same to any project that documents its security
        # decisions.
        'credentials and the demo `.env`. A real `password = "hunter2xyzABC"` with no',
        '# `DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"` was only warned about and stored, while',
        'The example below sets password = "Tr0ub4dor&3xKq9vZ" for illustration only',
    ],
)
def test_prose_discussing_credentials_is_not_a_credential(line):
    assert not value_looks_like_credential(line), line


@pytest.mark.parametrize(
    "line",
    [
        'DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"',
        "password: 'Xk92Lm04Qp77Zr'",
        '    secret_key = "a3f9e2b7c1d4e6f8a0b2c4d6e8f0a2b4"',
        'API_SECRET = "9f8e7d6c5b4a3f2e1d0c"  # production',
    ],
)
def test_terse_assignments_are_still_caught(line):
    """The prose guard must not swallow real assignments: a credential line is
    short, which is exactly what distinguishes it from a sentence."""
    assert value_looks_like_credential(line), line


def test_a_document_about_secrets_is_still_imported(conn, tmp_path):
    """End to end on the shape of our own decision log."""
    from kernote.ingest.pipeline import scan_project

    (tmp_path / "SECURITY.md").write_text(
        "# Security decisions\n\n"
        "## Status\n\nAccepted\n\n"
        "## Decision\n\n"
        'We refuse any file containing a credential. A real `password = "hunter2xyzABC"`\n'
        "with no recognisable format is imported with a warning instead.\n"
    )
    project = prepo.create(conn, Project(name="s", root_path=str(tmp_path)))
    result = scan_project(
        conn, project_id=project.id, root=tmp_path, max_file_bytes=1_000_000, max_files=50
    )
    assert not [
        s for s in result.skipped if s.reason.value == "secret_suspected"
    ], "a document discussing credentials was refused"
    assert mrepo.list_for_project(conn, project.id), "no memories extracted"


# ─── found by scanning a real data-heavy repository (ADR-0020c) ─────────────


def test_a_high_entropy_value_without_a_credential_key_only_warns():
    """A digest, a UUID, a git object id and an API token are the same shape.

    Scanning a real modelling repository refused 2918 of 2938 files on
    `Hex High Entropy String` alone -- including three of its seven Markdown
    documents -- because every hash in a JSON manifest is twenty-plus
    characters without a space. For a low-precision hit the *name* has to
    carry the signal.
    """
    digest = "a3f5c9e1b7d04a26f8c3b159e7a2d4068b1c5e9f3a7d2b6c8e0f4a1d9c7b3e52"
    for line in (f'"sha256": "{digest}"', f'checksum = "{digest}"', f'"curve_id": "{digest}"'):
        assert not key_names_a_credential(line), line
        # The value *is* credential-shaped; only the key name saves the file.
        assert value_looks_like_credential(line), line
        refuse, warn = classify(
            [SecretHit(line_number=1, detector="Hex High Entropy String")], [line]
        )
        assert not refuse, f"a checksum must not refuse the file: {line}"
        assert warn, "it must still be recorded for a human glance"


def test_a_high_entropy_value_under_a_credential_key_still_refuses():
    """The fix must not let a real secret through."""
    value = "a3f5c9e1b7d04a26f8c3b159e7a2d406"
    for line in (
        f'api_key = "{value}"',
        f'"access_token": "{value}"',
        f'DB_PASSWORD = "{value}"',
        f'client_secret: "{value}"',
        f'private_key = "{value}"',
    ):
        assert key_names_a_credential(line), line
        refuse, _ = classify(
            [SecretHit(line_number=1, detector="Hex High Entropy String")], [line]
        )
        assert refuse, f"must still refuse: {line}"


def test_json_is_allowlisted_by_name_not_by_suffix():
    """`.json` as an allowed suffix swept in 2909 generated data manifests."""
    from kernote.ingest import walker

    assert ".json" not in walker.ALLOWED_SUFFIXES
    for name in ("package.json", "tsconfig.json", "composer.json"):
        assert name in walker.ALLOWED_NAMES, name
