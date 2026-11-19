# Kernote — Roadmap

Status: draft for Day 1–2 approval · Last updated 2026-11-06

Day 1 = 2026-11-06. Day 25 = 2026-11-30. This is an aggressive release-candidate
target, **not** a claim of enterprise readiness.

---

## Milestones

| Days | Dates | Milestone | Deliverable | Done when |
|---|---|---|---|---|
| 1–2 | Nov 6–7 | Product & architecture foundation | Scope, flows, schema draft, API boundaries, wireframes, repo setup, the project contract | Six docs approved; Git repo initialized; toolchain verified |
| 3–5 | Nov 8–10 | Application foundation | React shell, FastAPI service, SQLite init+migrations, project selection, navigation, dashboard skeleton | `scripts/dev.sh` brings up both processes; a project can be registered and survives restart |
| 6–9 | Nov 11–14 | Repository ingestion | Safe scanner, parsing, Git metadata, source refs, deterministic extraction, **+ drift feasibility spike (P4)** | Fixture repo scans twice with zero duplicate captures; skipped files explained; **an edit inside cited lines yields a high finding and an edit elsewhere in the same file yields a low one** |
| 10–13 | Nov 15–18 | Core memory engine | Schema, CRUD, revisions, classification, dedupe candidates, evidence storage, **+ conflict feasibility spike (P5)** | Memory CRUD persists across restart with full lineage; evidence visible in UI; **two disagreeing sources yield one finding holding both claims, and agreeing sources yield none** |
| 14–17 | Nov 19–22 | Recall & evidence retrieval | FTS5, embeddings, hybrid retrieval, evidence composer, citation panel, retrieval tests | Fixed question set passes; citation correctness and abstention measured with `ranx` |
| 18–20 | Nov 23–25 | **Memory maintenance intelligence** — the differentiating milestone | Drift detection with hunk-overlap, **conflict detection (now `Must`)**, consolidation review, approval controls | A real file edit produces a reviewable finding naming the overlapping hunk; two contradicting sources produce a finding holding both claims; merge preserves lineage |
| 21–22 | Nov 26–27 | Agent delivery | Context bundle export, MCP server, Claude Code / Codex smoke tests | An agent retrieves project context through MCP in a live session |
| 23–24 | Nov 28–29 | Polish & evaluation | UI refinement, tests, dev packaging, sample repo, benchmarks, bug fixes | Benchmarks recorded on the Latitude 3420; evaluation reported on the four MemoryAgentBench axes; test suite green |
| 25 | Nov 30 | Release candidate | Tagged RC, README, architecture docs, demo script, known limitations | Demo script runs end to end from a clean clone |

## Vertical slices

Each slice is a visible user outcome with a working backend path. Never more than
one slice open at a time.

**S1 — Prove persistence (Days 3–5).**
Open a repository → scan README and project config → save one structured memory
with provenance → see it in Memory Explorer → restart the app → prove it
persisted. This is the slice named in the kickoff guide and it is the gate for
everything after it.

**S2 — Prove ingestion is safe and idempotent (6–9).** Scan the hostile fixture:
secrets refused with reasons shown, repeat scan creates nothing new.

**S3 — Prove evidence (10–13).** Every memory detail view shows its source file,
line range, hash and revision history; editing creates a revision, never an
overwrite.

**S4 — Prove grounded answers (14–17).** Ask a question, get cited evidence; ask
an unanswerable question, get an explicit "evidence not found."

**Feasibility spikes (done 2026-11-08, ahead of schedule).** Detection for both
halves of S5 is proven at test level: `maintain/drift.py` and
`maintain/conflicts.py` with 20 tests. Stage 6 now builds the review flow on a
mechanism that already works, rather than discovering the mechanism late. Both
false-positive guards hold: an edit outside the cited lines stays low severity,
and agreeing sources produce no conflict.

**S5 — Prove maintenance (18–20).** The differentiating slice, in two halves:
*(a) drift* — edit a referenced file, rescan, see the finding naming the
overlapping hunk, resolve it; approve a duplicate merge and see both inputs still
retrievable. *(b) conflict* — plant two sources that disagree about the same
setup command, rescan, see one finding holding both claims with their paths and
dates, resolve it and see the resolution audited.

**S6 — Prove agent delivery (21–22).** A Claude Code session pulls context
through MCP without a hand-written instruction file.

## Per-milestone definition of done

A milestone is done only when **all** of these hold — a benchmark or a mock
screen alone is never a completed feature:

1. The user-facing flow works in the running app.
2. Persisted data survives a restart.
3. Evidence states and error states are both visible in the UI.
4. Tests cover the important behaviour, and they were actually run.
5. `docs/DEV_HANDOFF.md` records what changed, what was verified, known issues
   and the next safe task.
6. The diff was reviewed for correctness, security, scope creep and secrets.

## Scope control

If the schedule slips, cut in this order:

1. Custom model training and classifier experiments (`requirements-ml.txt` work)
2. Advanced graph/relationship visualization
3. F10 Proactive Recommendations
4. F9 MCP → degrade to context-bundle file export only
5. F3 breadth — fewer question types, same citation rigour

**Never cut:** evidence provenance, safe memory updates, basic retrieval, tests,
the core application workflow, **drift with hunk-level evidence (F5)** or
**conflict detection (F8)**.

F8 left the cut list when ADR-0015 promoted it to `Must`: it is the wedge, so
cutting it would leave a product that competes only where the field is already
crowded. If Days 18–20 overrun, cut F9 and F3 breadth to protect it.

## Daily rhythm

1. Read the project contract, this roadmap and `DEV_HANDOFF.md`.
2. Pick **one** vertical slice with a visible user outcome.
3. Have Claude Code inspect the relevant code and propose a short plan before editing.
4. Implement, run targeted tests, inspect the diff, update docs.
5. Commit only a working increment; record what changed, what failed, next safe action.
