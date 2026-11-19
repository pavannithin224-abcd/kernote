"""The configurable include/exclude list (the project contract).

The asymmetry between the two rules is the point, so most of these tests are
about what configuration *cannot* do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernote.db.repositories import projects as project_repo
from kernote.domain.models import Project, SkipReason
from kernote.ingest import scanconfig
from kernote.ingest.pipeline import scan_project
from kernote.ingest.walker import walk


@pytest.fixture
def repo(tmp_path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "README.md").write_text("# R\n\n## Setup\n\nRun it.\n", encoding="utf-8")
    (tmp_path / "schema.json").write_text('{"title": "the real schema"}', encoding="utf-8")
    (tmp_path / "data" / "run001.json").write_text('{"x": 1}', encoding="utf-8")
    (tmp_path / "notes.txt").write_text("plain notes\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=sk-aaaaaaaaaaaaaaaaaaaaaaaa\n", encoding="utf-8")
    return tmp_path


def _walk(repo: Path, config=None):
    found, skipped = walk(repo, max_file_bytes=10**6, max_files=100, config=config)
    return (
        {f.rel_path for f in found},
        {s.rel_path: s.reason for s in skipped},
    )


def test_include_reaches_a_file_the_allowlist_would_skip(repo):
    """The case that motivated this: a meaningful JSON file under a name the
    built-in list does not know."""
    found, skipped = _walk(repo)
    assert "schema.json" not in found
    assert skipped["schema.json"] is SkipReason.NOT_ALLOWLISTED

    (repo / ".kernote.toml").write_text('[scan]\ninclude = ["schema.json"]\n', encoding="utf-8")
    found, _ = _walk(repo, scanconfig.from_file(repo))
    assert "schema.json" in found


def test_exclude_skips_with_its_own_reason(repo):
    (repo / ".kernote.toml").write_text('[scan]\nexclude = ["notes.txt"]\n', encoding="utf-8")
    found, skipped = _walk(repo, scanconfig.from_file(repo))
    assert "notes.txt" not in found
    assert skipped["notes.txt"] is SkipReason.EXCLUDED


def test_exclude_beats_include(repo):
    """When a path matches both, the safe direction wins."""
    (repo / ".kernote.toml").write_text(
        '[scan]\ninclude = ["**/*.json"]\nexclude = ["data/**"]\n', encoding="utf-8"
    )
    found, skipped = _walk(repo, scanconfig.from_file(repo))
    assert "schema.json" in found
    assert "data/run001.json" not in found
    assert skipped["data/run001.json"] is SkipReason.EXCLUDED


def test_include_cannot_reach_a_secret(repo):
    """A config file inside a repository is untrusted input. It must not be
    able to talk Kernote into reading a credential file."""
    (repo / ".kernote.toml").write_text(
        '[scan]\ninclude = [".env", "**/*"]\n', encoding="utf-8"
    )
    found, skipped = _walk(repo, scanconfig.from_file(repo))
    assert ".env" not in found
    assert skipped[".env"] is SkipReason.SECRET_SUSPECTED


def test_include_cannot_override_gitignore(repo):
    """The project contract requires .gitignore be respected, so there is deliberately
    no way to switch it off."""
    (repo / ".gitignore").write_text("secretplans.md\n", encoding="utf-8")
    (repo / "secretplans.md").write_text("# Plans\n\n## Thing\n\nHidden.\n", encoding="utf-8")
    (repo / ".kernote.toml").write_text(
        '[scan]\ninclude = ["secretplans.md"]\n', encoding="utf-8"
    )
    found, skipped = _walk(repo, scanconfig.from_file(repo))
    assert "secretplans.md" not in found
    assert skipped["secretplans.md"] is SkipReason.GITIGNORED


def test_include_cannot_override_the_size_limit(repo):
    (repo / "huge.md").write_text("x" * 5000, encoding="utf-8")
    (repo / ".kernote.toml").write_text('[scan]\ninclude = ["huge.md"]\n', encoding="utf-8")
    found, skipped = walk(
        repo, max_file_bytes=1000, max_files=100, config=scanconfig.from_file(repo)
    )
    assert "huge.md" not in {f.rel_path for f in found}
    assert {s.rel_path: s.reason for s in skipped}["huge.md"] is SkipReason.TOO_LARGE


def test_kernoteignore_is_still_honoured(repo):
    """It worked before this module existed and must keep working."""
    (repo / ".kernoteignore").write_text("# a comment\nnotes.txt\n", encoding="utf-8")
    config = scanconfig.from_file(repo)
    assert scanconfig.IGNORE_FILENAME in config.sources
    assert "notes.txt" in config.exclude
    assert "# a comment" not in config.exclude


def test_malformed_config_is_refused_not_ignored(repo):
    """A config the user believes is in force but which failed to parse is
    worse than an error."""
    (repo / ".kernote.toml").write_text("[scan]\ninclude = not-a-list\n", encoding="utf-8")
    with pytest.raises(scanconfig.ScanConfigError, match="could not be parsed"):
        scanconfig.from_file(repo)

    (repo / ".kernote.toml").write_text('[scan]\ninclude = "one-string"\n', encoding="utf-8")
    with pytest.raises(scanconfig.ScanConfigError, match="list of strings"):
        scanconfig.from_file(repo)


def test_an_unknown_key_is_reported_rather_than_silently_ignored(repo):
    (repo / ".kernote.toml").write_text('[scan]\nexcludes = ["typo.txt"]\n', encoding="utf-8")
    config = scanconfig.from_file(repo)
    assert any("excludes" in note for note in config.notes)


def test_the_override_persists_and_merges_with_the_repository_config(conn, repo):
    project = project_repo.create(
        conn, Project(name="C", root_path=str(repo), is_git_repo=False)
    )
    (repo / ".kernote.toml").write_text('[scan]\ninclude = ["schema.json"]\n', encoding="utf-8")
    scanconfig.save_override(conn, project.id, include=[], exclude=["notes.txt"])

    effective = scanconfig.effective(conn, project.id, repo)
    assert "schema.json" in effective.include
    assert "notes.txt" in effective.exclude
    assert scanconfig.CONFIG_FILENAME in effective.sources
    assert "project override" in effective.sources

    found, skipped = _walk(repo, effective)
    assert "schema.json" in found
    assert skipped["notes.txt"] is SkipReason.EXCLUDED


def test_a_scan_uses_the_configuration(conn, repo):
    """End to end: the pipeline, not just the walker."""
    (repo / ".kernote.toml").write_text(
        '[scan]\ninclude = ["schema.json"]\nexclude = ["notes.txt"]\n', encoding="utf-8"
    )
    project = project_repo.create(
        conn, Project(name="C", root_path=str(repo), is_git_repo=False)
    )
    result = scan_project(
        conn, project_id=project.id, root=repo, max_file_bytes=10**6, max_files=100
    )
    paths = {
        r["rel_path"]
        for r in conn.execute(
            "SELECT rel_path FROM source_files WHERE project_id=?", (project.id,)
        )
    }
    assert "schema.json" in paths
    assert "notes.txt" not in paths
    assert result.files_skipped > 0


def test_the_endpoints_report_the_effective_config_and_its_rules(client, tmp_path):
    (tmp_path / "README.md").write_text("# R\n\n## S\n\nx\n", encoding="utf-8")
    (tmp_path / ".kernote.toml").write_text(
        '[scan]\ninclude = ["weird.json"]\n', encoding="utf-8"
    )
    project = client.post(
        "/api/v1/projects", json={"name": "C", "root_path": str(tmp_path)}
    ).json()

    got = client.get(f"/api/v1/projects/{project['id']}/scan-config")
    assert got.status_code == 200
    body = got.json()
    assert "weird.json" in body["effective"]["include"]
    assert ".kernote.toml" in body["effective"]["sources"]
    assert any("cannot override a secret" in r for r in body["rules"])

    put = client.put(
        f"/api/v1/projects/{project['id']}/scan-config",
        json={"include": [], "exclude": ["docs/**"]},
    )
    assert put.status_code == 200
    merged = put.json()
    assert "docs/**" in merged["effective"]["exclude"]
    assert "weird.json" in merged["effective"]["include"], "the repo config must survive"
    assert merged["override"]["exclude"] == ["docs/**"]


def test_a_malformed_repository_config_fails_the_request_clearly(client, tmp_path):
    (tmp_path / "README.md").write_text("# R\n\n## S\n\nx\n", encoding="utf-8")
    project = client.post(
        "/api/v1/projects", json={"name": "C", "root_path": str(tmp_path)}
    ).json()
    (tmp_path / ".kernote.toml").write_text("[scan]\ninclude = nope\n", encoding="utf-8")
    got = client.get(f"/api/v1/projects/{project['id']}/scan-config")
    assert got.status_code == 422
    assert "could not be parsed" in got.json()["detail"]
