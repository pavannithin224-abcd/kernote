"""The API serves the built UI, so Kernote is one command on one port (Q4).

The risk in collapsing two servers into one is that the catch-all needed for
client-side routing starts answering for things it should not. These tests
pin the two boundaries that matter: an unknown API path must stay a JSON 404,
and a client-side route must return the app shell rather than 404.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kernote.config import settings
from kernote.main import create_app, web_dist


@pytest.fixture
def built(tmp_data_dir, tmp_path, monkeypatch):
    """A minimal stand-in for `frontend/dist`."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Kernote</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(settings, "web_dist", dist)
    with TestClient(create_app()) as c:
        yield c, dist


def test_the_app_shell_is_served_at_the_root(built):
    client, _ = built
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Kernote</title>" in r.text


def test_a_client_side_route_returns_the_shell_not_a_404(built):
    """`/graph` is a React Router path, not a file. A hard reload must work."""
    client, _ = built
    for route in ("/graph", "/dashboard", "/explorer"):
        r = client.get(route)
        assert r.status_code == 200, route
        assert "<title>Kernote</title>" in r.text


def test_real_files_are_served(built):
    client, _ = built
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_an_unknown_api_path_stays_a_json_404(built):
    """The failure this guard exists for.

    Falling through to index.html would answer 200 with HTML where a client
    expected a parseable error, turning a typo into a silent mystery.
    """
    client, _ = built
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")


def test_health_is_not_shadowed(built):
    client, _ = built
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_the_api_still_works_underneath(built):
    client, _ = built
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_a_traversal_attempt_cannot_escape_the_build(built, tmp_path):
    """`..` in the path must not reach a file outside the build directory."""
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me", encoding="utf-8")
    client, _ = built
    for attempt in ("/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt"):
        r = client.get(attempt)
        assert "do not serve me" not in r.text, attempt


def test_without_a_build_the_api_runs_alone(tmp_data_dir, tmp_path, monkeypatch):
    """The development arrangement: Vite serves the UI on its own port."""
    monkeypatch.setattr(settings, "web_dist", tmp_path / "nothing-here")
    assert web_dist() is None
    with TestClient(create_app()) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/").status_code == 404


# ===================== caching and CORS =====================


def test_hashed_assets_are_cached_forever(tmp_data_dir, tmp_path, monkeypatch):
    """Vite renames the file whenever the bytes change, so it never expires."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>K</title>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("x", encoding="utf-8")
    monkeypatch.setattr(settings, "web_dist", dist)

    with TestClient(create_app()) as client:
        cache = client.get("/assets/index-abc123.js").headers["cache-control"]
        assert "immutable" in cache and "max-age=31536000" in cache


def test_the_shell_is_never_cached(built):
    """A stale shell names assets that no longer exist.

    The symptom is a blank app after an upgrade, fixed only by a hard
    refresh the user has no reason to guess at.
    """
    client, _ = built
    for path in ("/", "/graph"):
        assert client.get(path).headers["cache-control"] == "no-cache", path


def test_cors_is_absent_when_no_origin_is_configured(tmp_data_dir, monkeypatch):
    """Served as one process there is only one origin, so the middleware is
    attack surface and nothing else."""
    monkeypatch.setattr(settings, "cors_origins", ())
    with TestClient(create_app()) as client:
        r = client.get("/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_still_works_for_the_dev_origin(tmp_data_dir, monkeypatch):
    """`just dev` must keep working: Vite on :5173, the API here."""
    monkeypatch.setattr(settings, "cors_origins", ("http://localhost:5173",))
    with TestClient(create_app()) as client:
        r = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_does_not_allow_an_unlisted_origin(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ("http://localhost:5173",))
    with TestClient(create_app()) as client:
        r = client.get("/health", headers={"Origin": "http://evil.example"})
        assert r.headers.get("access-control-allow-origin") != "http://evil.example"
