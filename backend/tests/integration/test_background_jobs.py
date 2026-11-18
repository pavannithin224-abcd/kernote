"""Scanning and analysis off the request thread.

What is worth testing here is not "does a thread run" but the decisions
around it: that a second scan of the same project is not queued twice
against a single-writer database, that a failure is recorded rather than
swallowed, and that the blocking endpoints still work because scripts and
tests depend on them.
"""

from __future__ import annotations

import pytest

from kernote import jobs


@pytest.fixture(autouse=True)
def fresh_runner(monkeypatch):
    """A clean runner per test, so queued work does not leak between them."""
    monkeypatch.setattr(jobs, "runner", jobs.JobRunner())
    return jobs.runner


def test_a_job_runs_and_records_its_result(fresh_runner):
    job = fresh_runner.submit("j1", "scan", "p1", lambda: {"files_seen": 3})
    # Not asserting it is still queued: a trivial job can finish before the
    # next line runs, and a test that depends on losing that race is a test
    # that fails on a fast machine.
    assert job.status in ("queued", "running", "done")

    finished = fresh_runner.wait("j1", timeout=10)
    assert finished.status == "done"
    assert finished.result == {"files_seen": 3}
    assert finished.started_at and finished.finished_at


def test_a_failure_is_recorded_not_swallowed(fresh_runner):
    def boom() -> dict:
        raise RuntimeError("the repository vanished")

    fresh_runner.submit("j2", "scan", "p1", boom)
    finished = fresh_runner.wait("j2", timeout=10)

    assert finished.status == "failed"
    assert "the repository vanished" in finished.error
    assert finished.finished_at, "a failed job must still be finished"


def test_one_failure_does_not_stop_the_worker(fresh_runner):
    """A dead worker would leave every later job queued forever."""
    fresh_runner.submit("bad", "scan", "p1", lambda: (_ for _ in ()).throw(ValueError("x")))
    fresh_runner.wait("bad", timeout=10)
    fresh_runner.submit("good", "scan", "p1", lambda: {"ok": True})
    assert fresh_runner.wait("good", timeout=10).status == "done"


def test_jobs_run_one_at_a_time(fresh_runner):
    """SQLite takes one writer; concurrency here would only add lock timeouts."""
    import threading

    concurrent = []
    running = threading.Semaphore(0)

    def slow() -> dict:
        concurrent.append(1)
        assert len(concurrent) == 1, "two jobs ran at once"
        running.release()
        concurrent.pop()
        return {}

    for i in range(3):
        fresh_runner.submit(f"s{i}", "scan", "p1", slow)
    for _ in range(3):
        assert running.acquire(timeout=10), "a queued job never ran"


def test_the_same_work_is_not_queued_twice(fresh_runner):
    import threading

    gate = threading.Event()
    fresh_runner.submit("first", "scan", "p1", lambda: (gate.wait(5), {})[1])

    assert fresh_runner.active_for("p1", "scan") is not None
    assert fresh_runner.active_for("p1", "analyze") is None, "a different kind is unrelated"
    assert fresh_runner.active_for("p2", "scan") is None, "a different project is unrelated"
    gate.set()
    fresh_runner.wait("first", timeout=10)
    assert fresh_runner.active_for("p1", "scan") is None, "a finished job is not active"


def test_listing_is_newest_first_and_filterable(fresh_runner):
    for i in range(3):
        fresh_runner.submit(f"a{i}", "scan", "pa", lambda: {})
    fresh_runner.submit("b0", "scan", "pb", lambda: {})
    for job in list(fresh_runner.list()):
        fresh_runner.wait(job.id, timeout=10)

    assert {j.id for j in fresh_runner.list("pb")} == {"b0"}
    assert len(fresh_runner.list("pa")) == 3


# ===================== over HTTP =====================


def test_background_scan_returns_a_job_then_completes(client, tmp_path):
    (tmp_path / "README.md").write_text("# A\n\n## Setup\n\nRun make.\n", encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "bg", "root_path": str(tmp_path)}
    ).json()["id"]

    queued = client.post(f"/api/v1/projects/{pid}/scan/background")
    assert queued.status_code == 200, queued.text
    job_id = queued.json()["id"]
    assert queued.json()["status"] in ("queued", "running")

    finished = jobs.runner.wait(job_id, timeout=30)
    assert finished.status == "done", finished.error

    seen = client.get(f"/api/v1/jobs/{job_id}").json()
    assert seen["status"] == "done"
    assert seen["result"]["files_seen"] >= 1

    listed = client.get(f"/api/v1/jobs?project_id={pid}").json()
    assert [j["id"] for j in listed] == [job_id]


def test_a_second_background_scan_returns_the_running_one(client, tmp_path):
    (tmp_path / "README.md").write_text("# A\n\n## Setup\n\nRun make.\n", encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "bg2", "root_path": str(tmp_path)}
    ).json()["id"]

    first = client.post(f"/api/v1/projects/{pid}/scan/background").json()
    second = client.post(f"/api/v1/projects/{pid}/scan/background").json()
    # Either the same job, or the first already finished and this is a new one.
    assert second["id"] == first["id"] or first["status"] == "done"
    jobs.runner.wait(second["id"], timeout=30)


def test_an_unknown_job_is_a_404(client):
    assert client.get("/api/v1/jobs/nope").status_code == 404


def test_the_blocking_endpoints_still_work(client, tmp_path):
    """Scripts, the demo and the existing tests depend on them."""
    (tmp_path / "README.md").write_text("# A\n\n## Setup\n\nRun make.\n", encoding="utf-8")
    pid = client.post(
        "/api/v1/projects", json={"name": "sync", "root_path": str(tmp_path)}
    ).json()["id"]
    assert client.post(f"/api/v1/projects/{pid}/scan").status_code == 200
    assert client.post(f"/api/v1/projects/{pid}/analyze").status_code == 200
