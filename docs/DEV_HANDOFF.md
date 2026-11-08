# Kernote — Developer Handoff

Updated at the end of every task, per `CLAUDE.md` §"Git and task workflow" step 7.
Newest entry first.

---

## 2026-11-08 — Spike review: fixed a latent wrong-answer bug in validity comparison

Review of the P4/P5 spikes, by probing them adversarially rather than reading
them. Four weaknesses found; the user chose to fix the first.

### The bug
`_windows_overlap` and the ADR-0017 ordering validator compared `valid_from` /
`valid_until` as **raw strings**. `"2026-1-1"` sorts after `"2026-01-01"`
because `"1" > "0"`, so an unpadded date gave the wrong overlap verdict with no
error. `"01/01/2026"` was accepted and compared as nonsense. Nothing validated
the format, and the fields are writable through the public API.

This is the worst failure shape available to this product: not a crash, but a
confident and wrong conflict finding, in the feature ADR-0015 made the wedge.

### What changed (ADR-0017a)
Three layers, in `domain/models.py` and `maintain/conflicts.py`:
1. A field validator parses with `datetime.fromisoformat` and rejects the rest,
   naming the field, showing an example and quoting the bad input.
2. Accepted values are normalised to one canonical form, so four spellings of
   the same instant cannot coexist on disk.
3. Ordering and overlap compare timezone-aware `datetime` objects. An
   unparseable **stored** bound is treated as open-ended and logged, erring
   towards reporting a possible conflict rather than hiding one.

### Verification performed
- **102 tests pass** (was 73). 29 new in `tests/unit/test_temporal.py`:
  rejection matrix (9 bad formats × 2 fields), normalisation table (5 forms),
  ordering across mixed formats, overlap (6 cases incl. touching windows),
  currency.
- Confirmed at the boundary: all of `2026-1-1`, `01/01/2026`, `2026-13-01`,
  `2026-02-30`, `yesterday`, `""` are now rejected before storage.
- `ruff check` and `ruff format --check` clean.
- Drift re-verified on the real demo repo after the change: still HIGH=1,
  LOW=6 on a one-line edit, so the fix did not disturb the overlap test.

### Known issues / blockers
1. **Problem 2 (not fixed, user deferred):** whitespace-only edits and prose
   reflow produce hunks, so a formatter run across the docs would flag every
   citation in the touched lines as high severity. Proposed fix was a `medium`
   band for "changed, but only whitespace within the cited lines", which also
   puts the currently-unused `medium` severity to work.
2. **Problem 3 (deferred to Stage 6):** `manual` is in `_COMMAND_METHODS`, so a
   hand-written procedure memory has its prose split into pseudo-commands.
   Harmless today because no UI creates them.
3. **Problem 4 (deferred to Stage 6, needs the eval set):** task normalisation
   is literal — `Setup`/`Set up`, `Testing`/`Tests`, `Build`/`Building` all
   miss. Widening it trades false negatives for false positives and should be
   tuned against the P11 labelled set, not by guesswork.
4. Stored temporal values changed shape (`"2026-03-11"` →
   `"2026-03-11T00:00:00+00:00"`). One round-trip test updated deliberately.
5. Proposal items P3, P6-P13 remain unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
Either Problem 2 (small, prevents a false-positive wave on the first formatter
run) or **Stage 3 proper**: `detect-secrets` content scanning, `rule:adr`
extraction to feed the decision-conflict signal, tree-sitter symbols, widened
allowlist.

---

## 2026-11-08 — Drift and conflict feasibility spikes (proposals P4, P5)

Detection only, test level, no UI. Full implementation stays in Stage 6. The
point was to prove the two mechanisms before the milestone that carries the
product wedge depends on them.

### What changed
- `maintain/findings.py` — the single review queue (ADR-0007), with a
  `dedupe_key` so re-running a detector cannot pile up duplicate findings.
- `maintain/drift.py` — hash change, then diff, then **hunk/line-range overlap**.
  High severity only when changed regions overlap the cited lines.
- `maintain/conflicts.py` — two deterministic signals: *same task, different
  commands* and *same question, different answer with overlapping validity*.
  The second is only possible because ADR-0017 made validity reachable.
- `unidiff` promoted from commented-out to installed in `requirements.txt`.
- ADR-0019 added (20 ADRs). `ROADMAP.md` Stage 3 and Stage 4 now carry the
  feasibility gates; a note records that both are already met.

### Verification performed
- **73 tests pass** (was 53). 20 new: 10 drift, 10 conflict.
- `ruff check` clean, `ruff format --check` clean (44 files).
- Demonstrated on the real `samples/demo-repo`: editing README line 10 produced
  **exactly 1 high finding** (the memory citing lines 6-11) and **6 low** for
  the other memories in that same file. A naive file-changed detector would
  have raised 7 false alarms. This is the single most important number in the
  spike.
- Conflict, on the same repo with a CONTRIBUTING.md added:
  `README.md:26-29 -> ['pytest -q', 'ruff check .']` versus
  `CONTRIBUTING.md:7-9 -> ['tox -e py312']`, one finding holding both claims,
  neither record touched.

### Two findings that changed the design
1. **A file conflicted with itself.** `## Testing` yields both a section memory
   and a commands memory, and "commands" is a filler word, so both normalised
   to the same task. My guard compared full citations, which differ by line
   range. Fixed two ways: only extractors that produce an actual command list
   participate (`rule:markdown_commands`, `manual`), and comparison is now per
   **file**, not per citation. This is exactly what a spike is for.
2. **`git diff` is the wrong source for hunks** (ADR-0019). It yields nothing
   for untracked files, nothing outside a repository, and nothing for
   working-tree edits against a mid-session hash — which is the normal state of
   a project someone is actively editing, precisely when freshness matters.
   Diffs now come from the stored L1 capture via `difflib` + `unidiff`, with
   `n=0` context so neighbouring unchanged lines do not create false overlaps.
   A test asserts drift works in a directory with no Git at all.

### Known issues / blockers
1. Conflict title normalisation is literal: "Setup" and "How to set up" do not
   match. Acceptable for heading-derived titles, but Stage 6 should widen it,
   and that will trade false negatives for false positives — needs the
   evaluation set to tune against, not guesswork.
2. Neither detector is wired to an endpoint or the UI. Deliberate: Stage 6.
3. Severity is binary (overlap or not). Medium is unused for `stale_risk`.
4. `_decisions` only fires when a `decision` payload exists, and no extractor
   produces one yet — only manual memories do. `rule:adr` in Stage 3 will feed it.
5. Proposal items P3, P6-P13 remain unapplied.
6. ADR-0009 (Windows) and open questions Q1, Q2, Q4 still unanswered.

### Next safe task
**Stage 3 proper.** `detect-secrets` content scanning to replace the path
deny-list (ADR-0013), `rule:adr` extraction to feed the decision-conflict
signal, tree-sitter symbols with per-language `tags.scm` (ADR-0012), and the
allowlist widened to source files. Gate: slice S2, plus the Stage 3 drift gate
which is already met.

---

## 2026-11-08 — Backend hardening: write integrity, supersession, temporal validity

Scope chosen by the user: strengthen the backend and eliminate bugs before
adding features. UI work deferred to Stage 8.

### Bugs found by auditing Stage 2's own code, each reproduced before fixing

1. **Orphaned memories.** The connection runs in autocommit
   (`isolation_level=None`) and no application code opened a transaction, so
   `memories.create()` committed the memory row, then its revision, then its
   source refs as three independent writes. Simulating a failure on the second
   left a **committed memory with no lineage and no provenance** — MEMORY_MODEL
   invariant 3 violated at the storage layer, below where validation can help.
2. **Duplicate current source files.** `ix_source_files_current` was a plain
   partial index, so two rows for one path could both be `is_current=1`. The
   rule lived only in Python, and the database accepted the violation when
   tested directly.
3. **Non-atomic scans.** Hundreds of autocommitted writes meant a mid-scan
   failure left captures committed without their chunks and memories — worse
   than failing outright, because the next scan treats the capture as known and
   never retries the extraction.

### What changed
- `db/connection.py`: `transaction()` context manager — `BEGIN IMMEDIATE`,
  **re-entrant** (a nested call joins the outer unit of work and rolls back with
  it), guarded by one process-wide `RLock` (ADR-0018).
- `repositories/memories.py`: `create`, `update`, `archive` are now single units
  of work; new `supersede()`.
- `repositories/sources.py`: `record_file` demote-then-insert is atomic, which
  it must be now that the index is UNIQUE.
- `ingest/pipeline.py`: rewritten so **one file is one transaction**; extraction
  split into `_ingest_one_file`.
- **Migration 0002** (forward-only): makes `ix_source_files_current` UNIQUE,
  repairing any existing violation first by demoting all but the most recently
  seen row per path; adds indexes for `superseded_by` and `(project_id,
  valid_until)`.
- **Proposal P1/P2 implemented** (ADR-0017): `valid_from`, `valid_until`,
  `superseded_by`, derived `supersedes` and the `decision` payload are now
  reachable through the domain model, the repositories and the API. They were
  columns no code touched.
- New endpoint `POST /api/v1/memories/{id}/supersede`, and `Memory.is_current`.
- Domain invariants now enforced, not documented: backwards validity window
  rejected, self-supersession rejected, `superseded_by` + `active` rejected,
  decision payload only on `type='decision'`.
- ADR-0017 and ADR-0018 added (19 ADRs).

### Verification performed
- Both bugs **reproduced first**, then re-tested after the fix: the orphan case
  now leaves 0 rows, and the duplicate-current insert is refused by the database
  with `UNIQUE constraint failed`.
- **53 tests pass** (was 37). 16 new in `tests/integration/test_write_integrity.py`
  covering atomicity, re-entrancy, uniqueness, supersession, temporal validity
  and a 4-thread × 8-write concurrency check asserting every memory ends with
  exactly one revision and one source ref.
- `ruff check` clean, `ruff format --check` clean, `tsc --noEmit` clean, frontend
  builds.
- Live end-to-end on the demo repo at schema v2: scan 4 files / 11 memories,
  re-scan 0/0, supersede closes the old window and the old record stays
  fetchable with 2 revisions and a derived inverse edge.

### Process note
One edit silently no-op'd because I used `replace` without an assertion — the
anchor had changed when ruff removed a then-unused `import json`. It surfaced as
a `NameError` in nine tests. Every edit in this session's scripts now asserts
exactly one match before writing.

### Known issues / blockers
1. **Writes now serialise.** Correct for a local single-user tool, but any
   future long-running write must be chunked rather than hold the lock.
2. `list_for_project` still returns superseded records by default;
   `MEMORY_MODEL.md` says they should be excluded unless asked. Deferred to
   Stage 4 with the richer explorer, since it changes UI behaviour.
3. The frontend does not yet surface validity, supersession or the decision
   payload — the API returns them, nothing renders them. Stage 4.
4. Proposal items **P3–P13 remain unapplied** and unreviewed.
5. ADR-0009 (Windows) and open questions Q1, Q2, Q4 still unanswered.

### Next safe task
Either (a) apply proposal **P4/P5** — the drift and conflict feasibility spikes
in Stages 3 and 4, which are now cheap because provenance and validity are both
reachable; or (b) begin **Stage 3** ingestion proper: `detect-secrets` content
scanning, `unidiff`, tree-sitter symbols, widened allowlist. P4 first is the
better order: it de-risks Stage 6 before more surface area is added.

---

## 2026-11-08 — Stage 2 fix: `honcho start` was broken on a clean PATH

### What changed
- `Procfile` web process now prepends `$HOME/.local/bin` itself, so Node is
  found without the caller exporting PATH.
- `frontend/vite.config.ts`: `strictPort: true`.

### Why
Pre-flighting the exact command the README tells you to run found two faults
that separate-process testing had hidden:

1. **`backend/.venv/bin/honcho start` failed** with `/bin/sh: 1: npm: not
   found`. Stage 2 verification had started uvicorn and npm as separate
   commands with PATH already exported, so the documented single command was
   never actually exercised. Reproduced with a sanitised PATH, then fixed.
2. **Vite was silently sliding to the next free port** (it reported 5175 while
   something else held 5173), which would make the documented URL wrong and
   point the API proxy at the wrong place. `strictPort` now fails loudly.

While checking, two **orphaned Vite processes from earlier test runs** (pids
10953, 12208, up 25 minutes) were found squatting 5173/5174. They made the
first fixed-Procfile check ambiguous, because curl to 5173 was being answered
by a stale server rather than the one just started. Both were terminated and
the check re-run against free ports.

### Verification performed
Re-run with a sanitised PATH, no stale listeners and an empty database:
Vite bound to 5173 (not a fallback port), `/` served HTTP 200 with
`<title>Kernote</title>`, `/health` ok at schema 1, the `/api` proxy returned
`[]` then completed register → scan (4 files, 4 captures, 11 memories) →
detail with citation `README.md:6-11` → re-scan creating 0 and 0. Ports were
released on shutdown.

Also re-run after the change: **37 tests passed**, ruff clean, frontend
typecheck and build clean.

### Lesson worth keeping
Verifying the components separately is not verifying the command in the
README. Pre-flight the documented entry point itself, on a PATH that does not
already have your fixes in it.

---

## 2026-11-08 — Stage 2 complete: application foundation, slice S1 proven

### What changed
- **Node 20.20.2 LTS installed** to `~/.local/opt/node` (tarball,
  checksum-verified against `SHASUMS256.txt`) with symlinks in `~/.local/bin`.
  No root needed: `sudo` requires a password here and apt only offered Node 18.
- **Backend** (`backend/`): venv, staged `requirements*.txt`, `pyproject.toml`
  with ruff + pytest config.
  - `db/migrations/0001_init.sql` — **generated** from the schema block in
    `ARCHITECTURE.md` §4, then extended with the 6 FTS5 synchronisation
    triggers and the `schema_meta` seed the document did not need.
  - `db/connection.py` — WAL, foreign keys ON, busy_timeout, forward-only
    idempotent migration runner.
  - `domain/models.py`, `domain/scoring.py` — pure; the MEMORY_MODEL rules are
    enforced in code, not merely documented.
  - `db/repositories/{projects,sources,memories}.py` — the only SQL writers.
  - `ingest/{walker,capture,gitmeta,normalize,pipeline}.py`,
    `ingest/extract/{markdown,manifests}.py`.
  - `api/` with 10 endpoints + `/health`; `main.py` binds 127.0.0.1 only.
- **Frontend** (`frontend/`): Vite + React + TS, Tailwind v4, react-router,
  TanStack Query, hand-written typed client, 7 routed screens. Dashboard and
  Memory Explorer are functional; the other five are explicit placeholders
  naming their stage and gate.
- **Orchestration**: `justfile`, `Procfile` (honcho), `scripts/dev.sh` fallback.
- **`samples/demo-repo/`** plus `NOTE.md`, and the README setup section.

### Verification performed
All of the following were run, and these are the actual results:

- **`ruff check backend`** → All checks passed. **`ruff format --check`** →
  38 files already formatted.
- **`pytest backend/tests`** → **37 passed**, 1 warning (a starlette/anyio
  deprecation, not our code).
- **`tsc --noEmit`** → clean. **`npm run build`** → built, 235 kB JS / 11.7 kB CSS.
- **Live run with both servers up**, exercised over real HTTP *through the Vite
  proxy*: register → scan (3 files, 3 captures, 10 memories, 1 refused) →
  list → detail → re-scan → counts. `.env` refused as `secret_suspected`.
- **S1 gate proven**: a second app instance against the same database file sees
  the same project, all 10 memories, their provenance and their revisions.

Invariants now covered by named tests: #1 idempotent re-scan (0 new captures,
0 new memories), #3 no provenance unless manual, #4 FTS index rebuildable,
#5 archived records stay fetchable, #7 secrets and gitignored files refused.
Plus: the walker does not modify the project tree, CRLF files stay readable,
and `0001_init.sql` cannot drift from `ARCHITECTURE.md` without a test failing.

**Three real bugs found and fixed during the stage, worth remembering:**
1. `executescript()` implicitly COMMITs, so an outer `BEGIN` was silently
   discarded and a failed migration could have half-applied. The transaction
   now lives *inside* the script.
2. `check_same_thread` was documented but not set, so every request from
   FastAPI's threadpool raised. Set, with the reasoning recorded in the code.
3. Tailwind v4.0.0 build failed because `@tailwindcss/vite@4.0.0` bundles
   `tailwindcss@4.3.5` internally — a version mismatch, not a CSS error as the
   message suggested. Both pinned to 4.3.5.

### Known issues / blockers
1. **Node is not on your shell `PATH`.** Adding it to `~/.bashrc` was blocked
   as unauthorised persistence, which is fair, so I kept it project-scoped: the
   `justfile` and `scripts/dev.sh` prepend `~/.local/bin` themselves. To use
   `node`/`npm` directly in your own terminal, add this yourself:
   `export PATH="$HOME/.local/bin:$PATH"` in `~/.bashrc`.
2. `samples/demo-repo/.env` is **intentionally not committed** (root
   `.gitignore` refuses it). `NOTE.md` explains how to recreate it by hand;
   tests use a generated hostile fixture instead of a committed fake secret.
3. The frontend client is hand-written. It is replaced by
   `openapi-typescript` in Stage 4, once the endpoint surface stops moving.
4. shadcn/ui is **not** installed yet despite `CLAUDE.md` naming it. Stage 2
   needed a shell and a table, not a component library; it lands in Stage 4
   when the Memory Explorer gets rich. Flagging rather than quietly skipping.
5. No Windows verification yet (ADR-0009 still `proposed`).
6. ADR-0009 and open questions Q1, Q2, Q4 remain unanswered.
7. Stage 6 still carries the product wedge and sits second-to-last.

### Next safe task
**Stage 3 (Days 6–9): repository ingestion.** In order: add `detect-secrets`,
`unidiff`, `tree-sitter` + `tree-sitter-language-pack` to
`requirements.txt`; replace the walker's path-based deny-list with
`detect-secrets` content scanning (ADR-0013); add `ingest/extract/adr.py` and
`ingest/extract/code_symbols.py` with per-language `tags.scm` (ADR-0012);
widen the allowlist to source files; record git blob hashes for tracked files
in `memory_source_refs`. Gate: slice S2 — the hostile fixture scans with every
refusal explained, and a repeat scan still creates nothing.

---

## 2026-11-07 — Day 2 (cont.): contract aligned with ADR-0015

### What changed
- `CLAUDE.md` scope item 3: "Ask Your Project" → "Cited evidence retrieval".
- `CLAUDE.md` scope item 6: now marked the differentiating feature, ref ADR-0015.
- Nothing else in `CLAUDE.md` touched. 2 insertions, 2 deletions.

### Verification performed
- Both edits applied by assertion-guarded script (exactly one match required
  each); `git diff` confirms 2 lines changed and no collateral edits.
- Full cross-check of the remaining `CLAUDE.md` clauses against all 17 ADRs.
  Compliant: the MiniLM baseline (ADR-0011 runs the same model via ONNX;
  ADR-0014 keeps MiniLM as the baseline unless our own numbers justify a swap),
  the vector-index clause (ADR-0003a validated and deferred on evidence — the
  clause working as intended), PyTorch confinement (ADR-0004), conditional MCP
  (scope 7 vs the F9 cut order — the kickoff guide itself made MCP conditional),
  and untested-language claims (ADR-0012 is structurally compliant).
- **One phrase left deliberately unedited:** scope item 8's "polished
  desktop-quality application screens" against ADR-0001, which ships a localhost
  app rather than a packaged desktop binary. Read as a claim about UI craft, not
  distribution, and already disclosed in README "Known limitations". Raise it if
  you meant a packaged binary — that would reopen ADR-0001 and cost Stage 8–9 time.

**Not verified:** still no application code, so no tests, lint, type or build
checks were run, and none are claimed.

### Known issues / blockers
1. **Node.js still not installed** — the only remaining Stage 2 blocker.
2. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 unanswered.
3. Stage 6 carries the product wedge and sits second-to-last.

### Next safe task
**Stage 2 (Days 3–5), slice S1**, on a feature branch: install Node 20 LTS →
re-run the toolchain probe → `backend/` skeleton with migration 0001 applied →
`frontend/` Vite shell routing the seven screens → `justfile` + `Procfile` →
then S1 end to end: register a project, scan README and config, save one memory
with provenance, see it in Memory Explorer, restart, prove it persisted.

---

## 2026-11-07 — Day 2 (cont.): planning set committed

### What changed
- `git config user.name` set to "Pavan" at **repository scope only** (it was
  unset globally and a commit needs it). Change it with
  `git config user.name "<your name>"`; there is no remote, so history can still
  be amended freely.
- Added **ADR-0016**: the roadmap, structure and architecture are ours; prior art
  is reference only. 17 ADRs total.
- First commit of the project: the whole planning foundation, 12 files.

### Verification performed
- Secret scan before staging: no private keys, no `ghp_`/`sk-`/`AKIA`/`xox`/JWT
  patterns, no assigned credentials, and the account email appears in no tracked
  file (git config only). `.gitignore` confirmed to exclude both
  `*:Zone.Identifier` artifacts.
- Schema re-executed against sqlite3 immediately before committing: 29 tables,
  FTS5 present.
- Reviewed the file list: 12 files, all documentation plus the source kickoff PDF.
  No code, no generated artifacts, no database files.

**Not verified:** there is still no application code, so no tests, lint, type or
build checks were run, and none are claimed.

### Known issues / blockers
1. **Node.js still not installed** — the Stage 2 blocker.
2. `CLAUDE.md` scope items 3 and 6 still use pre-ADR-0015 wording. Left for you
   to approve, since `CLAUDE.md` is the contract that overrides these docs.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 unanswered.
4. Committed on `master`, the default branch, because this is a fresh repo with
   no prior commits and no remote. Stage 2 onward should use feature branches.
5. Stage 6 carries the product wedge and sits second-to-last; front-loading a
   conflict-detection spike remains an open option.

### Next safe task
**Stage 2 (Days 3–5), slice S1.** In order: install Node 20 LTS → re-run the
toolchain probe → scaffold `backend/` with `schema.sql` and migration 0001
applied → `frontend/` Vite shell routing the seven screens → `justfile` and
`Procfile` → then S1 end to end: register a project, scan README and config, save
one memory with provenance, see it in Memory Explorer, restart, prove it
persisted.

---

## 2026-11-07 — Day 2 (cont.): ADR-0015 applied

### What changed
- **ADR-0015 accepted** and applied across the planning set.
- `PRODUCT_SPEC.md`: new §2 positioning ("reviewable project memory", explicitly
  not an agent memory server); §4 success criteria reordered with drift and
  conflict first and a conflict criterion added; F3 renamed **Cited Evidence
  Retrieval** and marked `Must (supporting)`; **F8 `Should` → `Must`**; feature
  detail reordered to lead with F5 and F8; §7 gains a **Conflict** acceptance
  row, retrieval now measured as citation correctness + abstention, and the four
  MemoryAgentBench evaluation axes; §9 lists the new names to re-screen.
- `ROADMAP.md`: Days 18–20 relabelled the differentiating milestone with
  conflict as `Must`; Days 14–17 renamed off "Project Brain"; S5 split into
  drift and conflict halves; **F8 removed from the scope-cut list** and added to
  "never cut", with F9 and F3 breadth cut first instead.
- `README.md`: positioning headline, conflict feature, and three honest
  limitations including the extractive-answers caveat.
- `ARCHITECTURE.md` §9: conflict-detection test fixtures and the evaluation axes.
- `COMPETITIVE_LANDSCAPE.md` §6 marked accepted.

### Verification performed
- Every edit applied by an assertion-guarded script: each replacement required
  exactly one match or the run aborted. One assertion did fire (the acceptance
  table wording differed from my draft), was inspected and corrected rather than
  forced.
- Consistency sweep via `grep` for "Ask Your Project", "Project Brain" and
  `F8 ... Should`. All surviving hits are in historical records (ADR-0015, the
  landscape doc, the Day 2 handoff entry) where the old wording is the point.
- No code exists, so no tests were run and none are claimed.

### Known issues / blockers
1. **`CLAUDE.md` line 17 still says "Ask Your Project using hybrid retrieval and
   source citations."** `CLAUDE.md` is the authoritative contract that overrides
   every document I write, so I did **not** edit it. The kickoff guide says to
   update it when scope intentionally changes, which just happened. Recommended
   minimal edit, for you to make or approve:
   - scope item 3 → `Cited evidence retrieval using hybrid retrieval and source citations.`
   - scope item 6 → `Knowledge conflict review (differentiating feature; see ADR-0015).`
   Nothing else in `CLAUDE.md` conflicts with ADR-0015 — conflict review was
   already scope item 6.
2. **Node.js still not installed** — blocks Days 3–5.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 still unanswered.
4. Days 18–20 is now the highest-risk milestone by design, since the wedge lives
   there and it is late in the sprint. Consider pulling a conflict-detection
   spike earlier if Days 10–13 run ahead.
5. The embedding ONNX artifact is still not vendored or hash-pinned.
6. Still nothing committed; the working tree is untracked.

### Next safe task
1. Approve the two `CLAUDE.md` line edits above (or make them yourself).
2. Install Node 20 LTS; re-run the toolchain probe.
3. Commit the whole planning set as one reviewed increment.
4. Read `projectmem`'s event schema and MCP tool surface before finalizing ours
   (ADR-0010).
5. Then the Day 3–5 scaffold and the S1 vertical slice.

---

## 2026-11-07 — Day 2: competitive scan

### What changed
- Created `docs/COMPETITIVE_LANDSCAPE.md` — the first competitive analysis for
  this project. The kickoff guide's §1 only screened the *name*, never asked
  whether the product exists.
- Appended **ADR-0015 (proposed)** to `docs/DECISIONS.md`: reposition on
  reviewable memory, promote F8 to `Must`, demote F3 to supporting, make drift
  granularity the technical claim, adopt MemoryAgentBench evaluation axes.
- Updated the README documentation index.
- **No application code written. No priorities changed in `PRODUCT_SPEC.md`** —
  ADR-0015 is proposed, not accepted, because it alters agreed scope.

### Verification performed
- 7 web searches across four competitor lanes, plus a full read of
  arXiv:2606.12329v1 (PROJECTMEM) including its §2 related-work survey.
- Every claim in the landscape document is attributed in its §8; vendor claims
  are marked as vendor sources.
- No code, so no tests were run and none are claimed.

**Material finding:** the thesis is already occupied. `projectmem` is an
open-source, local-first, typed, provenance-keeping, MCP-served project memory
layer (Jun 2026). `Codified Context` is plain-text, no-vector-DB, MCP-served,
with a drift detector. Neither was known to the kickoff guide.

**Countervailing finding:** `MemoryAgentBench` evaluates retention, update,
retrieval and conflict resolution, and no architecture masters all four. The two
unsolved ones — update and conflict — are our F5 (`Must`) and F8 (`Should`).
That priority ordering is backwards.

### Known issues / blockers
1. **Node.js still not installed** — blocks the Day 3–5 frontend milestone.
2. **ADR-0015 needs a decision.** It changes agreed scope, so Days 3+ should not
   start until it is accepted, rejected or amended.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 still unanswered.
4. Days 18–20 becomes the highest-risk milestone if F8 is promoted to `Must`.
5. The MiniLM/potion ONNX artifact is still not vendored or hash-pinned.
6. Still nothing committed; the working tree is untracked.

### Next safe task
1. Decide on ADR-0015, then apply its edits to `PRODUCT_SPEC.md` §4/§5/§7 and
   `ROADMAP.md` if accepted.
2. Read `projectmem`'s event schema and MCP tool surface (ADR-0010: borrow the
   solved parts) before finalizing our MCP surface.
3. Install Node 20 LTS; re-run the toolchain probe.
4. Commit the planning set as one reviewed increment.
5. Only then the Day 3–5 scaffold and the S1 vertical slice.

---

## 2026-11-06 — Day 1: planning foundation

### What changed
- `git init` run in the project root (the repo did not exist before this task).
- Created `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/MEMORY_MODEL.md`,
  `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/DEV_HANDOFF.md`.
- Created `README.md` and `.gitignore`.
- **No application code written.** Per the kickoff guide §10, the blueprint is
  presented for approval before any scaffold or implementation.

### Verification performed
- `git --version` → 2.43.0 · `python3 --version` → 3.12.3 — both fine.
- Toolchain probe for `node`, `npm`, `pnpm` — **all missing** (see blockers).
- `python3 -c "import venv"` → ok. `pip3` present at `/usr/bin/pip3`, but the
  system environment is PEP-668 externally-managed, so a venv is mandatory.
- **The `ARCHITECTURE.md` schema was executed, not just written.** The SQL block
  was extracted and run through `sqlite3` 3.45.1 with `foreign_keys=ON`:
  `executescript` succeeded and produced 29 tables, confirming every constraint,
  composite foreign key, partial index and both FTS5 virtual tables are valid and
  that FTS5 is compiled into the system SQLite. Re-run with:
  `python3 -c "import re,sqlite3,pathlib; sqlite3.connect(':memory:').executescript('\n'.join(re.findall(r'\`\`\`sql\n(.*?)\`\`\`', pathlib.Path('docs/ARCHITECTURE.md').read_text(), re.S)))"`
- `git check-ignore` confirms the two `:Zone.Identifier` files are ignored.
- Documents reviewed against `CLAUDE.md` for contradictions; none found. Where
  this planning set adds a position `CLAUDE.md` did not take (extraction
  strategy, embedding runtime, vector search), it is recorded as an ADR rather
  than assumed silently.

**Not verified:** nothing executable exists yet, so no tests were run. No test
suite, lint or type-check has been claimed as passing because none exists.

### Known issues / blockers
1. **Node.js is not installed** — blocks the Day 3–5 frontend milestone. Need
   Node 20 LTS (`nvm install 20` or the distro package) before Nov 8.
2. **ADR-0009 is `proposed`, not accepted** — needs your call on whether native
   Windows is a Day 25 release target or best-effort (open question Q3). Affects
   whether Days 3–5 absorb a Windows environment spike.
3. **Open questions Q1, Q2, Q4** in `PRODUCT_SPEC.md` §10 have working defaults
   recorded but are unconfirmed.
4. `CLAUDE.md:Zone.Identifier` and `Kernote_Project_Kickoff_Guide.pdf:Zone.Identifier`
   are WSL artifacts from the Windows copy. Harmless; now gitignored rather than
   deleted. Remove them whenever you like.
5. The MiniLM ONNX artifact (ADR-0004) is not yet vendored or hash-pinned. Needed
   before the Day 14–17 retrieval milestone.
6. Nothing is committed yet — the working tree is untracked. `CLAUDE.md` step 9
   says not to commit unless asked.

### Next safe task
**Day 2 — close the blueprint, then scaffold.** In order:

1. Get approval on the six documents and a decision on ADR-0009 plus Q1–Q4.
2. Install Node 20 LTS and re-run the toolchain probe.
3. Make the first commit of the planning set.
4. Then, and only then, the Day 3–5 scaffold as its own task: `backend/`
   skeleton with `schema.sql` + migration 0001 applied, `frontend/` Vite shell
   with routing for the seven screens, `scripts/dev.sh`, and the S1 vertical
   slice (register project → scan README/config → one memory with provenance →
   visible in Memory Explorer → survives restart).

Do not start step 4 before steps 1–3. The slice in step 4 is the gate for the
whole ingestion milestone and it is worth having the schema reviewed first.
