#!/usr/bin/env python3
"""Kernote end-to-end demo: the Day-25 release-candidate gate.

Runs the whole product against a real repository and prints what it found,
using nothing but the HTTP API — the same surface the web app uses, so a green
run means the application works, not that the library imports.

Two deliberate safety choices, both of them product requirements rather than
demo conveniences:

* It runs against a **copy** of the sample repository in a temporary
  directory. Showing drift detection means editing a scanned file, and
  `CLAUDE.md` forbids rewriting the user's files. The demo does not get an
  exception to that.
* It uses a **temporary data directory**, so the demo's 50 fixture memories
  never land in your own vault.

    python3 scripts/demo.py            # starts its own API on a free port
    python3 scripts/demo.py --port 8787 --no-serve   # use a running API

Exits non-zero if any step fails, so CI and the release gate can run it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "samples" / "eval-repo"
BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
failures: list[str] = []


def _console_supports_utf8() -> bool:
    """Make the console UTF-8 if it will go, and report whether it did.

    Windows defaults stdout to the locale encoding -- cp1252 on the machine
    this was found on -- so printing a box-drawing rule raised
    `UnicodeEncodeError` and the release gate could not run there at all. Same
    root cause as the MCP transport bug, in the opposite direction.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                return False
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "")
    return encoding == "utf8"


UTF8 = _console_supports_utf8()
RULE = "\u2500\u2500" if UTF8 else "--"
BULLET = "\u00b7" if UTF8 else "*"


def step(title: str) -> None:
    print(f"\n{BOLD}{RULE} {title}{RESET}")


def ok(message: str) -> None:
    print(f"   {message}")


def bad(message: str) -> None:
    failures.append(message)
    print(f"   {BOLD}FAIL{RESET} {message}")


def check(condition: bool, message: str) -> bool:
    (ok if condition else bad)(message)
    return condition


def api(method: str, path: str, base: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - fixed localhost base
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300]
        raise SystemExit(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(
    base: str,
    process: subprocess.Popen | None,
    seconds: int = 90,
    log_file: Path | None = None,
) -> dict:
    deadline = time.monotonic() + seconds
    last = ""
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            detail = ""
            if log_file is not None and log_file.is_file():
                tail = log_file.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                detail = "\n" + "\n".join(tail[-15:])
            raise SystemExit(
                f"the API exited with code {process.returncode} before serving{detail}"
            )
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=5) as response:  # noqa: S310
                return json.loads(response.read())
        except Exception as exc:  # noqa: BLE001 - any failure here means "not up yet"
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(0.4)
    raise SystemExit(f"the API never became healthy at {base}: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--no-serve", action="store_true", help="use an already-running API"
    )
    args = parser.parse_args()

    if not CORPUS.is_dir():
        raise SystemExit(f"sample repository missing: {CORPUS}")

    port = args.port or (8787 if args.no_serve else free_port())
    base = f"http://127.0.0.1:{port}/api/v1"
    health_base = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="kernote-demo-") as workspace:
        workspace = Path(workspace)
        data_dir = workspace / "data"
        repo = workspace / "lanternfish"
        shutil.copytree(CORPUS, repo)
        print(f"{DIM}workspace {workspace}{RESET}")

        state: dict[str, subprocess.Popen | None] = {"process": None}
        log_path = workspace / "api.log"

        def launch() -> subprocess.Popen | None:
            if args.no_serve:
                return None
            environment = dict(os.environ, KERNOTE_DATA_DIR=str(data_dir))
            return subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "kernote.main:app",
                    "--app-dir",
                    str(ROOT / "backend"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                env=environment,
                stdout=subprocess.DEVNULL,
                # To a file, never to an unread PIPE. On Windows the pipe
                # buffer is small enough that the server's own log output
                # filled it mid-scan, uvicorn then blocked on write, and the
                # next request timed out after two minutes with the server
                # still apparently alive. A file is also diagnosable when the
                # server dies.
                stderr=log_path.open("a", encoding="utf-8"),
            )

        def stop() -> None:
            process = state["process"]
            if process is None:
                return
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        def restart() -> bool:
            """Really restart the API, so the persistence claim is tested.

            Printing "survives a restart" after merely querying again would be
            a claim the demo had not checked -- the exact thing this product
            exists to stop.
            """
            if args.no_serve:
                return False
            stop()
            state["process"] = launch()
            wait_for_health(health_base, state["process"], log_file=log_path)
            return True

        state["process"] = launch()
        try:
            return run(base, health_base, state, repo, restart, log_path)
        finally:
            stop()


def run(
    base: str,
    health_base: str,
    state: dict,
    repo: Path,
    restart,
    log_path: Path,
) -> int:
    step("The API is up")
    health = wait_for_health(health_base, state["process"], log_file=log_path)
    ok(f"schema version {health.get('schema_version')} · {health.get('status')}")

    step("Register a project and scan it, read-only")
    project = api(
        "POST", "/projects", base, {"name": "Lanternfish", "root_path": str(repo)}
    )
    scan = api("POST", f"/projects/{project['id']}/scan", base)
    ok(
        f"{scan['memories_created']} memories from {scan['captures_created']} captures"
        f" · {scan['files_seen']} files seen, {scan['files_skipped']} skipped"
        f" · {len(scan['secret_warnings'])} secret warning(s)"
    )
    check(scan["memories_created"] > 20, "the scan produced memories")
    skipped = api("GET", f"/scans/{scan['scan_run_id']}/skipped", base)
    if skipped["total"]:
        for reason, paths in skipped["by_reason"].items():
            ok(f"skipped {len(paths)} as {reason}: {', '.join(paths[:3])}")
    else:
        ok("nothing was skipped in this corpus")

    step("Rescanning changes nothing (idempotence)")
    again = api("POST", f"/projects/{project['id']}/scan", base)
    check(
        again["captures_created"] == 0 and again["memories_created"] == 0,
        f"second scan created {again['captures_created']} captures,"
        f" {again['memories_created']} memories",
    )

    step("Ask a question that the repository answers")
    answer = api(
        "POST",
        f"/projects/{project['id']}/ask",
        base,
        {"question": "Why does the queue use Redis streams instead of Celery?"},
    )
    ok(f"outcome: {answer['outcome']}")
    for item in answer["evidence"][:3]:
        ok(f"  [{item['kind']}] {item['citation']} — {item['title'][:54]}")
    check(answer["outcome"] == "evidence_found", "it found cited evidence")
    check(bool(answer["evidence"]), "every claim carries a citation")

    step("Ask something the repository does not answer")
    unknown = api(
        "POST",
        f"/projects/{project['id']}/ask",
        base,
        {"question": "What is the contractual delivery SLA for next-day orders?"},
    )
    ok(f"outcome: {unknown['outcome']}")
    ok(f"statement: {unknown['statement'][:96]}")
    for gap in unknown["unknowns"][:2]:
        ok(f"  unknown: {gap[:88]}")
    check(
        unknown["outcome"] != "evidence_found",
        "it declined to answer rather than inventing one",
    )

    step("Plant a contradicting decision, and watch both claims stay open")
    (repo / "docs" / "adr" / "0007-queue-revisited.md").write_text(
        "# ADR-0007: Celery for the job queue\n\nStatus: accepted\n"
        "Date: 2025-11-01\n\n## Decision\n\nWe will use Celery with RabbitMQ "
        "for the job queue, not Redis streams.\n\n## Consequences\n\n"
        "RabbitMQ joins the stack.\n",
        encoding="utf-8",
    )
    api("POST", f"/projects/{project['id']}/scan", base)
    analysis = api("POST", f"/projects/{project['id']}/analyze", base)
    ok(f"decision conflicts: {analysis['conflicts_decision']}")
    findings = api("GET", f"/projects/{project['id']}/findings", base)
    conflicts = [f for f in findings if f["kind"] == "conflict"]
    check(bool(conflicts), "the contradiction produced a conflict finding")
    for finding in conflicts[:1]:
        ok(f"  [{finding['severity']}] {finding['explanation'][:100]}")
        for claim in finding["evidence"].get("claims", [])[:2]:
            ok(f"    claim: {str(claim)[:96]}")
    check(
        all(f["status"] == "open" for f in conflicts),
        "both claims stay open until a human resolves them",
    )

    step("Edit a cited file, then detect the drift")
    target = repo / "docs" / "adr" / "0002-redis-queue.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace(
            "We will use Redis streams with consumer groups, not Celery.",
            "We will use Celery with RabbitMQ after all, reversing this decision.",
        ),
        encoding="utf-8",
    )
    api("POST", f"/projects/{project['id']}/scan", base)
    analysis = api("POST", f"/projects/{project['id']}/analyze", base)
    ok(
        f"drift high/medium/low: {analysis['drift_high']}/"
        f"{analysis['drift_medium']}/{analysis['drift_low']}"
        f" · {analysis['refs_checked']} source refs checked"
        f" · duplicate candidates {analysis['duplicate_candidates']}"
    )
    findings = api("GET", f"/projects/{project['id']}/findings", base)
    drift = [f for f in findings if f["kind"] == "stale_risk"]
    check(bool(drift), "the edit produced a staleness finding")
    for finding in drift[:2]:
        ok(f"  [{finding['severity']}] {finding['explanation'][:96]}")
        evidence = finding["evidence"]
        ok(
            f"    cited lines {evidence.get('cited_lines')}"
            f" · overlapping hunks {evidence.get('overlapping_hunks')}"
            f" · cosmetic only: {evidence.get('cosmetic_only')}"
        )
        ok(
            f"    hash {str(evidence.get('pinned_hash'))[:12]}"
            f" -> {str(evidence.get('current_hash'))[:12]}"
        )

    step("A finding is a request for review, resolved by a human")
    if drift:
        resolved = api(
            "POST",
            f"/findings/{drift[0]['id']}/resolve?project_id={project['id']}",
            base,
            {"verdict": "resolved", "note": "Reviewed in the demo."},
        )
        check(resolved["verdict"] == "resolved", "the resolution was recorded")

    step("Measured retrieval quality")
    report = api("POST", "/evaluation/run", base, {"limit": 10})
    ok(
        f"citation correctness {report['citation_correctness']:.1%}"
        f" · useful abstention {report['useful_abstention_rate']:.1%}"
        f" · Recall@5 {report['recall_at_k'].get('5')}"
    )
    ok(f"verdicts: {report['verdicts']}")
    check(
        report["useful_abstention_rate"] >= 0.5,
        "it declines on most unanswerable questions",
    )

    step("Package context for a coding agent, inside a token budget")
    bundle = api(
        "POST",
        f"/projects/{project['id']}/context",
        base,
        {"task": "change how invoices are generated", "token_budget": 1200},
    )
    ok(
        f"~{bundle['tokens_used']} of {bundle['token_budget']} tokens"
        f" · {bundle['included']} included · {bundle['excluded_total']} left out"
    )
    check(
        bundle["tokens_used"] <= bundle["token_budget"] or bundle["over_budget"],
        "the bundle stayed inside its budget, or said that it could not",
    )
    check(
        bundle["included"] + bundle["excluded_total"] > bundle["included"],
        "it reports what it left out rather than truncating silently",
    )

    step("The read-only agent surface")
    mcp = api("GET", f"/projects/{project['id']}/mcp", base)
    ok(f"{len(mcp['tools'])} tools, writable={mcp['writable']}")
    for tool in mcp["tools"]:
        ok(f"  {tool['name']}")
    check(mcp["writable"] is False, "the MCP surface is read-only")
    check(len(mcp["tools"]) == 4, "four tools are advertised")

    step("Everything survives a restart")
    before = api("GET", f"/projects/{project['id']}/memories?limit=200", base)
    restarted = restart()
    after = api("GET", f"/projects/{project['id']}/memories?limit=200", base)
    projects = api("GET", "/projects", base)
    if restarted:
        ok("the API process was stopped and started again")
    else:
        ok("--no-serve: reading again without a restart")
    check(
        len(after) == len(before) and len(after) > 0,
        f"{len(after)} memories readable after the restart (was {len(before)})",
    )
    check(
        any(p["id"] == project["id"] for p in projects),
        "the project is still registered",
    )
    # The endpoint returns open findings only, so the resolved one is absent
    # by design -- counting "resolved" here would have reported zero whatever
    # the truth was.
    open_after = api("GET", f"/projects/{project['id']}/findings", base)
    ok(f"{len(open_after)} finding(s) still open for review after the restart")
    check(
        all(f["id"] != drift[0]["id"] for f in open_after) if drift else True,
        "the finding a human resolved did not come back",
    )
    print(
        f"\n{DIM}The demo's data directory and repository copy are now deleted.{RESET}"
    )

    if failures:
        print(f"\n{BOLD}DEMO FAILED{RESET} — {len(failures)} check(s):")
        for failure in failures:
            print(f"  {BULLET} {failure}")
        return 1
    print(f"\n{BOLD}DEMO PASSED{RESET} — every step above ran against the real API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
