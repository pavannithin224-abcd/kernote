# Kernote — Developer Handoff

Updated at the end of every task, per `CLAUDE.md` §"Git and task workflow" step 7.
Newest entry first.

---

## 2026-11-09 — Stage 6 defect sweep

### Probed and found sound
- **Change Impact at width.** A 1,200-file commit range works: SQLite's
  parameter limit here is **250,000**, not the 999 often assumed. Now pinned by
  a test rather than assumed.
- Merge chains cannot form by accident — an already-superseded record is
  refused as a merge input.

### Bugs found and fixed (ADR-0025a)
1. **Approval silently reverted a human's edit.** The merged content is
   computed when the duplicate is *detected*; editing the keeper and then
   approving applied the stale preview over the newer wording. This is the
   worst defect found in the project so far — everything else produces a bad
   *suggestion*, this destroyed deliberate work under a button that promises
   nothing is lost. The preview now carries a fingerprint of each input and
   approval refuses when either has changed, leaving the proposal pending so a
   fresh analysis replaces it.
2. **Merging into an archived record succeeded.** `supersede_into` checked the
   absorbed record's status but never the keeper's, so merged wording could
   land somewhere hidden from every listing. Both sides must now be live.

### Verification performed
- **328 tests pass** (was 321). 7 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Re-probed: an edit before approval is refused with the edit intact; an
  archived keeper is refused; an untouched proposal still merges cleanly
  (citations 1 → 2, 2 revisions).

### Known issues / blockers
1. **Approval is still not reversible.** The data supports an undo — the
   absorbed record is byte-intact and the supersession is recorded — but there
   is no endpoint. Worth adding before anyone relies on the merge button.
2. Resolved findings are closed, not re-openable.
3. **ADR-0014's four-way embedding benchmark remains the biggest gap**, and it
   needs the labelled question set (P11). That plus `ranx` metrics is the
   Stage 8 story and the oldest outstanding item in the project.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

No known Stage 6 defects remain open.

### Next safe task
**Stage 8's evaluation work is the higher-value target** even though Stage 7
comes first in the roadmap: F9 (MCP) is first on the scope-cut list, while the
labelled question set, `ranx` metrics and the embedding benchmark have been
deferred since Day 1 and are what the Day-25 acceptance criteria actually
measure.

---

## 2026-11-09 — Stage 6: the review flow

The differentiating milestone. Detection was proven by the P4/P5 spikes; this
is the half where a human decides and the decision is recorded.

### What changed
- **`memories.supersede_into()`** — merge into an *existing* record, in one
  transaction: carries the absorbed record's citations onto the keeper, writes
  revisions on both, closes the absorbed one with `superseded_by` and a
  `valid_until`, records a typed edge. Nothing deleted (ADR-0025).
- **`maintain/review.py`** — `approve_proposal`, `reject_proposal`,
  `resolve_finding`. Approval **verifies its own promise**: it compares the
  citations the preview advertised against the keeper's actual citations and
  rolls back if any is missing.
- **`maintain/impact.py`** — Change Impact over a commit range, with `direct`
  vs `same_file` classification (ADR-0026).
- **`ingest/gitmeta.py`** — `resolve`, `changed_files`, `file_diff`,
  `recent_commits`.
- **Migration 0005** — `feedback.verdict` now allows `'resolved'`.
- **API** — approve, reject, resolve, impact, commits. 22 endpoints.
- **UI** — the Memory Intelligence Center's buttons now do something:
  *Approve merge* / *Not a duplicate* on proposals, *Needs attention* /
  *False positive* on findings, with the citation delta reported back. New
  **Change Impact** screen with a commit picker.
- ADR-0025 and ADR-0026 added (33 ADRs).

### Verification performed
- **321 tests pass** (was 301). 20 new.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP on this repository:** scan 105 files / 348 memories →
  analyze → approve a real proposal → **citations 1 → 2, 2 revisions, promise
  held**, absorbed record still fetchable with its wording intact, second
  approval returns **409**. Resolve a conflict finding → 200. Change Impact
  `HEAD~1..HEAD` → 6 files, 41 memories in them, **5 directly affected**.

### Two bugs found while building
1. **A CHECK constraint disagreed with the code.** `findings.status` has always
   allowed `'resolved'`, but `feedback.verdict` did not, so resolving a finding
   as resolved passed every application check and then failed on the last
   statement — the review flow's own happy path. Migration 0005 rebuilds the
   table; SQLite cannot alter a CHECK.
2. **A fixture produced no memories** because its section body was under the
   40-character floor, which surfaced as an `IndexError` rather than a clear
   failure. Lengthened; worth remembering that the extractor's minimum body
   length is a silent filter in tests.

### Known issues / blockers
1. **Approval is not reversible.** Superseding is recorded and the absorbed
   record is intact, so an undo is *possible* — but there is no endpoint for
   it. Worth adding before anyone relies on the merge button.
2. Resolved findings are closed, not re-openable.
3. **ADR-0014's four-way benchmark is still the biggest gap**, and it needs the
   labelled question set (P11). That plus `ranx` metrics is the Stage 8 story.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

### Next safe task
Either the **Stage 6 defect sweep**, or **Stage 7 (Days 21-22): agent
delivery** — the context-bundle export and the four read-only MCP tools. Note
that F9 is the first thing on the scope-cut list, so Stage 8's evaluation work
(the labelled question set, `ranx` metrics, the embedding benchmark) is the
higher-value target if time is short.

---

## 2026-11-09 — Stage 5 defect sweep

### Probed and found sound
- **Latency.** 450 vectors: search p50 **5 ms**, a full ask **7 ms**. Loading
  the whole matrix per query is not a problem at this scale.
- **Index build.** 322 memories + 316 chunks in ~41 s, then fully incremental.

### Bugs found and fixed (ADR-0024a, migration 0004)
1. **An edited memory kept its old vector**, so semantic search matched text
   the project no longer contained — the derived index diverging from the
   source of truth. `embeddings.source_hash` now records exactly what was
   embedded. `updated_at` was the tempting alternative and is wrong:
   importance refinement touches it without changing a word.
2. **Vectors outlived their targets.** `embeddings` has a polymorphic target so
   it cannot carry a foreign key; deleting a project left its vectors forever.
   `AFTER DELETE` triggers now do what the FK cannot.
3. **The stemmer over-matched**: a fixed two-character chop turned "import"
   into "impo", a prefix of "important". Now strips known suffixes and compares
   whole stemmed tokens, with a `+e` variant for "deleted"/"delete".
4. **`CI`, `DB`, `UI`, `ML` were unsearchable** — the content-term floor
   excluded them, so "what does the CI do" could only abstain.

### Verification performed
- **301 tests pass** (was 287). 14 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Both bugs re-probed after the fix: an edit now re-embeds exactly one record
  and `search("Cassandra")` finds it; a project delete leaves **0** orphans.
- 10 of 10 stemming cases correct in both directions.

### A self-reference worth noting
Asking *"what is the airspeed velocity of an unladen swallow"* against this
repository now returns `evidence_found` — because ADR-0024 documents that exact
sentence as its own worked example, so the corpus genuinely contains it. Not a
regression: the controlled fixtures still assert abstention. The same
self-reference bit the secret scanner in Stage 3, and it is worth remembering
that a project documenting its own behaviour becomes part of its own corpus.

### Known issues / blockers
1. **ADR-0014's four-way benchmark is still outstanding.** `fastembed` does not
   carry the potion models, so they need `model2vec` as a second runtime (an
   ADR-0011 amendment), and the benchmark needs the labelled question set (P11).
2. No `ranx` metrics yet — Recall@k, MRR, nDCG belong with that set.
3. Stage 6 work: proposal approval, finding resolution, Change Impact.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

No known Stage 5 defects remain open.

### Next safe task
**Stage 6 (Days 18-20) — the differentiating milestone.** Approval for
consolidation proposals (writing revisions and `superseded_by` through the
existing `supersede()` path), resolution for findings, and the Change Impact
screen over a commit range. Both detection halves are already proven.

---

## 2026-11-09 — Stage 5: recall and evidence retrieval

### What changed
- **`retrieval/fts.py`** — keyword search with a safe MATCH builder.
- **`retrieval/embed.py`** — `fastembed` (ONNX, no torch), **opt-in** with a
  filesystem-only status check (ADR-0023).
- **`retrieval/vector.py`** — float32 BLOBs, cosine by one numpy matmul,
  incremental index, project-scoped, `clear()` for reindex.
- **`retrieval/hybrid.py`** — Reciprocal Rank Fusion plus small boosts; every
  result explains its rank (ADR-0024).
- **`retrieval/answer.py`** — evidence composition with three outcomes and
  labelled, cited items; turns persisted to `ask_turns` with a full trace.
- **`api/routers/ask.py`** — `POST /ask`, `GET /embeddings`,
  `POST /embeddings/build`. 17 endpoints total.
- **Project Intelligence screen** — asks, renders labelled evidence with
  citations and matched terms, shows unknowns, and offers the opt-in download
  with its size and destination stated.
- ADR-0023 and ADR-0024 added (31 ADRs).

### Verification performed
- **287 tests pass** (was 245). 42 new, with the semantic ones skipped when the
  model is not cached so the suite never reaches the network.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP**: 102 files → 319 memories → index 319 memories + 313
  chunks → three questions answered with citations, session reused across turns.
- 8 of 8 probe questions classify correctly on this repository.

### Five defects found by measuring first
1. **FTS5 crashed on 8 of 10 realistic questions** — `"what's the setup?"`,
   `sqlite-vec`, `C++`, `100%`, `""`, `OR`. Measured *before* writing the
   module, which is why the safe MATCH builder exists at all rather than being
   bolted on after a crash report. Now 0 of 13.
2. **Stopwords manufactured support.** "airspeed velocity of an unladen
   swallow" matched "an/is/of/the" and reported `evidence_found`.
3. **Exact substring matching abstained wrongly.** "secrets" missed ADR-0020a's
   "Secret refusal"; fixed with a prefix stem against the item's full text.
4. **One coincidental word passed as support** — `CLAUDE.md` contains "Do not
   **swallow** errors", so the nonsense question passed again. Support now
   needs `min(2, content_terms)` matches.
5. **The model cache sat under `data_dir`**, so relocating the database meant
   another 90 MB download. Found when tests pointed `data_dir` at a temp
   directory and the model silently vanished. Weights now live in the user
   cache.

### Known issues / blockers
1. **The honest cost of ADR-0006 is now visible and pinned by a test:** *"which
   database did we choose"* returns `weak_evidence`, because the ADR says
   "PostgreSQL" and "persistence" and never "database". A human would answer
   it; term overlap cannot. This is the clearest place an optional model
   adapter would earn its keep.
2. **ADR-0014's four-way benchmark is not done.** `fastembed` does not carry
   the potion models, so `potion-code-16M-v2` and `potion-retrieval-32M` need
   `model2vec` as a second runtime — an ADR-0011 amendment, to be decided
   deliberately. The benchmark also needs the labelled question set (P11).
2. No `ranx` metrics yet: Recall@k, MRR and nDCG belong with the labelled set.
3. Proposal approval and finding resolution remain Stage 6.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
Either **the Stage 5 defect sweep** (the pattern that has found real bugs at
every stage), or **Stage 6 (Days 18-20)** — the differentiating milestone:
approval for consolidation proposals, resolution for findings, and the Change
Impact screen over a commit range. Stage 6's detection halves are already
proven by the P4/P5 spikes.

---

## 2026-11-08 — Stage 4 defect sweep

Probed Stage 4 adversarially before starting Stage 5, as with Stage 3.

### Probed and found sound
- **Scale.** 120 files scanned and analysed in well under a second; the
  detectors are not the bottleneck.
- **Importance refinement** is idempotent (migration 0003 holds).

### Bugs found and fixed (ADR-0021a)
1. **A filler-only title was never compared.** "Overview", "Commands" and
   "This is it" are entirely filler words, so the bucket signature was empty
   and 120 files sharing an `## Overview` heading gave `compared=0`. Fixing
   bucketing alone was insufficient — `title_score` used the same stripped
   tokens, so Jaccard returned 0.0 and correctly-bucketed pairs still scored
   zero. Bucketing and scoring now share one fallback.
2. **Unbounded pairwise work.** A 120-member bucket is 7140 pairs. Buckets
   above 5 members now compare against the highest-importance record instead
   of every pair: 24 actionable statements rather than 300. Buckets above 25
   are truncated and candidates capped at 200, both logged.
3. **Cross-granularity false positives.** A section in one file and a fenced
   block in another share a title and an overlapping body — 4 candidates where
   2 were real. Pairs now require matching `extraction_method`.
4. **Unbounded entity derivation.** A 400-dependency manifest produced 401
   entities and ~800 writes for one memory. Capped at 60, paths first.
5. **Dead code**: `entities.fan_in()`, defined and never called.

### Verification performed
- **245 tests pass** (was 236). 9 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- All five probe cases correct: 120 identical sections → 24 bounded
  candidates; cross-file section/commands → 2; planted duplicate → 1;
  same-title-different-body → 0; unrelated → 0.
- Dogfood: comparisons fell from **1851 to 168**, candidates from 2 to **1**,
  and the remaining one is genuine with citations provably preserved.

### Known issues / blockers
1. Proposal approval and finding resolution are still unimplemented, so the
   queue only grows. Stage 6, and the UI says so.
2. Fan-in adjusts nothing on this repository (each command appears once).
3. `SecretWarning` has no findings row (needs a new `findings.kind`).
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the tree-sitter wheels.

No known Stage 4 defects remain open.

### Next safe task
**Stage 5 (Days 14-17): recall and evidence retrieval.** FTS5 keyword search,
`fastembed` embeddings (ADR-0011), the four-way model benchmark (ADR-0014),
hybrid fusion, and the extractive composer that labels evidence, inference and
unknowns. `chunks`, both FTS tables and `embeddings` are wired and waiting.

---

## 2026-11-08 — Stage 4: core memory engine

### What changed
- **`ingest/entities.py`** — entity derivation and linking. `entities` and
  `memory_entities` were created in migration 0001 and never written to; they
  are now populated during a scan from data already extracted (source paths,
  manifest package names, the first bare word of a command, decision options).
- **`maintain/duplicates.py`** — duplicate candidates and consolidation
  proposals with a before/after preview (ADR-0021). Detection proposes;
  nothing merges.
- **`maintain/importance.py`** — fan-in refinement that explains itself in
  `importance_reason` (ADR-0022).
- **Migration 0003** — `memories.importance_base`, so refinement is idempotent.
- **`api/routers/maintenance.py`** — `POST /projects/{id}/analyze`,
  `GET /findings`, `GET /proposals`. Analysis is explicit rather than automatic
  on scan: it writes findings, and a scan's meaning ("what is in the
  repository") stays separate from analysis ("what looks wrong").
- **Frontend** — Memory Explorer now renders **validity**, **supersession**
  (with links in both directions) and the **decision payload**, all of which
  the API had been returning and nothing displayed. New Memory Intelligence
  Center with the review queue, severity, diff hunks and side-by-side
  consolidation previews.
- ADR-0021 and ADR-0022 added.

### Verification performed
- **236 tests pass** (was 217). 19 new in `test_stage4_memory_engine.py`.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP** on this repository: scan 95 files / 285 memories →
  analyze → 285 refs checked, 1 conflict, 2 duplicate candidates, 2 proposals,
  3 open findings. 29 decision memories, **27 with a parsed payload**. The
  proposal preview was asserted to preserve every citation from both inputs.

### Four measurements that set the thresholds
Each is a defect found by running against our own repository, not a guess.

1. **8 false duplicates out of 8** from title similarity alone: `function
   create` in two repository modules, `function get`, `function extract` —
   same identifier, different function. A candidate now also requires body
   overlap, and symbol memories are excluded entirely since they are keyed by
   (file, qualified name) and unique by construction.
2. **The obvious duplicate was invisible** when bucketing by shared entity
   alone: two root-level files have no shared `module`, so identical "Running
   the tests" sections in `README.md` and `CONTRIBUTING.md` were never
   compared. Title-signature bucketing was added.
3. **Every `## Setup` section duplicated its own fenced block.** Parent and
   child, not two claims — memories whose line ranges nest are now skipped.
4. **Importance adjusted 271 of 271 memories.** Every memory under `docs/`
   shares the `docs` module, so file and module fan-in ranks nothing. Those
   kinds were removed from the weight table.

Plus two bugs in my own Stage 4 code: entity derivation produced commands
literally named ```` ``` ```` and ```` ```bash ```` from section-derived
procedure memories (now only real command lists yield command entities), and
fan-in was applied to the current score rather than a base, so importance crept
upward on every analysis — caught by the idempotency test and fixed with
migration 0003.

### Known issues / blockers
1. **Proposal approval is not implemented.** The preview exists and says so in
   the UI; applying a merge is Stage 6, where it must write revisions and set
   `superseded_by` using the existing `supersede()` path.
2. Fan-in currently adjusts nothing on this repository because each command
   appears in a single memory. Honest, and the signal is exercised by a fixture
   instead. A larger repo will exercise it for real.
3. Findings have no resolve/dismiss endpoint yet, so the queue only grows.
   Stage 6, together with approval.
4. `SecretWarning` still has no findings row (needs a new `findings.kind`).
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the tree-sitter wheels.

### Next safe task
**Stage 5 (Days 14-17): recall and evidence retrieval.** FTS5 keyword search,
`fastembed` embeddings (ADR-0011) with the four-way model benchmark (ADR-0014),
hybrid fusion, and the extractive answer composer that labels evidence,
inference and unknowns. The `embeddings` table and both FTS tables are wired
and waiting; `chunks` is populated for both prose and code.

---

## 2026-11-08 — Stage 3 defect sweep, before starting Stage 4

Probed the Stage 3 code adversarially rather than working from the known-issue
list, then fixed everything confirmed.

### Probed and found sound (no change needed)
- **Symlink directory loops** do not hang the walker: `Path.rglob` does not
  follow directory symlinks. A child-to-parent loop returned in 0.00s.
- **The cached tree-sitter parser is safe under threads** in practice: 6
  threads x 12 parses produced one consistent symbol count and no errors.
- **No ReDoS in the ADR regexes**: a 40x200-character alternatives block and a
  5000-word decision line both parsed in under 0.01s.

### Bugs found and fixed
1. **A real credential was stored, only warned about** (ADR-0020b). The
   two-tier policy discriminated on the *detector*, but what distinguishes
   `DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"` from `SECRET_SUSPECTED =
   "secret_suspected"` is the *value*. A keyword hit now refuses the file when
   the value is credential-shaped. Detector co-occurrence was tried first and
   measured insufficient: that password produces no entropy hit.
2. **Superseded and archived memories were served as current.**
   `MEMORY_MODEL.md` says they are excluded unless asked; they were in every
   listing. Now hidden by default, still reachable by id, by explicit status,
   or with `include_inactive`. The Memory Explorer gained "Current" /
   "All, including replaced" / "Superseded" options.
3. **Prose was compared as a command list.** `manual` procedure memories had
   their sentences split into pseudo-commands. Now gated on command shape.
4. **Reindentation inside a code fence was called cosmetic** — the limitation
   ADR-0019a shipped with a test documenting. Inside a fence, indentation is
   compared but trailing whitespace is not, so a Python reindent is semantic
   while saving a file is still cosmetic.

### Three bugs in my own fixes, caught by my own tests
- `password: 'Xk92Lm04Qp77Zr'` was missed because the key was split on `=`
  only, making the whole line the "key" so the value looked self-referential.
- `PASSWORD = "<your-password>"` was flagged: the template pattern required
  `<lowercase>` and the value contained a hyphen.
- `PASSWORD = os.environ["DB_PASSWORD"]` was flagged, because the quoted part
  is a *key name*. An indirection guard now covers `environ`, `getenv`,
  `process.env`, `config.get` and similar.

### One regression I caused and caught by dogfooding
The stricter heuristic refused `docs/DECISIONS.md`, dropping decision memories
from 31 to **8** — our own decision log, lost for containing the example
`password = "hunter2..."` inside a sentence. Fixed with a prose guard: a line
whose text outside the quoted literal runs to 8+ words is read as prose, not an
assignment. Any project that documents its security decisions would have hit
this.

### Verification performed
- **217 tests pass** (was 183). 32 new in `test_stage3_fixes.py`, plus the
  fence tests rewritten to assert the fix rather than the limitation.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Dogfood: **91 files, 291 memories, 33 decisions**. Refusals are exactly the
  four files that genuinely contain credential-format literals (three test
  fixtures, the demo `.env`); our own docs and source that merely discuss
  secrets are imported with a warning.
- Drift on a clean tree: 0 high, 0 medium, 0 low across 260 source refs.

### Known issues / blockers
1. The value-shape heuristic is necessarily imperfect in both directions. Both
   are pinned by tests (13 detection, 12 non-detection), and the escape hatch
   is `# pragma: allowlist secret`, which detect-secrets honours in code files
   but not reliably in Markdown.
2. `SecretWarning` still has no review-queue entry; that needs a new
   `findings.kind` and a migration. Stage 6.
3. Task-name matching in conflict detection is still literal (`Setup` vs
   `Set up`). Deferred to Stage 6 against the P11 evaluation set, because
   widening it trades false negatives for false positives.
4. Four languages only, by design. No Windows verification of the tree-sitter
   wheels yet (risk R11); they load cleanly on Linux.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
**Stage 4 (Days 10-13): core memory engine.** Dedup candidate generation,
importance refinement over the symbol graph, and the Memory Explorer work that
surfaces validity, supersession and the decision payload the API already
returns. No known Stage 3 defects remain open.

---

## 2026-11-08 — Stage 3 part 2: tree-sitter symbols, widened allowlist

Stage 3 is now complete.

### What changed
- **`ingest/extract/code_symbols.py`** + `queries/{python,typescript,tsx,
  javascript}/tags.scm` — tree-sitter symbol extraction (ADR-0012, ADR-0012a).
  One `architecture` memory per top-level definition, names qualified by their
  enclosing class, private helpers skipped, test files excluded.
- **Walker allowlist widened to source files**, derived from the same language
  table as the extractor, so the allowlist cannot drift ahead of what we can
  actually parse.
- Source files are **chunked by symbol**, so each chunk has a real line range
  and a name for Stage 5 retrieval.
- **Two-tier secret policy** (ADR-0020a): format detectors refuse, keyword and
  entropy detectors warn via a new `SecretWarning` on the scan result.
- Path deny-list narrowed to configuration filenames.
- **Refactor:** findings persistence moved to `db/repositories/findings.py`,
  with `Finding`/`FindingKind`/`Severity` as domain types. `ingest/` needs to
  raise findings and `ARCHITECTURE.md` forbids `ingest` depending on
  `maintain`, so the repository is the only correct home.
- ADR-0012a and ADR-0020a added (23 ADRs).

### Verification performed
- **183 tests pass** (was 146). 37 new: 23 code symbols, 14 secret policy.
- `ruff check` / `format --check` clean. Frontend typechecks and builds.
- Every shipped `tags.scm` is asserted to compile against its grammar, and
  `supported_languages()` is asserted to equal exactly the set with query files.
- Dogfood on this repository: **91 files, 285 memories, 320 chunks, 3.1s** —
  133 symbol memories, 24 ADR memories, 117 section memories.

### Four more bugs found by dogfooding
1. **`secrets.py` was refused by the path deny-list.** `secrets.*` matched our
   own module. A file named `secrets.py` is ordinary Python; the pattern is now
   limited to config extensions.
2. **`SECRET_SUSPECTED = "secret_suspected"` refused `domain/models.py`**, and
   "possible secret" refused `Dashboard.tsx`. The keyword detector fires on the
   *name*, not the value. Hence the two-tier policy — refusals on this repo
   went from 6 files to 3, all 3 correct.
3. **19 architecture memories from one test file.** Tests describe behaviour,
   not module shape; test paths are now excluded, with the matcher anchored so
   "latest" and "protest" are not caught.
4. **TypeScript class methods were invisible.** The query captured the class
   but had no `method_definition` pattern, so a class's whole surface was
   missing. Caught by a test asserting `method Renderer.render`.

### Process note
My edit helper printed "ok" before writing to disk, so when a later assertion
aborted the script, earlier edits that had reported success were silently
discarded — and I chased a `NameError` twice as a result. The helper now writes
after each edit, so "ok" means it is on disk.

### Known issues / blockers
1. **A real `password = "..."` with no recognisable format is now imported**
   with a warning rather than refused. That is the deliberate cost of ADR-0020a
   and the reason the warning exists.
2. `SecretWarning` reaches the scan result but has no review-queue entry; that
   needs a new `findings.kind` and therefore a migration. Stage 6.
3. Four languages only. Adding one is a query file plus a test — by design.
4. Symbol `content` is signature plus docstring, while the line range spans the
   whole definition. Intentional (drift should fire on any change inside the
   function) but it means `content` is not the full source.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.
6. No Windows verification of the tree-sitter wheels yet (risk R11); it loads
   cleanly on Linux.

### Next safe task
**Stage 4 (Days 10-13): core memory engine.** Dedup candidate generation,
importance refinement using the symbol graph, and the Memory Explorer work that
surfaces validity, supersession and the decision payload the API already
returns. The Stage 4 conflict feasibility gate is already met.

---

## 2026-11-08 — Stage 3 part 1: secret scanning and ADR extraction

### What changed
- **`ingest/secrets.py`** — content-level secret refusal via `detect-secrets`
  (ADR-0013), wired into the pipeline before any capture is persisted. A file
  with a credential is refused whole and recorded as `secret_suspected`.
- **`ingest/extract/adr.py`** — `rule:adr`, handling three conventions:
  `adr-tools` / MADR one-decision-per-file, a combined log, and a plain
  `## Decision:` heading. Produces `status`, `chosen`, `alternatives`,
  `decided_on`, and sets `valid_from` from the decision date (ADR-0017).
- `extract/markdown.py` — heading classification now matches on word
  boundaries with optional plurals, not substrings.
- ADR-0020 added (21 ADRs).

### Verification performed
- **146 tests pass** (was 113). 19 new: 10 secret scanning, 9 ADR extraction.
- `ruff check` / `format --check` clean. Frontend typechecks and builds.
- **End-to-end payoff:** two opposing `adr-tools` files scanned from disk now
  produce a decision conflict — `0001-use-sqlite.md` chose SQLite,
  `0004-use-postgresql.md` chose PostgreSQL, both valid, one finding holding
  both claims with citations. Before this the signal could only fire on
  hand-written memories.
- Secret refusal asserted at the database level: after scanning a file with a
  pasted GitHub token, `source_captures.text` and `memories.content` contain
  zero occurrences of it.

### Four bugs found by dogfooding Kernote on its own repository
Scanning our own repo was worth more than any synthetic fixture.

1. **`scan_line` would have refused every file.** The obvious detect-secrets
   entry point bypasses the library's filters and reports high-entropy hits on
   ordinary prose, on `pip install -r requirements.txt` and on
   `fastapi==0.115.6`. `scan_file` applies the filter chain and returned zero
   hits on a benign documentation fixture while catching a GitHub token and an
   AWS key with correct line numbers.
2. **Numbered headings are not ADRs.** `## 1. Shape` and
   `## 2. Repository structure` in `ARCHITECTURE.md` were extracted as
   decisions — **44 false records out of 66**. The bare `N. Title` form is now
   only trusted inside a path that already looks like a decision document.
3. **One decision per file is the document, not a section.** The first
   implementation treated `## Status` / `## Decision` as candidate ADRs and so
   extracted *nothing* from `adr-tools` and MADR files, because no sub-section
   carries both a decision heading and a long enough body.
4. **`"adr"` was matched as a substring**, so "Quadratic scoring" and
   "Squadron layout" classified as decisions. Fixing it with a bare `\b`
   boundary then broke plurals — "Conventions" stopped matching "convention",
   which substring matching had handled by accident. Both are now covered by
   tests.

Also: the ADR extractor now owns its document, suppressing the generic section
extractor for it. Without that, every `## Decision` sub-heading produced a
second payload-less "Decision" memory duplicating the real record.

### Known issues / blockers
1. **`chosen` parses from 2 of 22 of our own ADRs.** Our house style states the
   decision as a paragraph ("Ship a Vite frontend plus…"), which is not
   reliably parseable. The extractor declines rather than guessing, because a
   fabricated option produces a fabricated conflict. `adr-tools` and MADR
   conventions parse correctly. This limits the decision-conflict signal to
   repos using a structured ADR format — worth stating plainly rather than
   claiming broad coverage.
2. A file containing one credential is refused **whole**, so a README with an
   example token loses its real content. `# pragma: allowlist secret` is the
   escape hatch in code files; it is unreliable in Markdown, where
   detect-secrets does not recognise `#` as a comment.
3. If a previously clean file gains a credential, its existing memories stay
   and their pinned hash goes stale, so drift flags them. Coherent, but the
   review UI should eventually say why the source vanished.
4. **Stage 3 is not finished:** tree-sitter symbol extraction (ADR-0012) and
   the widened source-file allowlist are still to do. That is the larger and
   riskier half — a native wheel (risk R11) plus per-language `tags.scm`.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
**Stage 3 part 2:** `tree-sitter` + `tree-sitter-language-pack` with
per-language `tags.scm` seeded from Aider's queries (ADR-0012, attributed),
and the allowlist widened to source files. Gate: slice S2 on a repository with
real code, plus a Windows note for risk R11.

---

## 2026-11-08 — Problem 2 fixed: cosmetic changes are no longer "stale"

### The problem
Drift severity had two bands, so **any** whitespace change inside a citation
was high severity: trailing spaces added on editor save, a rewrapped
paragraph, an inserted blank line, a reindented block. The first run of a docs
formatter over a real repository would have flagged every citation in every
touched line as high — risk R10 arriving by a second route, since the overlap
test exists precisely to stop "the file changed" meaning "everything is stale".

### What changed (ADR-0019a)
A third band. Each hunk is now classified by comparing its removed and added
lines with all whitespace collapsed, which also neutralises reflow. Then per
citation: **high** if an overlapping hunk's text really differs, **medium** if
overlapping but only formatting moved, **low** if the change missed the cited
lines. Evidence gains `cosmetic_only` and `substantive_hunks`.

A cosmetic change still raises a finding rather than silently re-pinning the
hash, because re-pinning is a write to canonical memory and `CLAUDE.md`
requires approval for that. The medium explanation says what accepting it does.

### Verification performed
Measured on the real `samples/demo-repo`:

| Scenario | Before | After |
|---|---|---|
| Whole-file reformat (trailing whitespace everywhere) | 7 high | **0 high / 7 medium** |
| Genuine one-line word change | 1 high / 6 low | **1 high / 6 low** (unchanged) |
| Both together in one file | — | **1 high / 1 medium / 5 low** |

The third row is the important one: each citation is judged on its own lines,
so a reflowed section and a rewritten section in the same file get different
verdicts.

- **113 tests pass** (was 102). 11 new: a 7-case parametrised
  cosmetic/semantic matrix, the formatter scenario, an over-correction guard
  asserting a real edit is still high, the mixed-file case, and one test that
  documents a limitation rather than a desire.
- `ruff check` and `ruff format --check` clean.

### Known issues / blockers
1. **Indentation inside code fences is treated as cosmetic.** It is significant
   in Python, YAML and Makefiles. A test asserts the current behaviour and says
   in its failure message that it documents behaviour, not intent. Fixing it
   needs fence-language awareness — Stage 6, measured against the P11 set.
2. **Problem 3** (prose split into pseudo-commands for `manual` memories) and
   **Problem 4** (literal task-name matching) remain open, both deferred to
   Stage 6 because widening them trades false negatives for false positives and
   needs the labelled evaluation set.
3. Proposal items P3, P6-P13 remain unapplied. ADR-0009 and Q1/Q2/Q4 open.
4. Neither detector is wired to an endpoint or the UI. Stage 6.

### Next safe task
**Stage 3 proper (Days 6-9).** `detect-secrets` content scanning to replace the
path deny-list (ADR-0013); `rule:adr` extraction, which is what will finally
feed the decision-conflict signal with real data instead of only manual
memories; tree-sitter symbols with per-language `tags.scm` (ADR-0012); the
allowlist widened to source files. Gate: slice S2, plus the Stage 3 drift gate
which is already met.

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
