"""Background work: scanning and analysis, off the request thread.

Scanning a repository and running every detector are the two slow things
Kernote does. Until now both were blocking `POST`s: the UI froze, the
request could time out, and nothing could report progress. This runs them
on a worker and leaves a record behind.

**One worker, on purpose.** SQLite takes a single writer, and scan and
analyze are both write-heavy. Running two at once would not be faster --
they would serialise on the database lock anyway, with the added
possibility of one timing out against the other. A queue makes the
serialisation explicit instead of accidental.

**State lives in memory, deliberately.** A job is a fact about *this
process*: it cannot survive a restart, because the work it describes does
not survive one either. Persisting it would mean reopening the app to a
list of jobs that are not running and cannot be resumed -- a record of
something untrue, which is the one thing this codebase consistently refuses
to store. What the work *produced* is already durable: scans write
`scan_runs`, analysis writes findings and `drift_runs`.
"""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import structlog

log = structlog.get_logger(__name__)

Status = Literal["queued", "running", "done", "failed"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    kind: str
    project_id: str
    status: Status = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "project_id": self.project_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class JobRunner:
    """A single worker thread draining a queue of callables."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: queue.Queue[tuple[str, Callable[[], dict]]] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._drain, name="kernote-jobs", daemon=True)
        self._worker.start()

    def _drain(self) -> None:
        while True:
            job_id, work = self._queue.get()
            job = self._jobs.get(job_id)
            if job is None:  # pragma: no cover - defensive
                continue
            with self._lock:
                job.status = "running"
                job.started_at = _now()
            try:
                result = work()
                with self._lock:
                    job.status = "done"
                    job.result = result
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                # The traceback goes to the log; the message goes to the user.
                # Losing either would make a failed job unexplainable.
                log.error(
                    "job.failed",
                    job_id=job_id,
                    kind=job.kind,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                )
                with self._lock:
                    job.status = "failed"
                    job.error = str(exc)
            finally:
                with self._lock:
                    job.finished_at = _now()
                self._queue.task_done()

    def submit(self, job_id: str, kind: str, project_id: str, work: Callable[[], dict]) -> Job:
        job = Job(id=job_id, kind=kind, project_id=project_id)
        with self._lock:
            self._jobs[job_id] = job
        self._queue.put((job_id, work))
        self._ensure_worker()
        log.info("job.queued", job_id=job_id, kind=kind, project_id=project_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, project_id: str | None = None, limit: int = 20) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if project_id:
            jobs = [j for j in jobs if j.project_id == project_id]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    def active_for(self, project_id: str, kind: str) -> Job | None:
        """A queued or running job of this kind, so one is not started twice.

        Submitting a second scan of the same project does not make it finish
        sooner -- it makes the same work happen twice against a single-writer
        database.
        """
        with self._lock:
            for job in self._jobs.values():
                if (
                    job.project_id == project_id
                    and job.kind == kind
                    and job.status in ("queued", "running")
                ):
                    return job
        return None

    def wait(self, job_id: str, timeout: float = 30.0) -> Job | None:
        """Block until a job finishes. For tests and for synchronous callers."""
        job = self.get(job_id)
        if job is None:
            return None
        deadline = threading.Event()
        waited = 0.0
        while job.status in ("queued", "running") and waited < timeout:
            deadline.wait(0.02)
            waited += 0.02
        return job


runner = JobRunner()
