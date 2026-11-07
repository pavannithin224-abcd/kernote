# Kernote — Developer Handoff

Updated at the end of every task, per `CLAUDE.md` §"Git and task workflow" step 7.
Newest entry first.

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
