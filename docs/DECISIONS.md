# Kernote — Decision Log

Status: living document · Last updated 2026-11-06

Format: one ADR per decision. Status is `accepted`, `proposed`, `superseded` or
`rejected`. A decision changes only by adding a new entry that supersedes an old
one — entries are never edited away. This file is the dogfood target: Kernote's
own `decision` memory type should eventually be able to read it.

---

## ADR-0001 — Two local processes, no desktop shell for the MVP
**Status:** accepted · 2026-11-06

**Context.** The guide calls for a "desktop-quality application" on Windows and
Linux. That can mean Electron/Tauri packaging or a localhost web app.

**Decision.** Ship a Vite/React frontend plus a FastAPI backend on localhost for
the MVP. No Electron or Tauri.

**Alternatives.** *Tauri* — small binaries and a real desktop feel, but adds a
Rust toolchain and a packaging story to a 25-day budget. *Electron* — familiar
but heavy on a 16 GB machine and slow to iterate.

**Consequences.** Days saved now; packaging deferred to Day 21 as a stretch. The
frontend must avoid browser-only assumptions in its data layer so a shell can be
added later without a rewrite. "Desktop-quality" is therefore a UI-craft claim,
not a distribution claim, and the README must say so plainly.

---

## ADR-0002 — SQLite as the single source of truth, indexes disposable
**Status:** accepted · 2026-11-06

**Context.** `CLAUDE.md` requires separated raw captures, normalized chunks,
canonical memories and derived indexes, with rebuildable indexes.

**Decision.** One SQLite database per project workspace holds L1–L3. L4 (FTS5
tables and embedding vectors) is derived and droppable, with a tested `reindex`
that reproduces retrieval results exactly.

**Alternatives.** *Postgres* — overkill and hostile to local-first distribution.
*Files on disk plus an index* — loses transactional integrity across the lifecycle.

**Consequences.** Simple backup (copy one file) and simple export. Single-writer
concurrency must be respected: WAL mode, `busy_timeout`, one writer, scans
batched per file group. Reindex equivalence becomes a required test.

---

## ADR-0003 — numpy brute-force vector search for the MVP
**Status:** accepted · 2026-11-06

**Context.** The guide explicitly defers the vector-index choice until a spike
confirms Windows/Linux install reliability.

**Decision.** Store 384-d float32 L2-normalized vectors as SQLite BLOBs and do
cosine similarity with a single numpy matrix multiply. No vector extension.

**Alternatives.** *sqlite-vec* — good fit, but a native extension load is exactly
the Windows friction the guide warns about. *FAISS* — heavy, another large wheel.
*Chroma/LanceDB* — a second datastore, contradicting ADR-0002.

**Consequences.** Zero install risk and no extra dependency. At MVP scale
(≤50k chunks → ~75 MB, one 50k×384 matmul) latency stays in the tens of
milliseconds, which is well inside the p50 budget. Revisit via spike if a real
repo exceeds ~200k chunks or RAM becomes the binding constraint; that revisit
would be ADR-0003a, not an edit here.

---

## ADR-0004 — `onnxruntime` for runtime embeddings; PyTorch confined to experiments
**Status:** accepted · 2026-11-06

**Context.** The baseline embedding model is `all-MiniLM-L6-v2`. The obvious
path, `sentence-transformers`, pulls in `torch` (~2 GB CPU wheel) as a *runtime*
dependency, on a 16 GB machine with no CUDA, for a product whose core flows must
work with no paid API and a fast local install.

**Decision.** Runtime embeddings run on `onnxruntime` with the MiniLM ONNX export
plus `tokenizers` (~90 MB total), in `requirements.txt`. `torch`, `sklearn` and
`sentence-transformers` move to `requirements-ml.txt`, installed only for the
optional classifier and tiny-LM experiments.

**Alternatives.** *sentence-transformers at runtime* — simplest code, but a 2 GB
install and slower CPU inference for the core product. *No embeddings, FTS only* —
cheapest, but loses the semantic half of hybrid retrieval, which is a `Must`.

**Consequences.** Install is minutes, not tens of minutes, and CPU inference is
faster. Cost: the embedding path is slightly more code than one import, and the
ONNX artifact must be vendored or fetched once with its hash recorded. This does
not contradict `CLAUDE.md`'s "PyTorch for narrow experiments" — it enforces it.

---

## ADR-0005 — Dual fingerprints: content hash primary, Git blob hash as attribution
**Status:** accepted · 2026-11-06

**Context.** Freshness must rest on deterministic evidence. Git blob hashes are
the natural choice, but they are unavailable for untracked files and non-repo
folders, and `core.autocrlf` can make them differ across Windows and Linux for
byte-identical logical content.

**Decision.** Every source reference stores `content_hash` (SHA-256 of raw bytes,
always present, the key for content-addressed captures) and, when inside a repo,
`git_blob_hash` + `git_commit` for attribution and diff generation.

**Alternatives.** *Git blob only* — breaks outside repos and across autocrlf.
*Content hash only* — cannot produce a `git diff` as evidence.

**Consequences.** Kernote works on a plain directory, with drift detection
degrading to "this file changed" without hunk-level overlap. Minor storage cost
for the second hash. Cross-OS capture identity stays stable.

---

## ADR-0006 — Deterministic extraction first; the model adapter is strictly additive
**Status:** accepted · 2026-11-06

**Context.** Lifecycle stage 3 ("Understand") classifies memory types and extracts
facts, decisions, commands and dependencies. The MVP may not depend on a paid API
and may not depend on a local generative model. This is the single largest
unflagged risk in the kickoff guide: without a position here, Days 6–9 stall.

**Decision.** Stage 3 is implemented as a set of named deterministic rule
extractors (`rule:markdown_sections`, `rule:markdown_commands`, `rule:adr`,
`rule:manifests`, `rule:config`, `rule:code_symbols`, `rule:git_history`) plus
user-authored memories. An optional model adapter may improve titles, summaries
and rationale afterwards; its output is schema-validated and tagged
`model:<id>@<version>`. The app is fully functional with the adapter disabled,
and that configuration is the default and the one that CI tests.

**Alternatives.** *LLM-first extraction* — higher recall, but introduces a hard
dependency the product principles forbid and makes output non-reproducible.
*Manual-only memories* — safe but gives no reason to scan a repository.

**Consequences.** Lower extraction recall than an LLM pipeline, which the README
must state as a known limitation. In exchange: reproducible output, fast tests,
no API cost, and `extraction_method` lets any bad extractor's output be found and
re-reviewed in bulk later.

---

## ADR-0007 — A finding is a request for review, never a verdict
**Status:** accepted · 2026-11-06

**Context.** Stale, conflicting and duplicate signals are all probabilistic. The
guide identifies false stale alerts as a trust-destroying risk.

**Decision.** One `findings` table for every maintenance signal. A finding
carries a detector id, machine-readable evidence (hashes, diff hunks, scores), an
explanation, and a severity band. It never asserts a memory is wrong. Memory
status moves to `needs_review` only on high severity, and only a human resolution
changes canonical content. Conflicts keep both claims; merges write new revisions
and set `superseded_by` without deleting anything.

**Alternatives.** *Auto-mark stale* — cheap, and it poisons trust on the first
false positive. *Separate tables per signal* — triples the review UI for no gain.

**Consequences.** One review queue, one resolution flow, one audit trail across
Memory Intelligence Center and Change Impact. Severity thresholds need tuning
against the evaluation set, and the diff-overlap test in `maintain/drift.py`
becomes the highest-value unit test in the codebase.

---

## ADR-0008 — MCP surface is read-only
**Status:** accepted · 2026-11-06

**Context.** Agents need project context. `CLAUDE.md` forbids silent destructive
memory operations and requires approval for canonical writes.

**Decision.** The MCP server exposes exactly four read-only tools:
`search_memory`, `project_summary`, `get_decision`, `build_context`. No write
tool, in any form.

**Alternatives.** *Agent-writable memory* — attractive for capture, but an agent
writing unreviewed records is precisely the "silent" path the contract forbids.

**Consequences.** Agents consume but cannot corrupt the vault. If agent-proposed
memories are wanted later, they arrive as `findings` for human review — a new ADR,
not a loosening of this one. A small tool surface is also a testable one, which is
what makes the `Should` rating achievable in two days.

---

## ADR-0009 — Linux/WSL is the primary dev target; Windows is verified, not assumed
**Status:** proposed · 2026-11-06 · *needs your confirmation (open question Q3)*

**Context.** The guide targets Windows + Linux. Development is happening on
WSL2 on this machine. Windows dependency friction is a named risk.

**Decision (proposed).** Develop and CI on Linux/WSL. Verify native Windows at
two checkpoints — Day 18 and Day 23 — covering install, scan, retrieval and
restart. Keep the stack free of native extensions (which ADR-0003 and ADR-0004
already enforce) so that verification is cheap.

**Consequences if accepted.** Windows is a supported-but-later-verified target;
the Day 25 limitations list states exactly what was tested on which OS. If
Windows must be co-primary instead, Days 3–5 need an extra half-day for a
Windows-first environment spike.

---

## ADR-0010 — Buy-before-build: borrow proven libraries for everything outside the core
**Status:** accepted · 2026-11-06 · *supersedes nothing; constrains all later ADRs*

**Context.** Kernote is being built as a real-world product, not a research
demo. A 25-day budget cannot absorb hand-written implementations of solved
problems, and hand-rolled versions of gitignore matching, secret detection, diff
parsing and multi-language code parsing are reliably worse than the maintained
originals — not just slower to write.

**Decision.** Anything outside Kernote's differentiated core is taken from a
proven, maintained open-source project, including for small tasks. The core —
the memory lifecycle, provenance, drift evidence, review flows, grounded answer
composition, scoring with reasons, context policy — is written here. Candidate
libraries are verified against their source before adoption, never recalled from
memory. `docs/TOOLING.md` holds the mapping, and §5 of it holds the rejection
criteria (owns our core, native/GPU build on a core path, unmaintained,
one-liner, untestable offline, incompatible license).

**Alternatives.** *Minimal-dependency purism* — fewer supply-chain and audit
surfaces, but on this timeline it buys a worse product. *Framework-first* (adopt
a RAG or agent framework wholesale) — fast to a demo, but it would own the memory
model, which is the one thing that must not be outsourced.

**Consequences.** Faster, more correct non-core code, and more review attention
available for the parts that matter. Costs accepted deliberately: a larger
dependency tree, a license-compatibility obligation (MIT/Apache-2.0/BSD/ISC
only; GPL read but never vendored), and a `pip-licenses` + `detect-secrets`
check in the Day-23 release gate. Every core-path dependency must state in
`TOOLING.md` what hand-written code it replaced.

---

## ADR-0011 — `fastembed` is the embedding runtime
**Status:** accepted · 2026-11-06 · *implements ADR-0004*

**Context.** ADR-0004 chose ONNX over PyTorch for runtime embeddings but left
the implementation as hand-written `onnxruntime` + `tokenizers` glue — roughly
150 lines covering tokenization, batching, pooling, normalization and model
fetching with hash pinning.

**Decision.** Use `fastembed` (Qdrant). Verified 2026-11-06: it runs
`sentence-transformers/all-MiniLM-L6-v2` at 384 dimensions on ONNX Runtime with
**no PyTorch dependency**, manages its own execution providers, and batches.

**Alternatives.** *Hand-written ONNX glue* — one fewer dependency, 150 lines of
pooling and tokenization bugs to find ourselves. *`sentence-transformers`* —
rejected in ADR-0004 for the ~2 GB torch runtime wheel.

**Consequences.** `retrieval/embed.py` shrinks to a thin adapter, which keeps the
model swap in ADR-0014 cheap. `fastembed` ignores any `device` argument — it is
CPU/ONNX-managed — which suits the Iris Xe target where GPU acceleration was
never available anyway.

---

## ADR-0012 — tree-sitter for code symbol extraction, with per-language query files
**Status:** accepted · 2026-11-06 · *refines ADR-0006*

**Context.** ADR-0006 lists `rule:code_symbols` among the deterministic
extractors without saying how it parses code. Regex-based symbol extraction
across several languages is weeks of work and permanently approximate, and
provenance needs exact line ranges.

**Decision.** Use `tree-sitter` with `tree-sitter-language-pack` (verified
2026-11-06: one package, 300+ grammars, extracts symbols, imports and structure
with line ranges). Follow `cased/kit`'s architecture: per-language
`queries/<lang>/tags.scm` files, so adding a language is a new query file rather
than a change to core logic. Seed those queries from Aider's `aider/queries/`
(Apache-2.0, attributed).

**Alternatives.** *universal-ctags* — mature, but a system binary dependency and
coarser output. *Regex per language* — rejected above. *LLM extraction* —
forbidden as a core path by ADR-0006.

**Consequences.** Exact line ranges for `architecture` memories, and only tested
languages get a query file — which is how `CLAUDE.md`'s "do not claim support for
untested languages" becomes structurally true rather than a promise. Costs: a
native wheel (prebuilt for Windows and Linux, so acceptable under ADR-0010 §2)
and a per-language query-writing effort that is explicitly scoped and cuttable.

---

## ADR-0013 — Borrow the scanner's hard parts
**Status:** accepted · 2026-11-06 · *refines the ingest design in ARCHITECTURE.md*

**Context.** The scanner's correctness is a safety boundary: it must not ingest
secrets, must honour `.gitignore` exactly, and must produce diff hunks precise
enough that drift findings are trustworthy. My Day-1 draft hand-rolled all four
of these.

**Decision.** Replace the hand-written pieces with: `pathspec` for gitignore
semantics, `identify` for text/binary and file-type tagging, `detect-secrets`
for secret refusal, `unidiff` for diff hunk parsing. Scanner exclude defaults are
seeded from `github-linguist/linguist`'s `vendor.yml` and `documentation.yml`
rather than invented. Git is still invoked via the Git CLI with argument lists
per `CLAUDE.md`; only the parsing is borrowed.

**Alternatives.** *Hand-rolled* — my original plan. Gitignore negation and
precedence, and real-world secret formats, are both areas where a from-scratch
implementation fails quietly, and quiet failure here means leaking a credential
into the vault.

**Consequences.** The highest-risk safety path now rests on maintained, widely
audited code. `detect-secrets` also goes into `pre-commit`, so the contract's
"review the diff for secrets" step is machine-enforced. The hostile fixture
(fake `.env`, fake private key, binary, 5 MB file, CRLF file) tests our *wiring*
of these tools rather than our reimplementation of them.

---

## ADR-0014 — Spike `model2vec` static embeddings as a possible default
**Status:** proposed · 2026-11-06 · *needs a Day 14–17 measurement*

**Context.** The target machine is CPU-only with no CUDA. Embedding a medium
repository is the heaviest routine operation in the product, and ADR-0004's
MiniLM-via-ONNX baseline is the slow path in both scan and reindex.

**Decision (proposed).** During the Days 14–17 retrieval milestone, benchmark
`minishlab/potion-base-8M` against `all-MiniLM-L6-v2` on our own labelled
question set using `ranx`. Published MTEB figures (verified 2026-11-06) put
`potion-base-8M` at **91.96%** of all-MiniLM-L6-v2's average score at orders of
magnitude lower CPU cost, with `potion-base-32M` at ~92% and roughly 70× faster
on CPU. Adopt it as the default only if **our** Recall@k and nDCG stay within an
agreed margin; otherwise keep MiniLM and record the measurement.

**Alternatives.** *MiniLM only* — the known-good baseline, and the fallback if
the spike disappoints. *A larger model* — contradicts the hardware constraint.

**Consequences if accepted.** Much faster scan and reindex on the Latitude 3420,
which makes the performance budgets in `ARCHITECTURE.md` §8 comfortable instead
of tight. `embeddings.model_id` is already part of that table's primary key, so
both models can coexist and be compared without a migration. The decision must
rest on our own measured numbers, not the published benchmark — an embedding
model chosen from a leaderboard is exactly the research-demo habit this product
is avoiding.

---

## ADR-0003a — `sqlite-vec` deferral confirmed by evidence
**Status:** accepted · 2026-11-06 · *amends ADR-0003, does not supersede it*

**Context.** ADR-0003 deferred `sqlite-vec` on a *predicted* Windows install
risk. Since `sqlite-vec` ships as a plain pip wheel loaded via
`sqlite_vec.load(conn)`, that prediction deserved checking rather than assuming.

**Decision.** The deferral stands, now on evidence. Verified 2026-11-06:
`asg017/sqlite-vec` issues #13 and #45 document the precompiled extension
failing to load from Python on Windows 10/11 ("The specified module could not be
found"), including cases where `enable_load_extension()` succeeds and the
subsequent load fails — meaning the failure is not reliably detectable up front.
Some Python builds also ship with extension loading disabled entirely.

**Consequences.** numpy brute force remains the MVP path. A `sqlite-vec` spike
stays on the stretch list and must include a native-Windows load test as its
first step. Also noted for whenever it is revisited: SQLite's 1 GB blob limit
bounds any single-blob vector layout.

---

## ADR-0015 — Reposition on reviewable memory, not agent memory
**Status:** accepted · 2026-11-07 · *evidence in `docs/COMPETITIVE_LANDSCAPE.md`*

**Context.** A competitive scan on 2026-11-07 — the first one done for this
project, since the kickoff guide only screened the *name* — found the product
thesis already occupied. `projectmem` (arXiv:2606.12329, Jun 2026) is an
open-source, local-first, typed, provenance-keeping, MCP-served project memory
layer for coding agents. `Codified Context` is plain-text, no-vector-DB,
MCP-served, and ships a drift detector. Lane A (agent memory servers) also holds
agentmemory, AI-Memory, ByteRover, mem0, Zep, Letta and others, mostly free.
Meanwhile Claude Code now ships native per-project memory and a
`/doctor prompt-audit` that flags contradictory instruction files, and Cursor
removed its Memories feature in v2.1.

Separately, `MemoryAgentBench` evaluates retention, **update**, retrieval and
**conflict resolution**, and the published finding is that no current
architecture masters all four.

**Decision.**
1. Headline becomes **reviewable project memory with visible evidence and human
   approval** — an audit/review workspace. MCP becomes an output, not the pitch.
2. **F8 Knowledge Conflict Detection: `Should` → `Must`.** It is an unmastered
   capability, an afterthought for the nearest competitors, and nearly free on
   the `findings` table already designed.
3. **F3 Ask Your Project: hero → supporting**, rescoped as *cited evidence
   retrieval*, not a chat competitor. Competing on answer fluency against
   frontier-LLM products while ADR-0006 forbids an LLM in the core loop is a
   comparison we lose.
4. Drift granularity becomes the technical claim: per-source-ref content hash
   **plus diff-hunk/line-range overlap**, finer than session-start commit
   divergence.
5. Evaluation axes adopt MemoryAgentBench's four competencies.

**Alternatives.** *Proceed unchanged* — risks shipping a late, LLM-less entrant
into the most crowded lane. *Abandon* — unwarranted: the under-served capability
is real and reachable in the remaining 23 days. *Pivot to the agent-side gate*
(projectmem's "warn before repeating a failed fix") — interesting, but it is
their occupied differentiator and needs session capture we have not designed.

**Consequences.** Applied 2026-11-07 to `PRODUCT_SPEC.md` §2/§4/§5/§7/§9,
`ROADMAP.md`, `README.md` and `ARCHITECTURE.md` §9. `ROADMAP.md` Days 18–20 absorbs
conflict detection as a `Must`, which is the milestone most at risk of slipping;
F3's acceptance criterion changes from answer quality to citation correctness and
abstention rate. The name screen must be re-run against the competitor names
found (none of which is "Kernote"). `projectmem` is open source, so per ADR-0010
its event schema and MCP surface should be read before ours is finalized.

---

## ADR-0016 — The roadmap, structure and architecture are ours; prior art is reference only
**Status:** accepted · 2026-11-07 · *constrains how ADR-0010 is applied*

**Context.** ADR-0010 committed us to borrowing proven libraries for everything
outside the core, and the 2026-11-07 competitive scan surfaced close prior art
(`projectmem`, `Codified Context`) plus useful technique (`Aider`'s repomap,
`cased/kit`'s query layout). Borrowing *code* and borrowing a *plan* are
different acts, and the second one is dangerous: a competitor's roadmap encodes
a competitor's priorities, and the scan showed theirs aim at a different lane.

**Decision.** Kernote's stage plan, repository structure, schema and module
boundaries are designed here, from scratch, and recorded as our own ADRs with
alternatives considered. Prior art is read as reference — for approach,
technique and pitfalls — and every borrowing states what we took and what we
rejected. No competitor's roadmap, stage breakdown or module layout is adopted
as a template. If a plan step exists only because another project does it that
way, it gets cut.

**Alternatives.** *Clone a working design* — fastest to something runnable, but
it inherits someone else's priorities and produces a late, worse copy in a lane
we already decided not to compete in (ADR-0015). *Pure invention, no reading* —
wastes the deadline rediscovering solved problems and contradicts ADR-0010.

**Consequences.** Slower design decisions, each needing a recorded rationale,
and a standing obligation to justify structure on our own terms rather than by
precedent. In exchange the roadmap stays aimed at our wedge — knowledge update
and conflict resolution — and the ADR log stays a genuine decision record rather
than a list of imitations. ADR-0012 is the model: it seeds tree-sitter queries
from Aider's while keeping our own extraction design and attribution.

---

## ADR-0017 — `superseded_by` is the authoritative supersession edge; validity is first-class
**Status:** accepted · 2026-11-08 · *implements proposal P1/P2*

**Context.** The 0001 schema carried `valid_from`, `valid_until`,
`superseded_by` and `decision_json` on `memories`, and `memory_links` carried a
`supersedes` kind. An audit on 2026-11-07 found that **no application code read
or wrote any of them**: the columns existed, the domain model did not expose
them, and no endpoint could reach them. Temporal validity and supersession were
documented capabilities with no implementation. Worse, supersession was modelled
twice — as a column and as a link kind — with nothing stating which wins.

This matters beyond tidiness: conflict detection (F8, the product wedge under
ADR-0015) is specified as finding "decisions on the same subject with
overlapping validity windows", which is unimplementable while validity is
unreachable.

**Decision.**
1. `memories.superseded_by` is the **single authoritative** supersession edge.
2. `supersedes` is **derived** by inverse lookup and never stored on the record.
   The `memory_links` row of kind `supersedes` is written as a convenience for
   graph traversal only; it is not a second source of truth.
3. `valid_from` / `valid_until` are first-class fields on the domain model,
   meaning *when the claim was true of the project* — which is not when the row
   was written.
4. Invariants enforced in the domain layer, not merely documented: a validity
   window may not end before it starts; a record may not supersede itself; a
   record with `superseded_by` set may not remain `active`; a decision payload
   is only legal on `type='decision'`.
5. Supersession is one operation (`supersede()`), atomic, which closes the old
   record's validity window, sets its status, writes a closing revision and
   keeps every byte it had. Double supersession is refused.
6. `Memory.is_current` combines all three: active, not replaced, and inside its
   validity window.

**Alternatives.** *Keep the columns unused* — leaves a documented capability
undelivered and F8 unbuildable. *Make `memory_links` authoritative* — a graph
edge is the wrong place for a 1:1 relation and makes every "is this current?"
check a join. *Add a `supersedes` column too* — two writable representations of
one relation is precisely the drift this ADR removes.

**Consequences.** Migration 0002 adds indexes on `superseded_by` and
`(project_id, valid_until)`, since both are now queried per project. The old
record is never destroyed, so a project's decision history grows monotonically —
acceptable and intended, and the reason `superseded_by` sits outside the project
CASCADE. Thirteen tests in `tests/integration/test_write_integrity.py` cover the
invariants.

---

## ADR-0018 — Multi-statement writes are one transactional unit of work, with a single writer
**Status:** accepted · 2026-11-08

**Context.** The connection was opened with `isolation_level=None`
(autocommit) and no application code opened a transaction. `memories.create()`
issued three statements — the memory, its first revision, its source refs — each
committing independently. A reproduction on 2026-11-08 confirmed the
consequence: simulating a failure on the second statement left a **committed
memory row with no revision and no provenance**, violating MEMORY_MODEL
invariant 3 at the storage layer rather than the validation layer.

A second reproduction showed `ix_source_files_current` was a plain partial
index, so two rows for one path could both be `is_current=1`. The rule was
maintained in Python, which is not the same as the database refusing to break it.

**Decision.**
1. A `transaction()` context manager wraps every multi-statement write.
   `BEGIN IMMEDIATE` takes the write lock up front rather than upgrading a read
   lock later, which turns a lock conflict into a clean wait instead of an
   intermittent "database is locked".
2. It is **re-entrant**: a nested call joins the caller's unit of work, so a
   repository write composes inside a larger scan without either side knowing
   about the other, and rolls back with it.
3. One process-wide `threading.RLock` serialises writers. SQLite's serialized
   mode protects the C layer but cannot keep a *logical* multi-statement write
   indivisible across Python threads.
4. A scan treats **one file as one unit of work**, so a mid-scan failure cannot
   leave a capture committed without its chunks and memories — which would be
   worse than failing outright, because the next scan would see the capture as
   already known and never retry the extraction.
5. Migration 0002 makes `ix_source_files_current` UNIQUE, repairing any existing
   violation first by demoting all but the most recently seen row per path.

**Alternatives.** *Per-statement autocommit* — the status quo, which the
reproduction shows corrupts lineage. *A connection per request* — more
concurrency, but SQLite's single-writer model makes it contention, not
throughput, and it would break the one-writer assumption WAL is tuned for.
*Enforce uniqueness only in Python* — already tried; the database accepted the
violation.

**Consequences.** Writes serialise, which is correct for a local single-user
tool and bounded by the performance budgets in `ARCHITECTURE.md` §8; WAL still
lets readers run concurrently with the writer. Any future long-running write
must be chunked rather than held open, or it will block other writers for its
duration. A concurrency test with four threads × eight writes asserts every
memory ends with exactly one revision and one source ref.

---

## ADR-0019 — Drift diffs come from the stored capture, not `git diff`
**Status:** accepted · 2026-11-08 · *refines ADR-0005; implements proposal P4*

**Context.** `ARCHITECTURE.md` describes the drift pipeline as running
`git diff` between two blobs to obtain hunks. Implementing the Stage 3
feasibility spike exposed a problem with that: `git diff` can only compare
objects Git knows about, so it produces nothing for an untracked file, nothing
in a directory that is not a repository, and nothing for uncommitted working-tree
edits against a hash we pinned mid-session. Those are not edge cases — they are
the normal state of a project someone is actively working on, which is exactly
when freshness matters most.

**Decision.** Generate the unified diff with `difflib` from **the stored L1
capture** (the text we pinned, keyed by `content_hash`) against the bytes
currently on disk, then parse it with `unidiff` to obtain hunks in the new
file's line numbering. Git metadata is still recorded for attribution
(`git_blob_hash`, `git_commit`) and remains available for commit-range views in
Stage 6, but it is not on the critical path for detecting drift.

`n=0` context is used deliberately: with context lines, a hunk spans unchanged
lines either side of the edit and the overlap test reports false positives for
citations that merely sit near a change.

**Alternatives.** *`git diff` as specified* — rejected for the coverage holes
above, and it would make drift silently useless outside a repository.
*Hash comparison only* — tells you a file changed but cannot say where, so every
finding degrades to "something moved", which is risk R10 realised.
*`pygit2`* — a native dependency, which ADR-0003/0004 exist to avoid.

**Consequences.** Drift works in a plain directory with no Git at all, which a
test asserts. Storage cost: L1 capture text must be retained for any file with
live source refs — already true by design, since L1 is immutable. Deletions
need care: a pure deletion has `target_length` 0, so it is normalised to span
the line it was removed from, or a removed setup step would never raise a
finding. A test covers that specific case.

---

## ADR-0017a — Temporal values are strict ISO-8601, parsed not compared as strings
**Status:** accepted · 2026-11-08 · *amends ADR-0017, does not supersede it*

**Context.** ADR-0017 made `valid_from` / `valid_until` first-class but typed
them as plain strings, and both the ordering validator and the conflict
detector's `_windows_overlap` compared them lexicographically. Probing the
Stage 4 spike exposed the consequence: `"2026-1-1"` sorts **after**
`"2026-01-01"` because `"1" > "0"`, so an unpadded date produced the wrong
overlap verdict — silently, with no error anywhere. `"01/01/2026"` was worse:
accepted and meaningless. Nothing validated the format, so this was reachable
through the public API.

A misread date here does not crash; it emits a confident, wrong conflict
finding. That is the most damaging failure mode this product has, because the
whole pitch is that findings can be trusted.

**Decision.** Defence in depth, at three layers:
1. **Boundary.** A Pydantic field validator parses both fields with
   `datetime.fromisoformat` and rejects anything else, naming the field, showing
   a valid example and quoting what was given. Python 3.12's parser already
   rejects unpadded, non-ISO, impossible-month and impossible-day input.
2. **Normalisation.** Accepted values are stored in one canonical form, so
   `2026-03-11`, `20260311`, `2026-03-11 14:30:00` and `2026-03-11T14:30:00Z`
   cannot sit in the database as four different spellings of the same instant.
   Naive values are read as UTC.
3. **Comparison.** The ordering check and `_windows_overlap` compare real
   timezone-aware `datetime` objects. `_windows_overlap` additionally treats an
   unparseable stored bound as open-ended **and logs it**, so a value
   hand-edited into the database errs towards reporting a possible conflict
   rather than hiding one.

**Alternatives.** *A `datetime` field type on the model* — cleaner in Python,
but SQLite stores text and the API is JSON, so a string field with a validator
keeps one representation end to end instead of three. *Lenient parsing with
`dateutil`* — accepting `01/01/2026` means guessing between day-first and
month-first, which is how a silently wrong date gets in. *Leave it* — rejected:
the failure is invisible and corrupts the product's core claim.

**Consequences.** Stored temporal values change shape: `"2026-03-11"` is
persisted as `"2026-03-11T00:00:00+00:00"`. One existing round-trip test was
updated to assert the canonical form, which is the behaviour change made
deliberate. Any value written before this validator existed, or by hand, now
raises on read — acceptable because the fields were unreachable until ADR-0017
landed the day before, so no such data exists. 29 tests in
`tests/unit/test_temporal.py` cover the rejection matrix, the normalisation
table, ordering across mixed formats, overlap and currency.

---

## ADR-0019a — Drift severity has three bands; cosmetic changes are not stale
**Status:** accepted · 2026-11-08 · *amends ADR-0019, does not supersede it*

**Context.** ADR-0019's drift detector had two bands: the cited lines changed
(high) or they did not (low). Probing it during the spike review showed that
any whitespace change inside a citation produced high severity — trailing
spaces added on editor save, a paragraph rewrapped, a blank line inserted, a
block reindented. On a real repository the first run of a docs formatter would
flag every citation in every touched line as high.

That is risk R10 arriving by a second route. The overlap test was added to stop
"the file changed" becoming "everything is stale"; without a cosmetic band,
"the line changed" becomes the same thing.

**Decision.** Three bands, decided per citation:

| Band | Condition |
|---|---|
| high | A changed region overlaps the cited lines **and** its text differs once whitespace is collapsed |
| medium | A changed region overlaps the cited lines but the text is identical once whitespace is collapsed |
| low | The file changed, but not within the cited lines |

A hunk is classified by comparing its removed and added lines with all
whitespace collapsed (`" ".join(text.split())`), which also neutralises reflow:
a sentence rewrapped across two lines squashes to the same text as the
single-line version. The evidence records `cosmetic_only` and
`substantive_hunks` so a reviewer can see which judgement was made and why.

A cosmetic change still produces a finding rather than silently re-pinning the
hash, because re-pinning is a write to canonical memory and `CLAUDE.md` forbids
doing that without approval. The medium explanation says what accepting it will
do.

**Alternatives.** *Normalise whitespace before diffing* — simpler, but it hides
the change entirely, so the pinned hash stays stale forever with no record.
*Keep two bands and tune later* — the failure is immediate and total on the
first formatter run. *Ignore whitespace only outside code fences* — better in
principle, see the consequence below.

**Consequences.** On the demo repository a whole-file reformat now yields
**0 high / 7 medium** where it previously yielded 7 high, while a genuine
one-line edit is unchanged at **1 high / 6 low**, and a file containing both
yields **1 high / 1 medium / 5 low** — each citation judged on its own lines.
The previously unused `medium` severity now has a meaning.

**Known limitation, deliberately not fixed:** indentation is significant in
Python, YAML and Makefiles, so a reindent inside a fenced code block is
classified cosmetic when it may be a real change. A test asserts this current
behaviour and says in its message that it documents behaviour rather than
intent. Fixing it means parsing fence languages and knowing which are
whitespace-sensitive — Stage 6 work, and it should be measured against the P11
evaluation set rather than guessed.

---

## ADR-0020 — A file containing a credential is refused whole, and `scan_file` is the entry point
**Status:** accepted · 2026-11-08 · *implements the content half of ADR-0013*

**Context.** `walker.py` refuses `.env`, `*.pem` and `id_rsa*` by filename.
That misses the harder case: a credential pasted into a file whose name looks
innocent, which is how most accidental commits happen.

Two non-obvious findings shaped this:

1. **`detect_secrets.core.scan.scan_line` is unusable here.** It is a
   primitive that bypasses the library's filter chain, so it reports
   Base64/Hex "high entropy" hits on ordinary prose, on `pip install -r
   requirements.txt`, and on `fastapi==0.115.6`. Wiring it in would have
   refused effectively every file in every repository — a scanner that imports
   nothing. `scan_file` applies the filters: zero hits on a benign
   documentation fixture, correct detection of a GitHub token and an AWS key
   with line numbers.
2. **Redaction poisons drift.** Storing a redacted capture while hashing the
   real bytes makes the stored text differ permanently from the file, so every
   later drift diff reports phantom hunks at the redacted lines, forever.

**Decision.** Scan with `scan_file` inside one `default_settings()` context per
scan run. If a file has any hit, refuse the whole file: record
`skipped_files.reason = 'secret_suspected'`, persist no capture, no chunks and
no memories. Log the line numbers and detector names only — never the value,
because that log and the review UI would otherwise recreate the leak.

**Alternatives.** *Redact the offending lines* — rejected above. *Import the
file and flag it* — the credential would be in the database, which is the
thing being prevented. *Refuse only the offending chunk* — the line ranges of
every later chunk shift, so provenance for the rest of the file becomes
unstable.

**Consequences.** A README with one example credential loses its real content.
`# pragma: allowlist secret` is the escape hatch, and it works in code files;
in Markdown it is unreliable because detect-secrets does not treat `#` as a
comment there. A file that was clean and later gains a credential keeps its
existing memories, whose pinned hash now goes stale, so drift flags them for
review — coherent, though the UI should eventually explain that the source was
withdrawn. Tests assert at the database level that a pasted token appears in
neither `source_captures.text` nor `memories.content`.

---

## ADR-0012a — Symbol extraction scope: qualified names, no tests, four languages
**Status:** accepted · 2026-11-08 · *implements ADR-0012*

**Context.** ADR-0012 chose tree-sitter with per-language `tags.scm`. Building it
raised three scope questions that the original ADR did not answer, all surfaced
by scanning Kernote's own source.

**Decision.**
1. **One memory per top-level definition**, not one per file and not one per
   line. A per-file memory cannot be cited precisely; a per-line memory is not
   a memory.
2. **Names are qualified by their enclosing class**, and a function inside a
   class is labelled `method`. Unqualified, every `__init__` and every `render`
   in a codebase becomes a separate record titled "function `__init__`" —
   colliding on title and unreadable. `Hunk.overlaps` is a usable fact;
   `overlaps` is not.
3. **Private names are skipped** (leading underscore), except dunders, which
   are part of a class's public contract.
4. **Test files are excluded.** Dogfooding produced 19 `architecture` memories
   from a single integration test file. Tests describe behaviour, not a
   module's shape. Test *coverage* is a different question deserving a
   different memory type, later. The path matcher is anchored so "latest",
   "protest" and "contest" are not mistaken for tests.
5. **Four languages: python, typescript, tsx, javascript** — chosen because
   Kernote is written in them, so every query is exercised by dogfooding
   rather than by a synthetic fixture. A language exists only when
   `queries/<lang>/tags.scm` exists *and* has a passing test; the walker's
   source allowlist is derived from the same table. That is how `CLAUDE.md`'s
   rule against claiming untested language support becomes structural.

**Alternatives.** *One memory per file listing its symbols* — cheaper, but
drift then flags the whole module on any edit and citations lose precision.
*Include tests* — more coverage, much more noise. *Ship all 300+ grammars from
the language pack* — would claim support for languages with no query file and
no test.

**Consequences.** Source files are chunked by symbol, so each chunk carries a
real line range and a name, which is what will make it citable when retrieval
lands in Stage 5. On Kernote itself: 133 symbol memories across 91 files in
~3s. Risk R11 is contained — a missing grammar or an uncompilable query logs a
warning and degrades to "skip this language" rather than failing the scan, and
a syntax error in a source file yields no symbols rather than an exception.

---

## ADR-0020a — Secret refusal is two-tier: formats refuse, keywords warn
**Status:** accepted · 2026-11-08 · *amends ADR-0020*

**Context.** ADR-0020 refused a file on *any* detect-secrets hit. Scanning
Kernote with Kernote showed what that costs: `domain/models.py` was refused
because it contains `SECRET_SUSPECTED = "secret_suspected"`, and
`screens/Dashboard.tsx` because it contains the words "possible secret". Both
are our own domain vocabulary. The `Secret Keyword` detector fires on any
assignment whose name resembles a credential, regardless of whether the value
does.

Separately, the path deny-list pattern `secrets.*` refused
`ingest/secrets.py` — and a module named `secrets.py` is ordinary Python.

**Decision.**
1. Detectors are split by precision. **Format detectors** — GitHub Token, AWS
   Access Key, Private Key, Slack Token, JWT, Basic Auth and the rest of the
   vendor-format list — essentially do not misfire, so a hit refuses the file.
2. **Keyword and entropy detectors are guesses.** A hit from those alone
   imports the file and records a `SecretWarning` on the scan result, carrying
   the line numbers and detector names but never a value. The knowledge is
   kept and a human can glance at it.
3. The path deny-list is narrowed to **configuration** filenames
   (`secrets.json`, `credentials.yaml`, …) rather than any `secrets.*`, because
   content scanning already covers the real risk in source files.

**Alternatives.** *Refuse on everything* — the status quo, which loses files in
any security-adjacent codebase, including this one. *Warn on everything* —
would store real credentials. *Require two independent signals* — plausible,
but a lone GitHub token is a genuine leak and must still refuse.

**Consequences.** Refusals on this repository dropped from 6 files to 3, and
all 3 remaining are correct: two test fixtures containing deliberately fake
credentials and the demo `.env`. A real `password = "hunter2…"` with no
recognisable format is now imported with a warning rather than refused — the
accepted cost, and the reason the warning exists. A review-queue entry for
these warnings needs a new `findings.kind`, which needs a migration, so it is
Stage 6 work; for now the signal reaches the UI through the scan result.

---

## ADR-0020b — A keyword hit refuses the file when the *value* looks like a credential
**Status:** accepted · 2026-11-08 · *amends ADR-0020a*

**Context.** ADR-0020a split detectors by precision so that keyword and
entropy hits warn instead of refusing. Probing that policy before Stage 4
showed what it let through: `DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"` produced only a
`Secret Keyword` hit, so the file was **imported and the password stored**.
Meanwhile `SECRET_SUSPECTED = "secret_suspected"` was warned about. The policy
was discriminating on the detector, when the thing that actually distinguishes
these is the **value**.

Detector co-occurrence was tried first and is insufficient: that password
produced no entropy hit at detect-secrets' default limits.

**Decision.** A keyword or entropy hit refuses the file when
`value_looks_like_credential(line)` holds. A quoted value qualifies when it is
at least 8 characters, contains no whitespace, is not a placeholder or template
(`your-…`, `example`, `changeme`, `${…}`, `<…>`), is not an indirection
(`os.environ[…]`, `process.env`, `config.get`), does not merely restate its own
key, and has either two character classes or 20+ characters.

Two guards exist because the first implementations were wrong in both
directions:

* The key is split on `=` **or** `:`, because using `=` alone made the whole of
  `password: 'Xk92Lm04Qp77Zr'` the "key", so the value looked self-referential
  and a real secret was missed.
* A line whose text **outside** the quoted literal runs to 8 or more words is
  read as prose, not an assignment. Without that, documentation discussing
  secret handling is refused for containing an example — it cost
  `docs/DECISIONS.md` and 23 decision memories on the very next dogfood, and it
  would cost the same to any project that documents its security decisions.

**Alternatives.** *Require two detectors on one line* — misses real passwords,
as measured. *Refuse on every keyword hit* — ADR-0020a already rejected that.
*Entropy threshold alone* — `Tr0ub4dor&3xKq9vZ` is a strong password and a weak
entropy signal.

**Consequences.** On this repository, refusals are now exactly the four files
that genuinely contain credential-format literals: three test fixtures with
deliberately fake tokens and the demo `.env`. Our own source and docs that
merely *discuss* secrets are imported with a warning. The heuristic is
necessarily imperfect in both directions, so both directions are pinned by
tests: 13 asserting detection, 12 asserting non-detection.
