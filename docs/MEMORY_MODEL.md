# Kernote — Memory Model

Status: draft for Day 1–2 approval · Last updated 2026-11-06

This is the core of the product. Memory is a **maintained data product with a
lifecycle**, not rows in a table or vectors in an index.

---

## 1. The four layers

The single most important structural rule: these layers stay conceptually and
physically separate, and each one is reconstructible from the layer above it.

```
┌──────────────────────────────────────────────────────────────┐
│ L1  RAW CAPTURES      content-addressed snapshots of source  │  immutable
│     source_files, source_captures, scan_runs, git_meta       │  never edited
├──────────────────────────────────────────────────────────────┤
│ L2  NORMALIZED        cleaned, split, line-anchored chunks   │  derived from L1
│     chunks                                                   │  rebuildable
├──────────────────────────────────────────────────────────────┤
│ L3  CANONICAL         curated typed memories + lineage       │  SOURCE OF TRUTH
│     memories, memory_revisions, memory_source_refs,          │  human-reviewable
│     memory_links, entities, findings, proposals, feedback    │  append-oriented
├──────────────────────────────────────────────────────────────┤
│ L4  DERIVED INDEXES   search structures                      │  disposable
│     memories_fts, chunks_fts, embeddings                     │  rebuild any time
└──────────────────────────────────────────────────────────────┘
```

- **L1 is immutable.** A capture is keyed by the SHA-256 of the file's raw bytes.
  Re-scanning an unchanged file finds the existing capture and writes nothing.
  This is what satisfies the "no duplicate records on repeat scan" criterion.
- **L3 is the source of truth.** SQLite holds it. Everything in L4 can be dropped
  and rebuilt from L3 and L2 without data loss, and there must be a command that
  does exactly that (`kernote reindex`) as a tested operation.
- **Facts and interpretations never mix.** A claim extracted verbatim from a file
  and a claim a model inferred live in the same table but are distinguished by
  `extraction_method` and `claim_kind`, and the UI renders them differently.

## 2. Lifecycle

| Stage | Responsibility | Non-negotiable rule |
|---|---|---|
| 1. Capture | Read files, Git metadata/diffs, user notes | Track path, content hash, blob/commit hash, timestamp, method |
| 2. Normalize | Clean, split, parse metadata, extract entities | Preserve original text and stable line references |
| 3. Understand | Classify type; extract facts, decisions, components, commands, deps | Structured output is schema-validated before it is persisted |
| 4. Curate | Deduplicate, link, rank importance, propose consolidation | Never silently discard; retain lineage and a reviewable diff |
| 5. Store | Persist canonical records, evidence, revisions, relationships | SQLite is truth; indexes are rebuildable |
| 6. Retrieve | Hybrid keyword + semantic, filters, graph expansion, rerank | Return the evidence and the score rationale |
| 7. Maintain | Detect changed sources, stale claims, conflicts, broken links | Deterministic signals trigger review; no AI-only freshness claim |
| 8. Apply | Answer, build context, suggest edits, serve MCP | Human approval for writes to canonical memory or project files |
| 9. Learn | Record accepted/rejected suggestions and retrieval usefulness | Explicit feedback only; never silently train on private repo data |

Stage 3 has no mandatory LLM. See §6.

## 3. Memory types

| Type | Captures | Typical source |
|---|---|---|
| `project_fact` | Purpose, stack, runtime, layout, core constraints | README, manifests, config |
| `architecture` | Components, modules, boundaries, flows, dependencies | Docs, imports, directory shape |
| `decision` | Chosen option, alternatives, rationale, date, status | ADRs, PR/commit messages, user notes |
| `procedure` | Setup, build, test, deploy, troubleshooting steps | README code fences, scripts, CI config |
| `convention` | Coding patterns, naming, testing, review expectations | Lint/format config, CONTRIBUTING, observed patterns |
| `gotcha` | Known bugs, edge cases, workarounds, lessons | Comments, issue text, user notes |
| `current_state` | Active work, open questions, recent changes, next steps | Handoff docs, recent commits, user notes |

`current_state` is the one type expected to churn. It is also the one most likely
to go stale, so it defaults to a shorter `valid_until` horizon.

## 4. Canonical record

```
MemoryRecord
  id                   UUID
  project_id           UUID
  type                 enum (§3)
  title                string
  content              text
  summary              text?
  status               active | needs_review | superseded | archived
  claim_kind           source_fact | interpretation       # never blended
  importance           numeric + importance_reason        # reason is required
  confidence           numeric + confidence_reason        # reason is required
  source_refs          [{path, line_start, line_end, content_hash,
                         git_blob_hash?, git_commit?, url?, user_note?}]
  entity_refs          [{kind: file|module|component|dependency|decision, ref}]
  created_at / updated_at / last_verified_at
  valid_from / valid_until?
  supersedes / superseded_by?
  revision_id / parent_revision_id
  extraction_method    manual | rule:<name> | model:<id>@<version>
```

Rules that the schema enforces rather than hopes for:

- `importance` and `confidence` are **meaningless without their reason strings**;
  both are `NOT NULL`. A score the UI cannot explain is a bug.
- `extraction_method` is mandatory. It is how a bad extractor is later found and
  its output re-reviewed in bulk.
- A memory with zero `source_refs` is only legal when `extraction_method = manual`
  (a user assertion is its own provenance).
- `superseded_by` never deletes. The old record stays queryable forever.

## 5. Provenance and the two hashes

Every source reference stores **two** fingerprints where available:

- `content_hash` — SHA-256 of the file's raw bytes as Kernote read them. Always
  present. Works in a plain directory with no Git.
- `git_blob_hash` + `git_commit` — present only inside a Git repo. Gives
  commit-level attribution and lets drift evidence be a real `git diff`.

Why both: Git-only provenance breaks for untracked files and non-repo folders,
and `content_hash` alone cannot produce a diff. Also note Git's autocrlf can make
blob hashes differ across Windows and Linux for identical logical content, so
`content_hash` over raw bytes is the stable primary key for captures and the
blob hash is attribution metadata.

## 6. Understanding without a mandatory LLM

The MVP must be usable with no paid API and no local generative model, so stage 3
is **deterministic first**:

| Extractor | Input → output |
|---|---|
| `rule:markdown_sections` | Heading tree → `project_fact` / `architecture` candidates with exact line ranges |
| `rule:markdown_commands` | Fenced shell blocks under setup/install/build/test headings → `procedure` |
| `rule:adr` | `docs/adr/*`, `decisions/*`, ADR front-matter → `decision` with alternatives and status |
| `rule:manifests` | `package.json`, `pyproject.toml`, `requirements*.txt`, lockfiles → stack and dependency facts |
| `rule:config` | CI workflows, Dockerfile, lint/format config → `procedure` and `convention` |
| `rule:code_symbols` | Module/class/function headers and docstrings → `architecture` candidates. Parsed with tree-sitter via per-language `tags.scm` queries, giving exact line ranges (ADR-0012) |
| `rule:git_history` | Commit and merge messages matching decision language → `decision` candidates |
| `manual` | User-authored memory in the UI → any type |

An **optional model adapter** (user-supplied provider, or a local model if a later
spike justifies it) can propose better titles, summaries and decision rationale.
It is strictly additive: it runs after the rules, its output is schema-validated,
it is tagged `model:<id>@<version>`, and the app is fully functional with the
adapter disabled. Every custom classifier is compared against a rules or logistic
-regression baseline before it is allowed to replace one.

## 7. Intelligence behaviours

### Importance
Scored from durable signals — type, source authority (a README outranks an inline
comment), entity fan-in, Git recency, user pins — and the contributing signals are
stored so the UI can show *why* a record ranks where it does. Conversational
noise ranks below durable project knowledge.

For `architecture` memories, "entity fan-in" is not a raw reference count:
follow Aider's `repomap.py` approach (Apache-2.0, see `docs/TOOLING.md` §4) and
run personalized PageRank over the tree-sitter symbol graph, so a module that
important modules depend on outranks one merely referenced often. The same
token-budget fitting technique applies to the F7 context bundle.

### Consolidation
Duplicate candidates come from three cheap signals combined: FTS overlap,
embedding cosine above a tuned threshold, and shared `entity_refs`. A proposal
shows both source records, a before/after preview and the resulting lineage,
then waits for approval. Merging writes a new revision and sets `superseded_by`
on the inputs. **Nothing is deleted.**

### Freshness
```
memory.source_refs → referenced file + line range + content_hash
                     ↓ on rescan
          hash changed?  ──no──► nothing
                     ↓ yes
          git diff hunks overlap the referenced line range?
                     ↓ yes                        ↓ no
          finding: stale_risk (high)      finding: stale_risk (low)
          with the triggering hunks       file moved around it
```
The overlap test is what keeps the false-positive rate survivable. A finding is a
**request for review**, never an assertion that the memory is wrong.

### Conflicts
Both claims are stored, with their sources and dates, and the pair is held in
`needs_review` until a human resolves it. Kernote never picks a winner silently.
Detection signals: contradictory values for the same entity attribute,
mutually exclusive procedure steps for the same task, and decisions on the same
subject with overlapping validity windows.

### Retrieval
Keyword (FTS5) and vector results are fused with Reciprocal Rank Fusion, then
boosted by recency, importance, source authority and status (`active` over
`needs_review`; `superseded` and `archived` excluded unless explicitly asked).
The exact evidence passed to the answer composer is recorded with the answer, so
a bad answer is debuggable after the fact.

### Feedback
Accepted / rejected / edited on every proposal, and thumbs on retrieval
usefulness, written to `feedback`. Used to tune thresholds and to build the
labelled set for classifier experiments. Never used for implicit training.

## 8. Session state vs durable memory

Chat turns, draft answers and retrieval traces are **session state**: separate
tables, separately purgeable, never promoted into canonical memory without an
explicit user action. This keeps the vault from filling with transcript noise.

## 9. Invariants worth a test each

1. Re-scanning an unchanged repository creates zero new `source_captures`.
2. Dropping all of L4 and reindexing yields identical retrieval results.
3. No canonical memory lacks provenance unless `extraction_method = manual`.
4. A consolidation approval never reduces the total count of retrievable revisions.
5. A `superseded` record remains fetchable by id forever.
6. A stale finding always carries at least one concrete hash or diff artifact.
7. Scanning a directory containing a `.env` and a private key imports neither.
8. Every persisted model output passed schema validation first.
