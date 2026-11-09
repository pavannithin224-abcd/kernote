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

---

## ADR-0021 — Duplicate candidates need a shared entity *and* body overlap; proposals never merge
**Status:** accepted · 2026-11-08

**Context.** F4 requires duplicate suggestions with a before/after preview and
approval. Comparing every pair of memories is quadratic — 285 memories on this
repository is 40k pairs — and most pairs are unrelated. Entity links
(`entities`, `memory_entities`, dormant since migration 0001) give a cheap way
to compare only plausibly related records.

Three measurements on this repository shaped the thresholds:

1. Title similarity alone produced **8 false candidates out of 8**: `function
   create` in two repository modules, `function get`, `function extract`. Same
   identifier, different function.
2. Bucketing by shared entity alone **missed the obvious duplicate**: two
   root-level files have no shared `module` entity, so an identical "Running
   the tests" section in `README.md` and `CONTRIBUTING.md` was never compared.
3. Every `## Setup` section was flagged against its own `## Setup` fenced
   block — parent and child, not two independent claims.

**Decision.**
1. Candidates are bucketed by shared entity **and** by title-token signature,
   so neither a shared file nor a matching title alone is required.
2. A candidate needs title overlap (0.6 with a strong shared entity —
   command, dependency, decision — or 0.8 when only a file or module is
   shared) **and** body overlap of at least 0.35. A matching title with
   unrelated content is not a duplicate.
3. Memories whose line ranges nest inside one another in the same file are
   never candidates.
4. `rule:code_symbols` memories are excluded: they are keyed by (file,
   qualified name), unique by construction.
5. Detection writes a `duplicate` finding and a `pending` proposal. It changes
   no memory. The merge preview keeps the higher-importance record's wording
   verbatim and appends the other's citations, so **every citation from both
   records survives** — asserted by a test — and the preview can be checked by
   eye, which is the point of an approval step.

**Alternatives.** *Compare all pairs* — quadratic and mostly noise.
*Embedding cosine now* — the third signal, but it needs Stage 5's embeddings;
the scoring structure already takes a score from any source, so adding it is a
new signal rather than a rewrite. *Auto-merge above a threshold* — forbidden by
`CLAUDE.md` and by ADR-0007.

**Consequences.** On this repository: 1851 pairs compared, **2 candidates**,
both genuine (the README setup commands and the demo repository's). On a
fixture with a planted duplicate, 1 candidate; with same-title-different-body,
0; with unrelated sections, 0. Approval is Stage 6, so a proposal currently
previews and waits.

---

## ADR-0022 — Importance fan-in counts only non-incidental sharing, from a stored base
**Status:** accepted · 2026-11-08 · *refines the scoring in MEMORY_MODEL.md*

**Context.** `MEMORY_MODEL.md` lists entity fan-in as an importance signal. The
first implementation weighted every entity kind and **adjusted 271 of 271
memories** — every memory under `docs/` shares the `docs` module, so a signal
that fires on everything ranks nothing.

A second defect appeared immediately after: the bonus was applied to the
*current* score, so a second analysis added it again and importance crept
upward on every run.

**Decision.**
1. Only `command`, `dependency`, `decision` and `component` fan-in counts.
   Files and modules are shared incidentally and are deliberately absent from
   the weight table.
2. Fan-in must reach 3 before it counts, at most the three strongest signals
   are summed, and the total bonus is capped at 0.15.
3. The bonus is applied to `importance_base`, a column added in migration 0003
   and set at creation. Recovering the base by parsing the bonus back out of
   `importance_reason` would make a numeric score depend on string formatting.
4. The adjustment is appended to `importance_reason` in words naming the
   entity and its reference count, because MEMORY_MODEL requires that a score
   can always explain itself.

**Alternatives.** *PageRank over the symbol graph* — the refinement ADR-0012a
records as later work; a reference count is explainable in one sentence, which
is the binding constraint. *Weight files and modules lower rather than zero* —
tried; with hundreds of memories in a handful of directories the effect still
swamps everything else.

**Consequences.** Refinement is idempotent, asserted by a test. On this
repository it currently adjusts **nothing**, because each command appears in
one memory — an honest result rather than a flattering one, and the signal is
exercised by a fixture with genuinely shared commands instead.

---

## ADR-0021a — Duplicate detection: bounded work, canonical comparison, one granularity
**Status:** accepted · 2026-11-08 · *amends ADR-0021*

**Context.** Probing ADR-0021 before Stage 5 found four defects, three of them
only visible at a scale this repository does not reach.

1. **A filler-only title was never compared at all.** `_tokens` strips filler
   words, and "Overview", "Commands" and "This is it" are *entirely* filler, so
   the bucket signature was empty and the pair was never bucketed. A fixture of
   120 files sharing an `## Overview` heading produced `compared=0`. Fixing the
   bucketing alone was not enough: `title_score` used the same stripped tokens,
   so Jaccard returned 0.0 and the now-correctly-bucketed pairs still scored
   zero. Bucketing and scoring must share one fallback.
2. **Unbounded pairwise work.** One bucket of 120 members is 7140 pairs, and a
   finding for each would make the review queue unusable.
3. **Cross-granularity pairs.** A `## Setup` section in one file and a
   `## Setup` fenced block in *another* share a title and an overlapping body.
   Same-file nesting was already excluded; this gave 4 candidates where 2 were
   real.
4. **Unbounded entity derivation.** A 400-dependency manifest produced 401
   entities and, at two statements each, ~800 writes for a single memory.

**Decision.**
1. `_signature` and `_title_tokens` both fall back to the raw normalised words
   when filler-stripping empties the set.
2. Buckets above 5 members use a **canonical comparison** rather than a clique:
   every member against the highest-importance one. Twenty-five identical
   sections then yield 24 actionable statements ("this duplicates the canonical
   record") instead of 300 pairs. Buckets above 25 members are truncated and
   total candidates capped at 200; both log when they bite, so truncation is
   never silent.
3. Two memories are only compared when their `extraction_method` matches.
   Different extractors produce different granularity, and a section is not a
   duplicate of the code block inside it.
4. Entity derivation is capped at 60 per memory, path entities first, since a
   400-package dependency list is noise as a fan-in signal anyway.

Also removed: `entities.fan_in()`, defined and never called — `importance.py`
carries its own query.

**Consequences.** On this repository comparisons fell from **1851 to 168** and
candidates from 2 to **1**, the remaining one genuine. All five probe cases are
now correct: 120 identical sections give 24 bounded candidates, cross-file
section/commands gives 2, a planted duplicate gives 1, same-title-different-body
gives 0, unrelated gives 0. The canonical-comparison rule means a reviewer sees
"these 24 duplicate the canonical record" rather than a combinatorial list,
which is the more useful statement as well as the cheaper one.

---

## ADR-0023 — Semantic search is opt-in; keyword-only is a supported mode
**Status:** accepted · 2026-11-09

**Context.** `CLAUDE.md` forbids outbound network calls by default, and
`fastembed` fetches ~90 MB of model weights on first use. Those two facts
collide: embeddings cannot be a silent prerequisite.

**Decision.**
1. `embed.status()` reports availability from the **filesystem only** and never
   touches the network. `ensure_model(allow_download=True)` is the single path
   that may download, and the UI states the size, the destination and that only
   weights move — nothing about the user's code leaves the machine.
2. With the model absent, retrieval is **keyword-only**, and that is a
   supported mode rather than a degraded one — FTS5-alone is also the floor
   ADR-0014 measures against. `encode()` returns `[]` instead of raising so a
   caller falls back rather than failing a request.
3. Weights live in the **user cache** (`platformdirs.user_cache_dir`), not under
   `data_dir`. They were under `data_dir` first, which meant relocating the
   database triggered another 90 MB download — found when tests pointed
   `data_dir` at a temporary directory and the model silently vanished.

**Alternatives.** *Vendor the weights in the repository* — 90 MB in git, and a
licence question. *Download on first scan* — the silent network call the
contract forbids. *Require embeddings* — would make the product unusable
offline, which is the whole premise.

**Consequences.** First index of this repository: 319 memories + 313 chunks in
~56 s, then incremental (a second build embeds nothing). Warm encode is ~3 ms
and 200 short texts take 0.21 s, so query latency is dominated by the matmul,
not the model. Keyword-only remains fully functional, and the Project
Intelligence screen says so rather than appearing broken.

---

## ADR-0024 — Hybrid retrieval fuses ranks; support is decided by term overlap
**Status:** accepted · 2026-11-09 · *implements F3 as scoped by ADR-0015*

**Context.** F3 is *cited evidence retrieval*, not chat: there is no LLM in the
core loop (ADR-0006), so the product must return evidence and say honestly when
it has none. Two sub-problems, both measured rather than guessed.

**Fusion.** bm25 is an unbounded negative and cosine is bounded [-1, 1].
Normalising them onto one scale means inventing a conversion, and the
conversion would be doing the ranking. **Reciprocal Rank Fusion** combines
*ranks*, needs no such assumption, and every result carries the signals that
produced it because `MEMORY_MODEL.md` requires score/reason metadata. Boosts
(importance, a penalty for `needs_review`, a penalty for `interpretation`) are
scaled to reorder near-ties only, never to overrule the text signals.

**Support.** Retrieval always returns *something*, so relevance has to be
decided separately from ranking. Four measurements shaped that rule:

1. **FTS5 crashes on ordinary questions.** 8 of 10 realistic inputs raised
   `OperationalError` — `"what's the setup?"`, `sqlite-vec`, `C++`, `100%`, an
   empty string, even `OR`. Every term is now re-emitted as a quoted literal,
   making operators and punctuation inert. 0 of 13 inputs crash.
2. **Stopwords manufactured support.** "what is the airspeed velocity of an
   unladen swallow" matched "an", "is", "of" and "the" in a spec document and
   was reported as `evidence_found`.
3. **Exact substring matching created false negatives.** "secrets" did not
   match ADR-0020a's "**Secret** refusal", so a well-supported question
   abstained. A crude prefix stem fixed it, checked against the item's *full*
   text rather than the 500-character excerpt shown to the reader.
4. **One coincidental word is not support.** After (2) and (3), the swallow
   question passed again because `CLAUDE.md` contains "Do not **swallow**
   errors" — one word of four. Support now needs
   `min(2, number_of_content_terms)` matches, so a one-word question still
   works while a four-word question needs two.

**Decision.** Three outcomes: `evidence_found`, `weak_evidence` (something was
retrieved but nothing mentions what was asked) and `not_found`. Each item is
labelled `evidence` (quoted from source) or `inference` (derived or
model-generated), carries a citation, and lists which terms it matched. Terms
no source mentions are reported as unknowns. Every turn is persisted to
`ask_turns` with its full retrieval trace, so a bad answer is debuggable after
the fact — and session state stays out of the vault (MEMORY_MODEL §8).

**Consequences.** 8 of 8 probe questions now classify correctly on this
repository. The honest cost is pinned by a test: *"which database did we
choose"* returns `weak_evidence`, because the ADR says "PostgreSQL" and
"persistence" and never "database" — a human would answer it, term overlap
cannot. That is the documented price of ADR-0006, and the right place to spend
an optional model adapter later.

---

## ADR-0024a — Derived vectors track their source; matching is whole-token
**Status:** accepted · 2026-11-09 · *amends ADR-0024; adds migration 0004*

**Context.** Probing Stage 5 before Stage 6 found two correctness bugs and two
precision/recall problems. Search latency was fine throughout (5 ms over 450
vectors, 7 ms for a full ask), so none of this is about speed.

1. **An edited memory kept its old vector.** `_pending` only selected rows with
   *no* vector, so after an edit semantic search went on matching text the
   project no longer contained. The derived index silently diverged from the
   source of truth, which ADR-0002 exists to prevent.
2. **Vectors outlived their targets.** `embeddings` has a polymorphic target
   (`target_kind`, `target_id`) so it cannot carry a foreign key, and deleting
   a project left its vectors behind permanently.
3. **The stemmer over-matched.** Chopping a fixed two characters turned
   "import" into "impo", a prefix of "important", so a question about imports
   was "supported" by a sentence about importance.
4. **Two-letter technical terms were unsearchable.** `len(t) > 2` excluded
   `CI`, `DB`, `UI` and `ML`, leaving "what does the CI do" with no content
   terms at all — it could only ever abstain.

**Decision.**
1. **Migration 0004** adds `embeddings.source_hash`, a SHA-256 of exactly the
   text embedded. `_pending` re-embeds when the hash differs. `updated_at` was
   the obvious alternative and is wrong: importance refinement touches
   `updated_at` without changing a word, so it would re-embed the whole project
   after every analysis.
2. Migration 0004 also adds `AFTER DELETE` triggers on `memories` and `chunks`
   that remove the corresponding vectors — the cleanup a foreign key cannot do.
3. Stemming strips **known suffixes** (`s`, `es`, `ed`, `ing`, `ies` → `y`, …)
   rather than a fixed number of characters, and comparison is against whole
   **stemmed tokens** instead of substrings. A `+e` variant reunites
   "deleted"/"delete" and "caches"/"cache" without reopening the substring hole:
   "import" becomes "importe", which still does not match "important".
4. The content-term floor drops to two characters. Stopwords already remove the
   two-letter noise words.

**Consequences.** 10 of 10 stemming cases now classify correctly, in both
directions — `import`/`important`, `manage`/`management` and `vector`/`vectorise`
are rejected while `secrets`/`secret`, `dependencies`/`dependency`,
`deleted`/`delete` and `caches`/`cached` match. Re-indexing stays idempotent:
an unchanged project embeds nothing, and a single edit re-embeds exactly one
record.

One amusing confirmation that retrieval works: after this session, asking *"what
is the airspeed velocity of an unladen swallow"* against **this** repository
returns `evidence_found`, because ADR-0024 above now contains that sentence
verbatim as its own worked example. The controlled test fixtures still assert
abstention, which is the behaviour that matters.

---

## ADR-0025 — Consolidation merges into an existing record and verifies its own promise
**Status:** accepted · 2026-11-09 · *completes F4; implements the Stage 6 review flow*

**Context.** The duplicate preview (ADR-0021) promises three things: the
absorbed record is superseded and never deleted, every citation from both
records is retained, and no wording is paraphrased. Those promises are what
make it reasonable for a human to approve a merge they have skim-read. Until
Stage 6 they were only prose.

`supersede()` already existed but creates a *new* memory as the replacement. A
consolidation keeps one of the two records, so a second primitive was needed.

**Decision.**
1. `memories.supersede_into(absorb_id, keep_id, merged_content, reason)` — one
   transaction that copies the absorbed record's source refs onto the keeper
   (skipping duplicates), writes the merged wording as a **new revision** on
   the keeper, closes the absorbed record with `superseded_by`, a closing
   revision and a `valid_until`, and records a typed `supersedes` edge.
2. **The approval verifies its own promise.** After merging, it compares the
   citations the preview advertised against the keeper's actual citations and
   **raises, rolling the transaction back, if any is missing**. Trusting the
   merge code to be correct is not the same as checking, and silently dropping
   provenance is the one failure this feature cannot have.
3. Rejection leaves both memories byte-identical — asserted by a test that
   snapshots status, content and ref count.
4. Every decision writes a `feedback` row. MEMORY_MODEL stage 9 is explicit
   feedback only: this is what a human chose, and it is what any later
   threshold tuning must rest on.
5. Resolving a finding records a verdict and never edits memory content.
   `rejected` returns a `needs_review` memory to `active` and stamps
   `last_verified_at`, so the same unchanged source does not re-raise it.

**Alternatives.** *Create a third memory and supersede both* — more uniform,
but it orphans the surviving record's identity, so every existing link and
citation would point at a superseded row. *Delete the absorbed record* —
forbidden outright. *Trust the preview without re-checking* — the cheap option,
and the one that would let a provenance bug ship silently.

**Consequences.** Live on this repository: approving a real proposal moved the
keeper from 1 citation to 2, wrote 2 revisions, left the absorbed record
fetchable with its wording intact, and a second approval returned HTTP 409
rather than merging twice. Migration 0005 was required because
`feedback.verdict` forbade `'resolved'` while `findings.status` allowed it — a
CHECK constraint disagreeing with the code, which failed on the review flow's
own happy path and was caught by a Stage 6 test.

---

## ADR-0026 — Change Impact diffs refs; "affected" still means overlapping lines
**Status:** accepted · 2026-11-09

**Context.** Drift (ADR-0019) answers "has the file on disk moved under a
pinned claim?" by diffing the stored capture against the working tree. Change
Impact answers a different question — "I am reviewing this commit range; what
knowledge does it touch?" — which needs two *refs*, not a capture.

**Decision.** `maintain/impact.py` resolves both refs, lists changed paths with
`git diff --name-only`, and for each path takes `git diff -U0` and parses hunks
with `unidiff`. `-U0` for the same reason as ADR-0019: with context lines a
hunk spans unchanged lines either side of the edit, and citations that merely
sit near a change get reported.

A memory is **`direct`** only when the changed hunks overlap its cited line
range, and **`same_file`** otherwise — shown separately and described as
"likely unaffected". An unresolvable ref, or a project root that is not a
repository, returns `resolved: false` with a readable note rather than an error.

**Alternatives.** *List every memory whose file appears in the diff* — the
obvious implementation, and measurably useless here: `HEAD~1..HEAD` touches 6
files holding **41** memories, of which **5** are directly affected. Reporting
41 is how a reviewer learns to ignore the screen. *Reuse the drift path* —
wrong input; drift compares against a stored capture, which says nothing about
what changed between two commits.

**Consequences.** The 41-versus-5 ratio is the feature. A test asserts both
halves: the edited section is flagged `direct`, and the untouched section in
the same file is flagged `same_file` — if every memory in a changed file were
reported as affected, that test fails.

---

## ADR-0025a — A proposal is void once its inputs change
**Status:** accepted · 2026-11-09 · *amends ADR-0025*

**Context.** Probing Stage 6 found the worst defect in the project so far. The
merged content in a proposal is computed when the duplicate is *detected*. If a
human then edits the keeper and approves the proposal afterwards, the stored
preview was applied — **silently overwriting their own wording with text from
before the edit**.

Everything else this product can get wrong produces a bad suggestion. This
destroyed a human's deliberate edit, under a button labelled with a guarantee
that nothing is lost.

A second, smaller defect: `supersede_into` checked whether the *absorbed*
record was already superseded but never checked the **keeper's** status, so a
merge into an archived record succeeded and deposited the merged wording
somewhere hidden from every listing.

**Decision.**
1. `merge_preview` records an `input_fingerprints` map — a SHA-256 of each
   input's wording at preview time. Approval recompares and **refuses** when
   either differs, naming the memory and telling the user to re-run analysis.
   The proposal stays `pending`, so a fresh analysis replaces it.
2. Consolidation requires two live records: approval refuses when either the
   keeper or the absorbed record is `archived` or `superseded`.
3. Proposals created before fingerprinting existed fall through the check
   rather than failing, since there is nothing to compare against.

**Alternatives.** *Recompute the merged content at approval* — avoids the data
loss, but then what is applied is not what was shown, which breaks the only
reason an approval step is meaningful. *Let the newer edit win silently* —
indistinguishable from the bug. *Lock memories while a proposal is pending* —
punishes the user for Kernote's suggestion.

**Consequences.** Re-probed: an edit before approval is now refused with the
edit intact, and merging into an archived keeper is refused. The normal path is
unaffected — an untouched proposal still merges, taking citations 1 → 2 with 2
revisions. Also pinned: SQLite's parameter limit here is 250,000, not the 999
often assumed, so Change Impact over a 1,100-file range works; that is now a
test rather than an assumption.

---

## ADR-0027 — Logs go to stderr, resolved at write time
**Status:** accepted · 2026-11-09

**Context.** The MCP server speaks JSON-RPC over stdio, so **stdout is the
transport**. `structlog` was configured with the default
`ConsoleRenderer`, which writes to stdout — so the first log line the server
emitted corrupted the protocol and the client hung with no error at all. The
MCP client sat there until it was killed.

This was invisible to unit tests. Calling the tool functions directly works
perfectly; only driving a real server over stdio shows it.

A second defect appeared in the first fix. Binding `sys.stderr` once at
configure time meant anything replacing that stream afterwards left the logger
holding a dead file: pytest's `capsys` does exactly that, and one test then
poisoned every later log call in the suite with
`ValueError: I/O operation on closed file`.

**Decision.** A shared `kernote/logging.py` used by every entry point. Logs go
to **stderr**, through a late-bound sink that resolves `sys.stderr` at write
time and swallows `ValueError` if the stream has gone — diagnostics must never
be the reason a request fails. `configure_logging()` is called before anything
that might log, which for the MCP server means before the database is opened.

**Alternatives.** *Silence logging in the MCP server* — loses the diagnostics
exactly where they are hardest to get, inside a subprocess. *A file sink* —
another path to configure, and a supervisor capturing stderr is the convention.
*Keep binding the stream* — the `capsys` failure shows why not.

**Consequences.** stderr is also right for the HTTP API, so this is a shared
default rather than an MCP workaround. Two tests pin it: one asserts a log line
reaches stderr and not stdout, and the MCP tests drive a real subprocess over
stdio, which is the only way this class of bug surfaces.

---

## ADR-0028 — The MCP surface is four tools, and the dependency pins that made it possible
**Status:** accepted · 2026-11-09 · *implements ADR-0008*

**Context.** ADR-0008 fixed the MCP surface at four read-only tools. Building it
surfaced a supply-chain problem of exactly the kind ADR-0010 risk R12 named.

Installing `mcp==1.2.0` pulled `starlette 1.10.0`. FastAPI 0.115.6 requires
`starlette<0.42`, and the mismatch **broke the entire application** —
`Router.__init__() got an unexpected keyword argument 'on_startup'`, and all 328
tests failed to even collect. One `pip install` for a `Should`-priority feature
took down a `Must`-priority one.

**Decision.**
1. Four tools, all read-only: `kernote_search_memory`,
   `kernote_project_summary`, `kernote_get_decision`,
   `kernote_build_context`. A test asserts the advertised set is exactly these
   four and that no name contains write, create, update, delete, archive,
   merge or approve.
2. The server is a second **adapter** over the same core as the HTTP API — the
   same retrieval, bundle and repository functions — so the two cannot disagree
   about what the project knows.
3. `starlette==0.41.3` and `sse-starlette==2.1.3` are pinned in
   `requirements.txt` **with the reason written next to them**, because a
   future reader will otherwise "tidy up" an apparently arbitrary pin. Only the
   stdio transport is used, so `sse-starlette` is inert; it is pinned purely so
   a clean clone resolves. `pip check` reports no broken requirements and is
   part of the Day-23 gate.
4. `KERNOTE_PROJECT` selects the project. It is optional with one project
   registered and **required with several** — silently picking one would serve
   an agent a different project's knowledge.

**Alternatives.** *A separate virtualenv for the MCP server* — real isolation,
but two environments to install and keep in step for a feature that is first on
the scope-cut list. *Upgrade FastAPI to match starlette 1.x* — a larger change
to the `Must` half of the product in service of the `Should` half.

**Consequences.** Verified against a real client over stdio: four tools
advertised, `project_summary` returning 365 memories with citations,
`get_decision("sqlite-vec")` returning ADR-0003 with its source, and
`get_decision("quantum teleportation")` returning an explicit "evidence was not
found" rather than a guess. The `memory_type` filter originally contained an
`or True` and silently did nothing — a parameter that lies is worse than no
parameter, so it now looks the type up on the memory and a test asserts it
filters.

---

## ADR-0027a — A bundle's token count is measured, not summed
**Status:** accepted · 2026-11-09 · *amends ADR-0028's bundle contract*

**Context.** The bundle's one promise is that its stated size is true. The
Stage 7 sweep measured it: a bundle asked for 200 tokens came back at **792**
and reported **187**. At 500 it reported 482 and was 1118. The sweep also found
the count of what was left out was wrong in the other direction — the note said
"113 did not fit" while **260 further memories had never been weighed against
the budget at all**, because they ranked below `max_candidates`.

Both errors came from the same habit: reporting a number derived from the parts
instead of from the thing delivered. Per-entry estimates plus a fixed 160-token
reserve for the header missed the "did not fit" list entirely — and that list
*grows as the budget shrinks*, so the tighter the budget, the bigger the lie.

**Decision.**
1. The document is rendered and **measured**; `tokens_used` is the measured
   figure. Fitting is a search over rendered sizes, not a sum.
2. The listing of what did not fit competes for the same budget, and **content
   wins**: each listing length is costed and the combination carrying the most
   memory is chosen. It never falls to zero titles, because naming nothing
   trades one dishonesty for another.
3. Memories past the candidate cut-off are counted as `not_considered` and
   reported separately from `dropped`. `excluded_total` is the number the UI
   shows, and included + excluded always equals the project's current total — a
   test asserts that identity.
4. When even the smallest honest document exceeds the budget, `over_budget` is
   set and the bundle says so. It does not shrink the number to match.
5. A body cut at the per-entry cap is marked `[…truncated]`.
6. "No memory available" is reserved for an empty vault. When records existed
   and none fitted, the bundle says the budget was too small — blaming the
   vault for a budget problem sends the reader to rescan for nothing.

**Consequences.** Stated equals measured at every budget tested (200–32000),
asserted by a parametrised test. Writing the measured figure into the document
changes the document's length, so the figure is settled to a fixed point over a
bounded number of renders. One regression surfaced during the fix and was
caught by an existing test: maximising content made a 400-token bundle list
*no* dropped titles, which is why the floor in point 2 exists.

---

## ADR-0028a — Agent-facing parameters must refuse what they cannot honour
**Status:** accepted · 2026-11-09 · *amends ADR-0028*

**Context.** Three defects in the MCP tools, all the same shape: a response
that was confidently wrong rather than unavailable.

`kernote_get_decision` matched its subject by plain substring, so `"it"`
matched "SQLite" and returned six decisions, and `"a"` returned ten. This is
precisely the `"adr"`-matches-"Quadratic" defect fixed in Stage 3 — the lesson
had not travelled to a new module. An **empty** subject fell through the filter
entirely and returned ten arbitrary decisions as though they matched.

`kernote_search_memory` accepted any string as `memory_type`. An unknown type
filtered everything out, and the tool then returned `outcome:
"evidence_found"` with the statement *"19 supporting record(s) found"* beside
an **empty** evidence list.

The Agent Integrations screen listed the four tools from a **hand-written copy**
in the API router. Rename a tool and the screen lies — two sources of truth for
one fact, in a product built to catch exactly that.

**Decision.** Whole-word subject matching with the Stage 3 `\b…s?\b` form, so
plurals still match. A subject that is empty or a single stopword is refused
with a reason: `"a"` and `"it"` are whole words in nearly every decision
document, so they match everything and mean nothing, while short subjects that
*do* carry meaning — ML, UI, DB, Go — are not stopwords, which is why length is
the wrong filter. An unknown `memory_type` returns `invalid_request` naming the
valid types. When a valid filter empties the result, the outcome becomes
`evidence_not_found` and the statement says so rather than reporting
retrieval's own count. The screen's tool list is derived from the live
`FastMCP` registry.

**Consequences.** Five regression tests, and the whole surface re-verified
against a real client over stdio. A test asserts the advertised set equals the
derived manifest, so the two can no longer drift.

---

## ADR-0029 — The labelled question set, and metrics we can defend
**Status:** accepted · 2026-11-09 · *implements proposal item P11*

**Context.** Days 23–24 require retrieval reported as **citation correctness**
and **useful-abstention rate**. Both need labels, and the existing
`samples/demo-repo` is 67 lines — on a corpus that small every metric comes out
at 1.0 and measures nothing.

**Decision.**
1. A fixture corpus, `samples/eval-repo`: 22 files of a plausible service —
   README, architecture, six ADRs, three runbooks, conventions, source, two
   manifests — plus **deliberate distractors** (a CHANGELOG that names
   PostgreSQL three times and answers nothing, a glossary, an onboarding page
   that points elsewhere) and a stale `docs/legacy-setup.md` that contradicts
   the README on port and install command. Without distractors a question set
   measures nothing but itself.
2. A question set of **31 labelled questions** at `eval/questions.json`, graded
   2 (answers it), 1 (related, does not answer) — nDCG needs the distinction,
   Recall@k counts only grade 2. Six are **unanswerable**, chosen to share
   vocabulary with the corpus: "what is the retention period for customer
   personal data" against a runbook that says snapshots are "retained for 7
   days". Five (q27–q31) are deliberate **paraphrases** that avoid the corpus's
   own words, because every other question was written while looking at the
   document that answers it — a set without them is biased towards keyword
   search and cannot fairly test embeddings.
3. The set lives **outside** the corpus. Inside it, the questions and their
   answers would be scanned into the vault being measured.
4. Labels are **validated against the corpus on load** and a set with a label
   pointing at a missing file is refused. A rotted label silently lowers every
   score, which is worse than an error.
5. Metrics are implemented in `kernote/eval/metrics.py`, and `ranx` — the tool
   ADR-0014 named — is pinned in `requirements-eval.txt` as the *authority* we
   check against, not a runtime dependency. It pulls 22 packages (numba,
   llvmlite, pandas, scipy, matplotlib, seaborn) for five formulas, which
   cannot be a prerequisite for `pytest` in a product that claims to run on a
   modest laptop. A test asserts agreement to 1e-9 and skips when ranx is
   absent.
6. **Retrieving and asserting are scored separately.** See ADR-0014a for why
   that distinction turned out to carry the whole result.

**Consequences.** The cross-check earned its place immediately: our nDCG used
the exponential `2**grade - 1` gain where `ranx` uses the linear Järvelin gain.
Our figure was 0.305 against ranx's 0.319 — a 4% error that nothing else would
have caught, and far more dangerous than a crash. The default is now the linear
form, with `exponential_gain=True` available for `trec_eval` comparisons.

Recall and MRR return `float("nan")` for a question with no answer, and the
mean ignores it. Scoring an unanswerable question 0.0 would make honest
abstention look like failed retrieval and drag every average down.

**Honest limit.** 31 questions over 51 memories, all written by the same author
as the corpus. These numbers bound a regression, not the product's quality on
real repositories.

---

## ADR-0030 — Support requires a share of the question's information
**Status:** accepted · 2026-11-09 · *amends the ADR-0006 support rule*

**Context.** The first evaluation run returned a **useful-abstention rate of
0 out of 6**. The product's central claim — that it says "evidence was not
found" when that is the truth — failed every unanswerable question in the set.

The cause was a fixed bar: an item supported the question if it mentioned any
**two** content terms. Ask "what is the contractual delivery SLA for next-day
orders" and the architecture document matches "delivery" and "orders" — two
words that appear across half the corpus — and the answer came back
`evidence_found`. "SLA" and "contractual", the entire point of the question,
appear nowhere in the corpus.

**Decision.** Support still requires two matched terms, and now also that the
matched terms carry at least **30% of the question's inverse-document-frequency
weight**, computed over the project's own records. A term absent from the corpus
carries the *most* weight, deliberately: if a question turns on a word no record
contains, that word is exactly what makes it unanswerable.

**This is a trade-off, not a separating line, and the data says so.** On the
labelled set the classes overlap — the weakest answerable question scores 0.26
and the strongest unanswerable one 0.54 — so no threshold gets both right. 0.30
buys 4 of 6 correct abstentions for 1 false abstention in 20. It is **one
parameter fitted on 31 questions with no held-out split**, so the measured
abstention gain is optimistic.

**Alternatives.** *A proportional bar (match 60% of terms)* — ignores that
terms differ in value; "orders" and "SLA" are not worth the same. *An LLM
judge* — forbidden in the core loop by ADR-0006, and unverifiable. *Leave it* —
the measurement makes that untenable.

**Consequences.** Useful abstention 0% → 66.7%, citation correctness 53.8% →
60.3% on the then-current set, with all 355 existing tests still passing. False
abstention is now the headline weakness at 20–24%. The `weak_evidence`
statement names the heaviest unmatched term, so a user is told *what* was
missing rather than just that something was.

---

## ADR-0014a — Stop benchmarking embedding models; the gate downstream discards the gain
**Status:** accepted · 2026-11-09 · *resolves ADR-0014, which stays `proposed` and unimplemented*

**Context.** ADR-0014 proposed benchmarking `potion-base-8M` against
`all-MiniLM-L6-v2` on our own labelled set with `ranx`, and adopting the faster
model if our metrics held. That set now exists, so the question was finally
measurable — and the measurement redirected it.

**The measurement** (31 questions, 51 memories, `docs/EVALUATION.md`):

| | FTS5 only | + MiniLM |
|---|---|---|
| Retrieved an answering document | 60.0% | **72.0%** |
| ...and asserted it as evidence | 48.0% | **48.0%** |
| `missed` | 10 | **7** |
| `lead_only` | 3 | **6** |
| `answered` | 12 | **12** |

Semantic retrieval finds three more correct documents and **every one of them
becomes a lead rather than an answer**. The reason is ADR-0030's support gate:
it is lexical, and a paraphrase has no lexical overlap by construction. Ask
"how does the money owed get worked out including what the taxman takes" and the
invoice module is retrieved at rank 2 — and never says "taxman", so nothing can
verify it. All five paraphrase questions fail under both configurations.

**Decision.** ADR-0014's four-way benchmark is **not worth running**, and
`model2vec` is not added. Swapping MiniLM for a faster model would optimise a
stage whose output is currently discarded downstream. The embedding comparison
is only worth doing once the support gate can use what semantic retrieval
finds.

**What this does not say.** Not that embeddings are useless: they move
retrieval success 60% → 72% and nDCG 0.592 → 0.663, which is why ADR-0023's
opt-in semantic search stays. The limit is in the composer, not the model.

**Open question (Q5, new).** Can a semantically-retrieved document with no
lexical overlap ever be *asserted* as evidence? Honestly, not deterministically
— and ADR-0006 forbids an LLM in the core loop, so there is nothing to verify
with. A high cosine similarity is a plausible third tier between "lead" and
"evidence", but it would be the first claim in Kernote not backed by something
a user can check by reading, so it needs its own ADR and is not slipped in
here. Leaving it unresolved is the conservative choice: the product currently
under-claims, which is the right direction to err.

---

## ADR-0029a — Document frequency comes from the index; a metric reports only what it measured
**Status:** accepted · 2026-11-09 · *amends ADR-0029 and ADR-0030*

**Context.** The Stage 8 sweep found that ADR-0030's support gate, which is the
right idea, had been implemented in the wrong place and at the wrong cost, and
that two of the metrics reporting on it were quietly wrong.

**1. The gate was a full table scan in the interactive path.** The first
`_document_frequency` read every memory and chunk and stemmed the text in
Python for a handful of counts. Measured on this repository — 754 rows, 200k
characters — it cost **75ms per question, 88-92% of the entire cost of
answering**, and grew linearly with the vault. Every question paid it.

**2. A term in every record carried a negative weight.** `log(N/(1+df))` is
negative once `df` reaches `N`: a ubiquitous term scored -0.019, and a
single-record corpus -0.693. A question whose terms were all ubiquitous summed
to a *negative* total weight, which flipped the sign of the information share;
matching a common term produced a share of -0.005. The gate still behaved
correctly, by luck, because a negative share is below any positive threshold.

**3. Metrics reported cut-offs they never measured.** `Recall@10` was printed
for a run that retrieved three documents — Recall@3 with a misleading label,
and a `limit=3` run printed four identical numbers under four different names.
A repeated key also scored twice, so Recall read **1.0** when one of two
answering documents had been found. And `recall_at_k` with `k <= 0` returned
`0.0`, which `mean` then averaged in as a real score.

**Decision.**
1. Document frequency is counted through the **FTS index**, one indexed query
   per term. The FTS tables are tokenised `porter unicode61`, so the counts are
   already stem-aware, and the term's own variants are OR'd in. Porter and our
   suffix stemmer still disagree at the margins, which can leave a count
   slightly *low* — making a term look rarer and the gate **stricter**, never
   looser. The error can cost an unnecessary abstention; it cannot produce
   false confidence. That asymmetry is why this trade is acceptable.
2. Term weights are clamped at zero. A term that tells us nothing is worth
   nothing, not less than nothing. When every weight is zero there is nothing
   to discriminate with and the overlap bar stands alone — now stated, rather
   than reached by dividing by a negative number.
3. Metrics collapse duplicate keys themselves rather than trusting the caller,
   and return `nan` for `k <= 0`. A report lists only the cut-offs its
   retrieval depth can support, and states that depth.

**Consequences.** `ask()` went from 83ms to 18ms and from 86ms to 30ms on the
two measured questions — **4 to 7 times faster** — and the evaluation's
verdicts are **identical**: answered 12, lead_only 3, missed 10,
correctly_declined 4, wrongly_asserted 2, abstention 66.7%. Citation
correctness moved slightly up, 41.9% to 43.4% keyword and 51.1% to 52.2%
hybrid, because the Porter counts weight a few terms differently. The ADR-0014a
conclusion is unchanged. The ranx cross-check still agrees to 1e-9 after the
distinct-key change.

---

## ADR-0029b — A question set may not aim a scan at an arbitrary directory
**Status:** accepted · 2026-11-09 · *amends ADR-0029*

**Context.** ADR-0029 made a question set self-describing: `corpus` is a path
relative to the set's own file, so a set can be dropped anywhere and still find
what it describes. The sweep tried `"corpus": "../../../../etc"`. It loaded,
resolved to `/etc`, and the harness would then have pointed a repository scan
at it. `"/etc"` worked too. `CLAUDE.md` forbids reading credentials and private
keys during scanning, and the walker's deny-list is the wrong place to rely on
for this: the path should never have been accepted.

**Decision.** A corpus must resolve inside the question set's own directory or
one level above it — which is exactly what an `eval/questions.json` pointing at
`samples/eval-repo` needs, and nothing more. Anything else is refused by name
and reason. An **empty** question set is refused as well: every metric would be
undefined and the report would still look like a measurement.

**Alternatives.** *Trust the walker* — its allowlist would skip most of `/etc`,
but "most" is not a security property, and the scan should not begin. *Require
an absolute path* — no better, and it breaks the self-describing property.
*Pin the corpus to the repository root* — would stop a user pointing a set at
their own repository, which is a use we want.

**Consequences.** Four tests, including both traversal forms and both allowed
layouts. The shipped set is unaffected.

---

## ADR-0031 — A resolved finding suppresses its own cause
**Status:** accepted · 2026-11-09 · *amends ADR-0007*

**Context.** Found by the Stage 9 demo, which is the first thing to exercise
review *and then carry on working*. The dedupe query that stops a detector
piling up findings for one cause matched only `status='open'`. So the moment a
human resolved a finding, it stopped suppressing itself, and the next `analyze`
inserted an identical new one. The review queue refilled with exactly the item
just closed, on every scan, for ever.

ADR-0007 says a finding is a request for review. A request the product reissues
the instant you answer it is not a request, and a review the product discards
is worse than no review at all.

**Decision.** A finding suppresses its cause whatever its status. The weight
moves onto the dedupe key, which must contain whatever would make the finding
legitimately *new*:

* Drift keys carry the file's current content hash
  (`stale:{ref_id}:{hash}`), so a further edit makes a new key and a new
  finding while the resolved one stays closed. Verified in both directions.
* Conflict and duplicate keys are a pair of memory ids, so adjudicating that
  pair is final until one of them is replaced. That is the honest reading of a
  human decision; if those detectors should re-raise on changed content, their
  keys need a content fingerprint rather than a looser query here.

**Consequences.** A regression test asserts both halves: a resolved drift
finding does not return after `analyze`, and a subsequent edit still raises
one. The finding a human closed staying closed is now part of what the demo
checks, because this bug was invisible to every test that resolved a finding
and then stopped.

---

## ADR-0032 — Q5 closed: assertion stays lexical; leads are ordered by meaning
**Status:** accepted · 2026-11-09 · *resolves open question Q5 from ADR-0014a*

**Context.** Q5 asked whether a semantically-retrieved document with no lexical
overlap can ever be *asserted* as evidence. It was the named cause of the
product's largest quality weakness: 20-24% false abstention, where the right
document is retrieved and not called an answer. ADR-0014a left it open rather
than guessing. This decides it on measurement.

**What the measurement showed.** Three things, none of them what the question
assumed.

1. **The plausible relaxations do not help, and together they break the
   guarantee.** Dropping corpus-absent terms from the information-share
   denominator: no change to any verdict. Adding the missing function words to
   the stopword list: no change, and citation correctness slightly down.
   **Both together: useful abstention collapses from 66.7% to 33.3% and
   wrongly-asserted answers double from 2 to 4.** The relaxation path buys
   nothing and costs the one claim the product is built on.

2. **The two worst "false abstentions" are not about semantics at all.** For
   "why was MongoDB removed from the stack", the document that answers it
   matched the question's *subject* — `mongodb` — and scored 0.283, while a
   distractor matched one incidental rare word — `stack` — and scored 0.385,
   above the bar. Inverse document frequency is standing in for centrality, and
   in a small corpus an incidental rare word outweighs the subject of the
   sentence. That is a real limitation of ADR-0030's rule, and it is a
   different problem from Q5.

3. **The lead path was ordered by exactly the wrong signal.** When nothing is
   lexically supported, what comes back is a set of leads — and they were
   ordered by the hybrid fusion, which is dominated by the keyword hits that
   have just failed. On q29 the document that answers the question is first by
   meaning, fourth by fusion and eleventh by keyword.

**Decision.**
1. **No.** Assertion continues to require lexical verification. A semantic
   match is a similarity score; it is not something a reader can check by
   reading, and `evidence_found` must keep meaning "a source says this". No
   cosine threshold, and no LLM judge — ADR-0006 forbids one in the core loop
   and it would be unverifiable anyway.
2. When nothing is supported, **leads are ordered by meaning**, not by the
   fusion. The statement says so, because an ordering the reader cannot
   account for is its own kind of dishonesty.
3. The evaluation reports **`lead_first_rate`** — of the questions that end as
   leads, how often the right document came first. A lead is only useful if the
   reader does not have to hunt for it, and a binary answered/not-answered hid
   that entirely.

**Consequences.** Measured under identical conditions with the vector index
present, the right document is first among leads for **4 of 6 questions,
against 2 of 6 before** — 33% to 67%. Abstention (66.7%), asserted answers (12)
and citation correctness (52.2%) are all unchanged, so this is a gain on the
lead path with no movement in the guarantee. It also improved the ranking
metrics, since lead ordering is part of what they measure: Recall@1 0.560 to
0.620, MRR 0.611 to 0.668, nDCG@10 0.663 to 0.700.

One case got worse: on q28 the answering document moved from rank 3 to rank 5,
because semantic similarity preferred a glossary entry about the same subject.
A 4-of-6 gain for a 1-of-6 regression is worth taking, and it is recorded here
rather than averaged away.

**What this leaves open.** False abstention is still 20-24%, and Q5 is no
longer the explanation for it. Finding 2 above is: the share rule cannot tell a
question's subject from an incidental rare word. The next attempt at this
number should weight terms by **centrality** — position in the question, or
agreement between the question's terms and the document's title — not by
rarity alone. That is a new question (Q6), and it is not a licence to weaken
assertion; it is a request for a better lexical signal.

---

## ADR-0020c — A low-precision secret hit needs the key name, not the value shape
**Status:** accepted · 2026-11-09 · *amends ADR-0020b*

**Context.** Scanning a real data-heavy repository refused **2918 of 2938
files** as suspected secrets — including three of the repository's seven
Markdown documents and two of its Python scripts. The documentation this
product exists to read was silently dropped, and the scan took 30.6s because
every one of 2909 generated JSON manifests was being scanned line by line.

One detector was responsible: `Hex High Entropy String`. It is correctly
outside `HIGH_PRECISION`, so ADR-0020b's rule 2 applied — refuse when the value
on the line also looks like a credential. And `value_looks_like_credential`
ends with `_char_classes(value) >= 2 or len(value) >= 20`, so **any quoted
token of twenty characters without a space is credential-shaped**. In a JSON
manifest that is every SHA-256 digest, every UUID, every long identifier.

The heuristic was built in Stage 3 and tuned on Kernote's own repository, which
is prose. It had never seen a corpus of data.

**Decision.** For a low-precision hit, refusing requires **both** that the
line's key names a credential *and* that the value is shaped like one. Each
detector only knows half the story: the keyword detector knows the *name* looks
secret and needs the value to confirm it, while an entropy detector knows the
*value* is random and needs the name — because a digest, a UUID, a git object
id and an API token are indistinguishable by shape. `HIGH_PRECISION` format
matches still refuse unconditionally, which is what covers the realistic
high-value leaks: AWS keys, GitHub tokens, private keys, JWTs.

**Alternatives.** *Skip entropy detectors in data files* — needs a definition
of "data file" we do not have. *Raise the length threshold* — there is no
length at which a hex secret and a hex digest differ. *Leave it* — untenable
once measured: the feature was discarding the repository.

**Consequences.** On that repository: refusals 2918 → **0**, warnings 0 → 9, a
reviewable number; files ingested 23 → 2941 and then 29 after ADR-0020c's
companion change below; scan 30.6s → 2.0s. Two tests pin both directions — a
checksum under a `sha256` key warns, and the same value under `api_key`,
`access_token`, `DB_PASSWORD` or `client_secret` still refuses.

**Companion change.** `.json` was removed from the walker's allowed *suffixes*
and its meaningful instances allowlisted by *name* instead (`package.json`,
`tsconfig.json`, and the common others). JSON is a data format; allowing the
suffix made the name list redundant and swept in 2909 generated manifests,
which is both useless knowledge and an unusable review queue. Skips are
reported with a reason, so under-reading stays visible — and a project needing
a differently named JSON file is the case for the configurable include list
`CLAUDE.md` asks for and we have not yet built.

---

## ADR-0033 — A question is unanswerable when a third of it occurs nowhere
**Status:** accepted · 2026-11-09 · *supersedes the support rule in ADR-0030, resolves proposal item Q2*

**Context.** Proposal item Q2 asked which real repositories the evaluation set
would be. It had been answered with a corpus written for the purpose, which
bounds regressions and says little about real projects. Pointing the labelled
harness at a real repository broke the product's central claim on the first
run: **useful abstention measured 0 of 4**, with all four unanswerable
questions answered confidently. The same measure was 66.7% on the fixture.

Retrieval was *better* on the real repository — Recall@3 0.889 against 0.600 —
so this was not a retrieval problem. ADR-0030's information-share threshold can
be cleared by **breadth**. Asking "what is the monetary cost in dollars of one
SPICE simulation run", `monetary` and `dollars` carry 11.3 of the question's
21.2 total weight and appear nowhere in the project, while a document matching
the five ordinary words — cost, SPICE, one, run, simulation — scores 0.467
against a 0.30 bar. The more everyday words a question contains, the easier it
becomes to answer it without addressing it.

**Decision.** Nothing is asserted when **30% or more of a question's content
terms occur nowhere in the project**. The share threshold stays as a second,
per-record test. The user is told so in those words — "41% of what you asked
about does not occur anywhere in this project" — because that is a sentence a
reader can act on.

**Alternatives, one of them measured and rejected.** A per-record rule
requiring a match on the question's heaviest term was implemented first. It
refused *correct* answers whenever the question's subject words were common
enough in the corpus to weigh zero, leaving an incidental absent word as the
peak; a positive-control test caught it. Measured against the absent-share
rule on both corpora it was strictly worse: on the real repository it reached 3
of 4 correct abstentions and cost two answers, where the absent-share rule
reaches 4 of 4 and costs none.

**Consequences.**

| | Real repo | Fixture |
|---|---|---|
| Useful abstention | 0.0% → **100.0%** | 66.7% → **83.3%** |
| Wrongly asserted | 4 → **0** | 2 → **1** |
| False abstention | 11.1% → **11.1%** | 20.0% → **28.0%** |
| Answered | 7 → **7** | 12 → **12** |

The fixture's false abstention is the real cost, and it is recorded rather than
averaged away. For this product that is the right direction to trade: a
confident wrong answer is the failure the whole design exists to prevent.

**What this changes about how we evaluate.** Two of the three defects found in
this session were invisible to 392 passing tests and to a 31-question synthetic
set, and appeared within minutes of a real repository. A synthetic corpus tests
that the code does what it did yesterday. Only a corpus nobody wrote for the
purpose tests whether the product's claims are true. Q2 is closed as: **both** —
the fixture for regression, a real repository for truth.

---

## ADR-0034 — A configurable include/exclude list, and what configuration may not do
**Status:** accepted · 2026-11-09 · *satisfies a `CLAUDE.md` requirement*

**Context.** `CLAUDE.md` has always required Kernote to "respect .gitignore and
provide a configurable include/exclude list". Only half of that existed:
`.gitignore` and an undocumented `.kernoteignore` were honoured, but there was
no way to *include* anything, and nothing was visible in the application.

Real-repo evaluation made the gap concrete rather than theoretical. ADR-0020c
removed `.json` from the allowed suffixes because allowing it swept 2909
generated manifests into the vault — which was right for that repository and
wrong for one whose schemas happen to be JSON. Under-reading with an
explanation is better than ingesting data, but only if the user can say
otherwise.

**Decision.** Three layers, merged with their provenance recorded so the result
can be explained rather than merely obeyed:

1. The built-in allowlist.
2. **`.kernote.toml`** in the repository root — `[scan] include`/`exclude`, in
   `.gitignore` pattern syntax. The project's declared intent, versioned with
   the code and reviewable in a pull request. Kernote only ever *reads* it.
3. A **per-project override** in Kernote's own database, editable from Settings
   — the equivalent of `.git/info/exclude` beside a shared `.gitignore`, so
   trying an exclusion does not require a commit.

Nothing writes to the user's repository: `CLAUDE.md` forbids rewriting their
files, and an approval flow for config writes would be a larger feature than
the one being asked for.

**The asymmetry is the design.** A configuration file inside a repository is
untrusted input, so:

* **exclude** is evaluated early and always wins over include;
* **include** widens *only* the allowlist decision. It cannot override a secret
  refusal (by filename or content), `.gitignore`, the size limit or the binary
  check.

`.gitignore` therefore has no off switch, because `CLAUDE.md` requires it be
respected and a configurable exemption would be a way around that rule rather
than an implementation of it.

**Alternatives.** *Let Kernote write `.kernote.toml` from the UI* — the natural
thing to want, and it needs the review/approval flow that canonical writes get;
deferred rather than done badly. *Database only* — loses versioning and code
review, which is most of the value for a team. *A `[tool.kernote]` table in
`pyproject.toml`* — only sensible for Python projects, and Kernote is not one
language's tool.

**Consequences.** Malformed configuration raises rather than being ignored: a
config the user believes is in force but which silently failed to parse is
worse than an error, and an unrecognised `[scan]` key is reported by name so a
typo does not look like it worked. Migration 0006 adds
`project_scan_config`. Thirteen tests, of which five assert what configuration
*cannot* do.

Verified on the real repository: `exclude = ["datasets/**", "reports/**"]` skips
68 files with reason `excluded`, and `include =
["data/manifests/**/*reference.json"]` recovers exactly the 12 reference
manifests that matter without the 2906 generated ones — the precise outcome
ADR-0020c's blanket rule could not express.

---

## ADR-0009a — Windows verified: three product bugs, two environmental limits
**Status:** accepted · 2026-11-09 · *resolves ADR-0009 and open question Q3*

**What was actually run.** Native Windows Python **3.12.10 AMD64** against a
checkout on a native NTFS path (`C:\Users\Dell\AppData\Local\Temp`), driven
through WSL interop. Full install, full test suite, and `scripts/demo.py` end
to end. Not WSL, not a container.

**The install risk was unfounded.** Risk R11 — native wheels on Windows, carried
since day one and the main reason ADR-0009 stayed `proposed` — did not
materialise at install:
`tree-sitter-language-pack` and `onnxruntime 1.31.1` both came from prebuilt
`win_amd64` wheels, nothing built from source, no MSVC toolchain needed, and
`pip check` reported no broken requirements.

**Three product bugs, all found only here, all fixed.**

1. **Text I/O relied on the locale encoding.** Python defaults `open` and
   `Path.read_text` to the locale encoding, cp1252 on this machine. Reading our
   own `docs/ARCHITECTURE.md` raised `UnicodeDecodeError: 'charmap' codec can't
   decode byte 0x90` — it contains box-drawing characters. Worse than the error
   is the near miss: a byte cp1252 *can* map decodes silently into mojibake, so
   a migration comment or an extracted memory would be quietly wrong. Every
   read and write now names `encoding="utf-8"`, and
   `tests/unit/test_text_io_is_explicit.py` fails with the offending location
   if one does not. The scan path itself was already safe — `capture.py` reads
   bytes and decodes UTF-8 explicitly — so this never corrupted a user's
   content. It broke our own files. Fixing it took the suite from 24 failures
   to 14.
2. **The MCP server wrote cp1252 to a UTF-8 transport.** JSON-RPC over stdio is
   UTF-8; `sys.stdout` is not. The first tool response containing an em-dash was
   written as cp1252 and the client died with `UnicodeDecodeError: 'utf-8'
   codec can't decode byte 0x97`. Our memory content is full of em-dashes, so
   **the agent surface was unusable on Windows for any real project.** `main()`
   now forces UTF-8 on the stdio streams before anything writes. 27 of 27 MCP
   tests pass on Windows after the fix.
3. **The release gate deadlocked.** `scripts/demo.py` launched the API with
   `stderr=subprocess.PIPE` and never read it. Windows pipe buffers are small
   enough that the server's own logs filled it mid-scan, uvicorn blocked on
   write, and the next request timed out after two minutes with the process
   still apparently alive. Server output goes to a file now, which is also
   diagnosable when it dies. The demo also printed box-drawing characters to a
   cp1252 console, which raised before the first step finished.

**Two environmental limits remain, and they are not bugs in Kernote.**

* **`tree-sitter-language-pack` grammars do not load** (10 tests). The wheel
  installs, all 155 `.pyd` files are present, `tree_sitter` core imports, and
  the MSVC runtime is on the machine — but `get_language("python")` raises
  `ImportError: DLL load failed ... The specified module could not be found`,
  so a dependent DLL is unresolved. This is the same shape as the `sqlite-vec`
  evidence in ADR-0003a: installs cleanly, fails at load, not detectable up
  front. **Kernote degrades correctly** — `code_symbols` catches it and a scan
  completes without symbol memories (40 instead of 51 on the demo corpus).
* **Git is not installed** (3 `test_impact_*` tests). It is a documented
  prerequisite, and `gitmeta._git` catches `OSError`, logs `git.failed` and
  returns `None`, so scanning, drift, conflict, retrieval and the agent surface
  all work without it. **Drift still names the overlapping hunk**, because
  ADR-0019 diffs the *stored capture* rather than calling `git diff` — a
  decision taken for untracked files that turns out to carry a whole platform.

**Decision.** Windows is a **verified target with two stated caveats**: code
symbols require a working `tree-sitter-language-pack`, and Change Impact
requires Git on `PATH`. Everything else is verified by the demo passing end to
end, including a real process restart. ADR-0009's "verify, do not assume"
stance is upheld; its two checkpoints were collapsed into one because all nine
stages finished early.

**Not verified.** The frontend build — there is no Node on this Windows
install. It is the low-risk half (pure TypeScript, no native dependencies) and
is stated as untested rather than assumed.

**Final numbers.** Linux: 411 passed, 5 skipped. Windows: **391 passed, 13
failed, 11 skipped** — 10 grammar DLL, 3 missing Git, **zero in product code**.
The demo passes on both.

---

## ADR-0009b — `tree-sitter-language-pack` bumped 0.4.0 → 1.25.0; code symbols work on Windows
**Status:** accepted · 2026-11-09 · *amends ADR-0009a and ADR-0012*

**Context.** ADR-0009a recorded that on `tree-sitter-language-pack 0.4.0` the
grammars installed on Windows but would not load: all 155 `.pyd` files present,
`tree_sitter` core importing, MSVC runtime on the machine, and
`get_language("python")` still raising `ImportError: DLL load failed`. Ten tests
failed and Windows scans produced 40 memories instead of 51. Our pin dated from
Stage 3; the published version was **1.25.0**.

**Decision.** Bump to `1.25.0`, verified on both platforms *before* changing the
pin — the Stage 7 lesson, where one install broke the whole application.

**What the measurement showed.**

| | Windows | Linux |
|---|---|---|
| Before | 13 failed, 391 passed | 411 passed |
| After | **3 failed, 402 passed** | **411 passed** |

All four of our languages load on Windows, all 23 code-symbol tests pass there,
and a Windows scan of the demo corpus now produces **51 memories — the same as
Linux** — with matching metrics (citation correctness 37.9%, useful abstention
83.3%, Recall@5 0.6). The three remaining Windows failures are Change Impact
needing Git on `PATH`, which is a documented prerequisite.

**Why this was a safe bump, checked rather than assumed.** A `--dry-run
--report` showed **one** package changing and nothing transitive. `tree-sitter`
core stays at **0.23.2**, so `Language.query()` — which newer core versions
replace with `Query(language, source)` — is untouched and no code change was
needed. `pip check` is clean on both platforms, and grammar loading is
immeasurable (0.000s per language).

**One scare worth recording.** The first post-bump Linux run reported 4 failures
and took 369s against a normal 40s. Both were transient: a re-run was clean and
timed 36.7s, and the code-symbol file passed in isolation. The suite is timed in
this ADR precisely so a future 9x reading is recognised as the environment
rather than the dependency.

**Consequences.** ADR-0012's "native wheel; risk R11" caveat is now resolved
twice over: the wheels install *and* load on Windows. ADR-0009a's first stated
caveat is withdrawn; only the Git prerequisite remains. The guard test from
ADR-0009a had to be narrowed at the same time — it globbed from the repository
root and swept in a virtualenv's site-packages as soon as one appeared under a
name its exclusion list had not predicted (`.venv-win`). It now checks named
source roots, and a planted offender confirms it still fires.

---

## ADR-0035 — Q6 closed: a title match is worth the overlap bar on its own
**Status:** accepted · 2026-11-09 · *resolves open question Q6, amends ADR-0030*

**Context.** Q6 asked whether term weighting can tell a question's *subject*
from an incidental rare word. Inverse document frequency says how **rare** a
term is, not how **central** it is, and in a small corpus the two part company:
for *"why was MongoDB removed from the stack"* the record that answers it
matched `mongodb` and scored 0.283, while a distractor matched `stack` alone and
scored 0.385, above the bar.

**Four candidate signals, measured rather than argued.** For every answerable
question on both corpora, the answering record was compared against the
best-scoring wrong one, and each signal scored on whether it favoured the right
record or the wrong one:

| Signal | Favours the answer | Favours a distractor |
|---|---|---|
| **term is in the record's title** | **5** | **0** |
| term is an extracted entity | 2 | 0 |
| term was capitalised in the question | 2 | 0 |
| *position in the question* | 1 | **2** |

Position — the signal the open question proposed first — is **actively
harmful**, and that is the most useful thing the measurement produced. Title
agreement was the clear winner and is also the most explainable: "the record's
title names the thing you asked about" is evidence a reader can check by
looking.

**The real blocker was not the share at all.** Boosting the share changed *no
verdict* at any multiplier from 1.3 to 3.0, which took a second measurement to
understand: `_MIN_OVERLAP` is 2, the MongoDB record matches **one** term, so it
was rejected for matching "only one word" and never reached the share test. The
flat two-term bar was the thing refusing it.

**Decision.** A term matched in a record's own title counts **2.0** toward both
tests a record must pass — the overlap count and the information share. The
value is structural, not fitted: `_MIN_OVERLAP` is 2, so this is exactly *"a
term in the record's own title is worth the overlap bar by itself"*. 1.6 changed
no verdict because it could not clear that bar, and 3.0 changed none either, so
the value is not balanced on a knife edge. The share stays capped at 1.0 and the
ADR-0033 absent-term veto still runs in front of both tests.

**Consequences.** On the fixture: false abstention **28.0% → 20.0%**, answered
**12 → 15**, `lead_only` 3 → 1, `missed` 10 → 9, citation correctness
**51.6% → 54.7%**, Recall@5 **0.740 → 0.780**, MRR 0.678 → 0.718. Crucially
**useful abstention (83.3%) and wrongly-asserted (1) are unchanged**, so this
bought answers without spending the guarantee. The real repository is
**completely unaffected** — abstention 100%, false abstention 11.1%, zero
wrongly asserted — which is the right outcome for a change aimed at a defect
the fixture exhibited and it did not.

`lead_first_rate` reads lower (57.1% → 40.0%) only because there are now fewer
leads to be first among; the denominator changed, not the behaviour.

**What remains.** False abstention is 20% on the fixture and 11% on the real
repository, and it is now dominated by `missed` — documents retrieval never
surfaced — rather than by records it found and would not assert. That is a
retrieval problem, not a support-rule problem, so Q6 closes here rather than
being renamed.

---

## ADR-0036 — Retrieved records are never silently discarded; and the recall metric measured the wrong thing
**Status:** accepted · 2026-11-09 · *amends ADR-0029a and the ADR-0030 composer*

**Context.** `missed` was the largest failure bucket after Q6 closed — 9 or 10
of 25 answerable questions on the fixture — so the obvious next task was
retrieval recall. The diagnosis said otherwise.

For every one of the "missed" questions, the document that answers it **was in
the fused top ten**, at ranks 2 to 5. Nothing had been missed by retrieval at
all.

**Two separate faults, one in the product and one in the measurement.**

**1. The product discarded retrieved records in silence.** When any record
passed the support gate, every other retrieved record was dropped — and the one
that actually answered the question was repeatedly among them. Asked *"which
database does this project use and why was it chosen"*, the deciding ADR came
back at **rank 2 of 10** and was withheld, while four records that do not answer
it were returned as evidence, `docs/onboarding.md` among them. The response
implied "these four are what I found" when six had been found. For a product
whose thesis is showing its evidence and being honest about the rest, quietly
binning its best candidate is close to the worst available behaviour.

`AnswerBundle` now carries `related`: retrieved, labelled, never asserted.
`evidence` still means verified. The statement says how many related records
there are and that they are not evidence; the Ask screen shows them under
"Also retrieved, not verified" with the reason; `kernote_search_memory` returns
them as `related_but_unverified`.

**2. `retrieved_answer` was computed from what the composer returned.** So a
document retrieved at rank 2 and then withheld by the support gate scored as a
**retrieval miss**. The metric measured the composer, not retrieval. It now
reads everything retrieval surfaced, and the verdicts split three ways that do
not overlap: `answered` (asserted it), `lead_only` (retrieved it, did not
assert it — whether it declined or asserted something else), `missed` (never
retrieved it).

**Consequences, and which of these is real.**

| | before | after |
|---|---|---|
| Retrieved an answering doc | 80.0% | **100.0%** |
| ...and asserted it | 60.0% | **60.0%** |
| Recall@5 | 0.780 | **0.980** |
| MRR | 0.718 | **0.777** |
| `missed` | 9 | **0** |
| Useful abstention | 83.3% | 83.3% |
| False abstention | 20.0% | 20.0% |

**The retrieval numbers moved because the metric was wrong, not because
retrieval improved.** "...and asserted it" is unchanged at 60.0%, which is the
honest summary: the product asserts exactly what it asserted before. What
changed for a user is that the other retrieved records are now visible instead
of hidden. On the real repository nothing moved at all except the one genuine
miss being correctly identified as one.

**A rejected alternative, measured.** Capping records per source file — on the
theory that several chunks of one document were consuming the ten slots, which
is true: the real repository's answer to "what error metric is used" sits at
distinct-file rank 6 while the top ten collapse into four files. It changed no
verdict on either corpus and **cost citation correctness** (54.7% → 47.7% on the
fixture, 57.9% → 51.2% on the real repository). It cannot work by construction:
it filters the ten results the composer already holds rather than fetching more.
Reverted.

**What is actually left.** One genuine miss, on the real repository, needing a
deeper candidate pool rather than better ranking — which is a precision trade
(more records shown per answer), not a free win. The remaining 40% gap between
retrieving an answering document and asserting it is the support gate doing its
job: those records do not mention what was asked, and ADR-0032 settled that
assertion stays lexical.
