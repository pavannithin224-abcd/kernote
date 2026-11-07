import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


@pytest.fixture
def tmp_data_dir(monkeypatch):
    """Point Kernote's data dir at a throwaway directory for each test."""
    with tempfile.TemporaryDirectory() as d:
        from kernote.config import settings

        monkeypatch.setattr(settings, "data_dir", pathlib.Path(d))
        yield pathlib.Path(d)


@pytest.fixture
def conn(tmp_data_dir):
    from kernote.db.connection import open_db

    c = open_db(tmp_data_dir / "test.db")
    yield c
    c.close()


@pytest.fixture
def client(tmp_data_dir):
    from fastapi.testclient import TestClient

    from kernote.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def demo_repo() -> str:
    root = pathlib.Path(__file__).resolve().parents[2] / "samples" / "demo-repo"
    assert root.is_dir(), "samples/demo-repo missing"
    return str(root)


@pytest.fixture
def hostile_repo(tmp_path) -> pathlib.Path:
    """A repo designed to be refused: secrets, binary, oversized, CRLF."""
    (tmp_path / "README.md").write_text(
        "# Hostile\n\n## Setup\n\nRun it.\n\n```bash\nmake run\n```\n"
    )
    (tmp_path / ".env").write_text("API_KEY=sk-not-a-real-key-000000000000\n")
    (tmp_path / "server.pem").write_text("-----BEGIN PRIVATE KEY-----\nnope\n")
    (tmp_path / "id_rsa").write_text("ssh-private\n")
    (tmp_path / "credentials.json").write_text('{"token":"nope"}')
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(300))
    (tmp_path / "big.md").write_text("x" * 2_000_000)
    (tmp_path / "crlf.md").write_bytes(
        b"# Title\r\n\r\n## Setup\r\n\r\nWindows line endings.\r\n"
    )
    (tmp_path / ".gitignore").write_text("ignored.md\n")
    (tmp_path / "ignored.md").write_text("# Should not be imported\n\nSecret-ish plans.\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.json").write_text("{}")
    return tmp_path
