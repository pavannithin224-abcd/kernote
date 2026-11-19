"""A server with no login must refuse web pages that are not on this machine."""

from __future__ import annotations

import pytest


def test_foreign_host_header_is_refused(client):
    # DNS rebinding: the browser thinks it is same-origin, but Host gives it away.
    r = client.get("/api/v1/projects", headers={"Host": "evil.example.com"})
    assert r.status_code == 403
    assert "not allowed" in r.json()["detail"]


def test_foreign_host_cannot_reach_health_either(client):
    assert client.get("/health", headers={"Host": "evil.example.com:8787"}).status_code == 403


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "127.0.0.1:8787", "localhost", "localhost:5173", "[::1]:8787"]
)
def test_loopback_hosts_are_served(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 200


def test_lookalike_hosts_are_refused(client):
    # A suffix/prefix match would have let these through.
    for host in ("localhost.evil.example", "127.0.0.1.evil.example", "evil-localhost"):
        assert client.get("/health", headers={"Host": host}).status_code == 403, host


@pytest.mark.parametrize(
    "origin", ["http://evil.example.com", "null", "https://localhost.evil.example"]
)
def test_cross_origin_writes_are_refused(client, origin):
    r = client.post(
        "/api/v1/projects",
        json={"name": "x", "root_path": "."},
        headers={"Origin": origin},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "cross-origin write refused"


def test_same_machine_origin_may_write(client, tmp_path):
    r = client.post(
        "/api/v1/projects",
        json={"name": "ok", "root_path": str(tmp_path)},
        headers={"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 201


def test_a_write_with_no_origin_is_allowed(client, tmp_path):
    # curl, the MCP bridge and the demo script send no Origin header.
    r = client.post("/api/v1/projects", json={"name": "cli", "root_path": str(tmp_path)})
    assert r.status_code == 201


def test_reads_with_a_foreign_origin_are_not_blocked_by_the_origin_rule(client):
    # Reads are protected by CORS (not registered in single-process mode) and by
    # the Host check; the Origin rule is only for state changes.
    assert (
        client.get("/health", headers={"Origin": "http://evil.example.com"}).status_code == 200
    )
