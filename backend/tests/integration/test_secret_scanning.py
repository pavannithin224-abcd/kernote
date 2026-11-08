"""Content-level secret refusal (Stage 3, ADR-0013).

Path patterns stop `.env` and `id_rsa`. These cover the harder case: a
credential pasted into a file whose name looks innocent.
"""

import pytest

from kernote.db.repositories import projects as prepo
from kernote.domain.models import Project
from kernote.ingest.pipeline import scan_project
from kernote.ingest.secrets import scan_path, scanning_session

LEAKY = """# Deploy

Export the token first:

    export GH_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a

Then run make deploy.
"""

BENIGN = """# Widgetly

We chose Postgres because of write contention under render workers.

## Setup

```bash
pip install -r requirements.txt
```

Pinned at fastapi==0.115.6. Set API_KEY=your-api-key-here in your environment.
"""


def _scan(conn, root):
    project = prepo.create(conn, Project(name="s", root_path=str(root)))
    return project, scan_project(
        conn,
        project_id=project.id,
        root=root,
        max_file_bytes=1_000_000,
        max_files=500,
    )


# ------------------------------------------------------------- unit level


def test_benign_documentation_is_not_flagged(tmp_path):
    """The reason `scan_file` is used rather than `scan_line`: the low-level
    primitive bypasses detect-secrets' filters and reports high-entropy hits on
    prose, pip commands and version pins, which would refuse every file."""
    f = tmp_path / "README.md"
    f.write_text(BENIGN)
    with scanning_session():
        assert scan_path(f) == []


@pytest.mark.parametrize(
    ("label", "line"),
    [
        ("github token", "token: ghp_16C7e42F292c6912E7710c838347Ae178B4a"),
        ("aws key", "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"),
        ("private key header", "-----BEGIN RSA PRIVATE KEY-----"),
    ],
)
def test_real_credential_formats_are_detected(tmp_path, label, line):
    f = tmp_path / "notes.md"
    f.write_text(f"# Notes\n\nSome context here.\n\n    {line}\n")
    with scanning_session():
        hits = scan_path(f)
    assert hits, f"{label} was not detected"
    assert all(h.line_number > 0 for h in hits)


def test_hits_never_carry_the_secret_value(tmp_path):
    """These end up in logs and in the review UI; writing the credential there
    would recreate the leak being refused."""
    f = tmp_path / "notes.md"
    f.write_text("# N\n\nSome context.\n\n    ghp_16C7e42F292c6912E7710c838347Ae178B4a\n")
    with scanning_session():
        hits = scan_path(f)
    assert hits
    for hit in hits:
        assert "ghp_16C7" not in repr(hit)
        assert set(vars(hit)) == {"line_number", "detector"}


def test_unreadable_file_does_not_raise(tmp_path):
    with scanning_session():
        assert scan_path(tmp_path / "does-not-exist.md") == []


# --------------------------------------------------------- pipeline level


def test_file_with_a_credential_is_refused_and_nothing_is_stored(conn, tmp_path):
    (tmp_path / "README.md").write_text(BENIGN)
    (tmp_path / "DEPLOY.md").write_text(LEAKY)
    project, result = _scan(conn, tmp_path)

    assert ("DEPLOY.md", "secret_suspected") in [
        (s.rel_path, s.reason.value) for s in result.skipped
    ]
    stored = [r["rel_path"] for r in conn.execute("SELECT rel_path FROM source_files")]
    assert stored == ["README.md"], f"a file with a credential was stored: {stored}"

    # The decisive assertion: the secret is nowhere in the database.
    for table, column in (("source_captures", "text"), ("memories", "content")):
        leaked = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE '%ghp_16C7%'"  # noqa: S608
        ).fetchone()[0]
        assert leaked == 0, f"the credential leaked into {table}.{column}"


def test_a_clean_repository_is_unaffected(conn, tmp_path):
    (tmp_path / "README.md").write_text(BENIGN)
    _project, result = _scan(conn, tmp_path)
    assert result.files_seen == 1
    assert result.memories_created > 0
    assert not [s for s in result.skipped if s.reason.value == "secret_suspected"]


def test_refusal_is_stable_across_rescans(conn, tmp_path):
    (tmp_path / "README.md").write_text(BENIGN)
    (tmp_path / "DEPLOY.md").write_text(LEAKY)
    project, _ = _scan(conn, tmp_path)
    second = scan_project(
        conn,
        project_id=project.id,
        root=tmp_path,
        max_file_bytes=1_000_000,
        max_files=500,
    )
    assert second.captures_created == 0
    assert second.memories_created == 0
    assert [s.rel_path for s in second.skipped if s.reason.value == "secret_suspected"] == [
        "DEPLOY.md"
    ]


def test_path_and_content_refusal_both_report(conn, tmp_path):
    """Two layers, two reasons, both explained in the same scan."""
    (tmp_path / "README.md").write_text(BENIGN)
    (tmp_path / ".env").write_text("TOKEN=abc123\n")
    (tmp_path / "DEPLOY.md").write_text(LEAKY)
    _project, result = _scan(conn, tmp_path)
    refused = {s.rel_path for s in result.skipped if s.reason.value == "secret_suspected"}
    assert refused == {".env", "DEPLOY.md"}


# ------------------------------------------------- two-tier precision policy


def test_keyword_only_hits_warn_instead_of_refusing(conn, tmp_path):
    """Dogfooding refused Kernote's own `domain/models.py` because it contains
    `SECRET_SUSPECTED = "secret_suspected"`, and `Dashboard.tsx` for the words
    "possible secret". Any security-adjacent codebase would lose files."""
    (tmp_path / "models.py").write_text(
        'SECRET_SUSPECTED = "secret_suspected"\n'
        'REASON = "refused as possible secret -- never read"\n'
        "\n\ndef classify(value):\n    return value\n"
    )
    _project, result = _scan(conn, tmp_path)

    refused = [s.rel_path for s in result.skipped if s.reason.value == "secret_suspected"]
    assert "models.py" not in refused, "a keyword guess must not lose the file"
    warned = {w.rel_path for w in result.secret_warnings}
    assert "models.py" in warned, "a keyword guess must still be reported"
    warning = next(w for w in result.secret_warnings if w.rel_path == "models.py")
    assert warning.lines and warning.detectors
    assert all("secret_suspected" not in d for d in warning.detectors)


def test_format_hits_still_refuse(conn, tmp_path):
    """The two-tier policy must not weaken refusal of real credentials."""
    (tmp_path / "DEPLOY.md").write_text(LEAKY)
    _project, result = _scan(conn, tmp_path)
    assert [s.rel_path for s in result.skipped if s.reason.value == "secret_suspected"] == [
        "DEPLOY.md"
    ]
    assert not result.secret_warnings


def test_classify_splits_by_precision():
    from kernote.ingest.secrets import SecretHit, classify

    refuse, warn = classify(
        [
            SecretHit(1, "GitHub Token"),
            SecretHit(2, "Private Key"),
            SecretHit(3, "Secret Keyword"),
            SecretHit(4, "Base64 High Entropy String"),
        ]
    )
    assert [h.detector for h in refuse] == ["GitHub Token", "Private Key"]
    assert [h.detector for h in warn] == ["Secret Keyword", "Base64 High Entropy String"]


# -------------------------------------------------- path deny-list precision


@pytest.mark.parametrize(
    ("name", "refused"),
    [
        # Source modules named for secrets are ordinary code. `secrets.*`
        # refused Kernote's own `ingest/secrets.py`.
        ("secrets.py", False),
        ("secrets.ts", False),
        ("credentials.ts", False),
        ("secret_scanning.py", False),
        # Config files named for secrets are not.
        ("secrets.json", True),
        ("secrets.yaml", True),
        ("credentials.json", True),
        (".env", True),
        (".env.local", True),
        ("server.pem", True),
        ("id_rsa", True),
    ],
)
def test_path_deny_list_distinguishes_config_from_code(name, refused):
    from kernote.ingest.walker import _looks_secret

    assert _looks_secret(name) is refused
