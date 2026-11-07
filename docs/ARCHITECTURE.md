# Kernote — Architecture

Status: draft for Day 1–2 approval · Last updated 2026-11-06

---

## 1. Shape

Two processes on localhost, one SQLite file per project workspace.

```
┌───────────────────────────┐        ┌──────────────────────────────────────┐
│  Frontend (Vite dev /     │        │  Backend (FastAPI, uvicorn)          │
│  static build)            │        │                                      │
│  React + TS + Tailwind    │ HTTP   │  api/      typed routers, no logic    │
│  + shadcn/ui              │ :8787  │  domain/   pure models + rules        │
│                           │───────►│  ingest/   scan → normalize → extract │
│  7 screens, typed client, │        │  retrieval/ fts + embed + hybrid      │
│  no business logic        │        │  maintain/ drift, conflicts, dupes    │
└───────────────────────────┘        │  apply/    context bundles           │
                                     │  db/       schema, repositories       │
┌───────────────────────────┐ stdio  │                                      │
│  Coding agent             │───────►│  mcp/      read-only tool surface    │
│  (Claude Code / Codex)    │        └──────────────────────────────────────┘
└───────────────────────────┘                    │
                                        ┌────────▼─────────┐  ┌──────────────┐
                                        │ SQLite + FTS5    │  │ Git CLI      │
                                        │ kernote.db       │  │ (read-only)  │
                                        │ embeddings.bin   │  └──────────────┘
                                        └──────────────────┘
```

**Why two processes and not Electron/Tauri for the MVP.** Packaging a desktop
shell is a Day-21 concern that would cost days now and buys nothing the browser
does not already give us. The frontend is built so that wrapping it later is a
packaging change, not a rewrite: no browser-only assumptions in the data layer.

### Boundaries that must hold

- `api/` does validation and serialization only. No business rule lives in a router.
- `domain/` is pure: dataclasses/Pydantic models plus deterministic rules, no I/O,
  no SQL, no network. This is what unit tests hit hardest.
- `db/repositories/` is the only place that writes SQL. One module per aggregate.
- `ingest/`, `retrieval/`, `maintain/`, `apply/` depend on `domain` and
  `db.repositories`, never on `api` and never on each other's internals.
- `mcp/` calls the same service functions as `api/`. It is a second adapter over
  one core, never a parallel implementation.

## 2. Repository structure

```
kernote/
├── CLAUDE.md                      project contract
├── README.md
├── docs/
│   ├── PRODUCT_SPEC.md  ARCHITECTURE.md  ROADMAP.md
│   ├── MEMORY_MODEL.md  DECISIONS.md     DEV_HANDOFF.md
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt            runtime: fastapi, uvicorn, pydantic,
│   │                               fastembed, tree-sitter(+language-pack),
│   │                               markdown-it-py, pathspec, identify,
│   │                               detect-secrets, unidiff, platformdirs,
│   │                               structlog, typer, numpy, mcp
│   ├── requirements-ml.txt         OPTIONAL experiments only: torch, sklearn,
│   │                               sentence-transformers, datasets, model2vec
│   ├── requirements-dev.txt        pytest, syrupy, hypothesis, ranx, ruff,
│   │                               mypy, pre-commit, httpx
│   ├── kernote/
│   │   ├── main.py                 app factory, lifespan, CORS for :5173 only
│   │   ├── config.py               settings, paths, include/exclude defaults
│   │   ├── domain/
│   │   │   ├── models.py           MemoryRecord, SourceRef, Finding, …
│   │   │   ├── memory_types.py     the 7 types + per-type field rules
│   │   │   ├── scoring.py          importance/confidence with reasons
│   │   │   └── errors.py           typed domain errors → HTTP mapping
│   │   ├── db/
│   │   │   ├── schema.sql          §4
│   │   │   ├── migrations/         0001_init.sql, …  forward-only
│   │   │   ├── connection.py       WAL, foreign_keys=ON, busy_timeout
│   │   │   └── repositories/       projects, sources, memories, findings,
│   │   │                           proposals, feedback, sessions
│   │   ├── ingest/
│   │   │   ├── walker.py           pathspec (.gitignore) + identify (type),
│   │   │   │                       linguist-seeded exclude defaults
│   │   │   ├── secrets.py          detect-secrets adapter (ADR-0013)
│   │   │   ├── gitmeta.py          Git CLI (arg list only) + unidiff hunks
│   │   │   ├── capture.py          content-addressed L1 writes
│   │   │   ├── normalize.py        chunking with stable line anchors
│   │   │   ├── extract/            markdown (markdown-it-py token.map),
│   │   │   │                       manifests, adr, config, git_history,
│   │   │   │                       code_symbols/ + queries/<lang>/tags.scm
│   │   │   │                       (tree-sitter, ADR-0012)
│   │   │   └── pipeline.py         scan_run orchestration + progress events
│   │   ├── retrieval/
│   │   │   ├── fts.py              FTS5 queries, bm25 ordering
│   │   │   ├── embed.py            fastembed adapter (ADR-0011); model
│   │   │   │                       swappable per ADR-0014
│   │   │   ├── vector.py           numpy brute-force cosine (ADR-0003/0003a)
│   │   │   ├── hybrid.py           RRF fusion + boosts + filters
│   │   │   └── answer.py           grounded composer: evidence/inference/unknown
│   │   ├── maintain/
│   │   │   ├── drift.py            hash change + hunk/line-range overlap
│   │   │   ├── duplicates.py       FTS + cosine + shared entities
│   │   │   ├── conflicts.py        contradiction candidates
│   │   │   └── findings.py         unified review queue lifecycle
│   │   ├── apply/
│   │   │   └── context_bundle.py   budgeted Markdown export with citations
│   │   ├── api/
│   │   │   ├── routers/            §3
│   │   │   └── schemas.py          request/response DTOs
│   │   └── mcp/server.py           4 read-only tools (§6), official mcp SDK
│   ├── eval/                       question sets, harness, reports
│   └── tests/
│       ├── unit/  integration/  fixtures/
├── frontend/
│   ├── package.json                react, react-router, @tanstack/react-query,
│   │                               @tanstack/react-table, tailwind, shadcn/ui,
│   │                               react-diff-viewer-continued, @xyflow/react,
│   │                               openapi-fetch, cmdk, sonner, biome, vitest
│   └── src/
│       ├── app/                    router, layout, providers, theme
│       ├── screens/                dashboard, explorer, intelligence,
│       │                           maintenance, impact, agents, settings
│       ├── components/             evidence panel, citation chip, diff view,
│       │                           review actions, memory card
│       ├── lib/api/                client generated by openapi-typescript
│       └── lib/                    formatting, hooks
├── samples/demo-repo/              small reproducible demo project
├── justfile                        task runner (dev, test, lint, reindex)
├── Procfile                        honcho: api + web in one command
└── scripts/                        reindex, seed, fetch-model
```

Every module above exists because a `Must` feature needs it. If a directory has
no feature pointing at it by Day 10, it gets deleted.

**Dependencies and prior art:** see `docs/TOOLING.md` for what each third-party
package replaces, which repos to study, and the criteria for rejecting a
dependency (ADR-0010).

## 3. API surface

Versioned under `/api/v1`. All mutations are explicit; nothing mutates on a GET.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/projects` | List / register a local project workspace |
| GET | `/projects/{id}` | Project detail, health, counts |
| POST | `/projects/{id}/scan` | Start a read-only scan → `scan_run_id` |
| GET | `/scans/{run_id}` | Progress, counts, skipped files and reasons |
| GET/POST | `/projects/{id}/memories` | List with filters / create |
| GET/PATCH | `/memories/{id}` | Detail with evidence / edit → new revision |
| POST | `/memories/{id}/archive` | Archive (never delete) |
| GET | `/memories/{id}/revisions` | Lineage |
| GET | `/memories/{id}/related` | Graph neighbours |
| POST | `/projects/{id}/ask` | Grounded answer + citations + retrieval trace |
| GET | `/projects/{id}/findings` | Review queue: stale, conflict, duplicate |
| POST | `/findings/{id}/resolve` | Accept / reject / edit, with actor + note |
| GET | `/proposals/{id}` | Consolidation before/after preview |
| POST | `/proposals/{id}/approve` | Apply merge, write revisions and lineage |
| GET | `/projects/{id}/impact` | Change-impact view for a commit range |
| POST | `/projects/{id}/context` | Build a context bundle for a task |
| GET/PATCH | `/projects/{id}/settings` | Include/exclude, privacy, model adapter |
| POST | `/projects/{id}/reindex` | Rebuild L4 from L3/L2 |
| GET | `/health` | Liveness + schema version |

Scans and reindex are long-running: they return immediately with a run id and
report progress by polling. No WebSocket in the MVP.

## 4. SQLite schema (initial)

Forward-only migrations. `PRAGMA journal_mode=WAL`, `foreign_keys=ON`,
`busy_timeout=5000`.

```sql
-- ─── L1 RAW ────────────────────────────────────────────────────────────────
CREATE TABLE projects (
  id            TEXT PRIMARY KEY,          -- uuid4
  name          TEXT NOT NULL,
  root_path     TEXT NOT NULL UNIQUE,
  is_git_repo   INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  settings_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE scan_runs (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  status        TEXT NOT NULL CHECK (status IN
                  ('running','completed','failed','cancelled')),
  git_commit    TEXT,                      -- HEAD at scan time, if any
  files_seen    INTEGER NOT NULL DEFAULT 0,
  files_new     INTEGER NOT NULL DEFAULT 0,
  files_skipped INTEGER NOT NULL DEFAULT 0,
  error         TEXT
);

-- Content-addressed. The same bytes are stored once per project, forever.
CREATE TABLE source_captures (
  content_hash  TEXT NOT NULL,             -- sha256 of raw bytes
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  text          TEXT,                      -- NULL for non-decodable
  byte_size     INTEGER NOT NULL,
  encoding      TEXT,
  captured_at   TEXT NOT NULL,
  PRIMARY KEY (project_id, content_hash)
);

-- Path ↔ capture over time. A path seen again unchanged updates last_seen only.
CREATE TABLE source_files (
  id             TEXT PRIMARY KEY,
  project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  rel_path       TEXT NOT NULL,
  content_hash   TEXT NOT NULL,
  git_blob_hash  TEXT,
  git_commit     TEXT,
  language       TEXT,
  first_seen_run TEXT NOT NULL REFERENCES scan_runs(id),
  last_seen_run  TEXT NOT NULL REFERENCES scan_runs(id),
  is_current     INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY (project_id, content_hash)
    REFERENCES source_captures(project_id, content_hash)
);
CREATE UNIQUE INDEX ix_source_files_path_hash
  ON source_files(project_id, rel_path, content_hash);
CREATE INDEX ix_source_files_current
  ON source_files(project_id, rel_path) WHERE is_current = 1;

CREATE TABLE skipped_files (          -- transparency: why nothing was imported
  id          TEXT PRIMARY KEY,
  scan_run_id TEXT NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
  rel_path    TEXT NOT NULL,
  reason      TEXT NOT NULL CHECK (reason IN
                ('gitignored','excluded','binary','too_large',
                 'secret_suspected','unreadable','not_allowlisted'))
);

-- ─── L2 NORMALIZED ─────────────────────────────────────────────────────────
CREATE TABLE chunks (
  id             TEXT PRIMARY KEY,
  project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
  ordinal        INTEGER NOT NULL,
  line_start     INTEGER NOT NULL,
  line_end       INTEGER NOT NULL,
  heading_path   TEXT,                     -- "Setup > Local development"
  text           TEXT NOT NULL,
  token_estimate INTEGER NOT NULL
);
CREATE INDEX ix_chunks_file ON chunks(source_file_id, ordinal);

-- ─── L3 CANONICAL (source of truth) ────────────────────────────────────────
CREATE TABLE memories (
  id                 TEXT PRIMARY KEY,
  project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type               TEXT NOT NULL CHECK (type IN
                       ('project_fact','architecture','decision','procedure',
                        'convention','gotcha','current_state')),
  title              TEXT NOT NULL,
  content            TEXT NOT NULL,
  summary            TEXT,
  status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                       ('active','needs_review','superseded','archived')),
  claim_kind         TEXT NOT NULL CHECK (claim_kind IN
                       ('source_fact','interpretation')),
  importance         REAL NOT NULL,
  importance_reason  TEXT NOT NULL,        -- a score with no reason is a bug
  confidence         REAL NOT NULL,
  confidence_reason  TEXT NOT NULL,
  extraction_method  TEXT NOT NULL,        -- manual | rule:<n> | model:<id>@<v>
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  last_verified_at   TEXT,
  valid_from         TEXT,
  valid_until        TEXT,
  superseded_by      TEXT REFERENCES memories(id),
  current_revision   TEXT NOT NULL,
  decision_json      TEXT                  -- alternatives/status for `decision`
);
CREATE INDEX ix_memories_project_status ON memories(project_id, status, type);
CREATE INDEX ix_memories_importance ON memories(project_id, importance DESC);

CREATE TABLE memory_revisions (
  id            TEXT PRIMARY KEY,
  memory_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  parent_id     TEXT REFERENCES memory_revisions(id),
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  summary       TEXT,
  snapshot_json TEXT NOT NULL,             -- full record at this revision
  change_reason TEXT NOT NULL,
  actor         TEXT NOT NULL CHECK (actor IN ('user','rule','model')),
  created_at    TEXT NOT NULL
);
CREATE INDEX ix_revisions_memory ON memory_revisions(memory_id, created_at);

CREATE TABLE memory_source_refs (
  id             TEXT PRIMARY KEY,
  memory_id      TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  source_file_id TEXT REFERENCES source_files(id),
  rel_path       TEXT,
  line_start     INTEGER,
  line_end       INTEGER,
  content_hash   TEXT,                     -- pinned fingerprint for drift
  git_blob_hash  TEXT,
  git_commit     TEXT,
  url            TEXT,
  user_note      TEXT
);
CREATE INDEX ix_refs_memory ON memory_source_refs(memory_id);
CREATE INDEX ix_refs_hash ON memory_source_refs(content_hash);

CREATE TABLE entities (
  id         TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN
               ('file','module','component','dependency','command','decision')),
  name       TEXT NOT NULL,
  UNIQUE (project_id, kind, name)
);

CREATE TABLE memory_entities (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  role      TEXT,
  PRIMARY KEY (memory_id, entity_id)
);

CREATE TABLE memory_links (
  src_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  dst_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN
               ('relates_to','duplicate_of','contradicts','refines',
                'supersedes','depends_on')),
  reason     TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (src_id, dst_id, kind)
);

-- One review queue for every kind of maintenance signal.
CREATE TABLE findings (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL CHECK (kind IN
                 ('stale_risk','conflict','duplicate','broken_link',
                  'missing_doc')),
  severity     TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN
                 ('open','accepted','rejected','resolved')),
  memory_id    TEXT REFERENCES memories(id) ON DELETE CASCADE,
  other_id     TEXT REFERENCES memories(id) ON DELETE CASCADE,
  detector     TEXT NOT NULL,              -- rule:<n> | model:<id>@<v>
  evidence_json TEXT NOT NULL,             -- hashes, diff hunks, scores
  explanation  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  resolved_at  TEXT,
  resolution_note TEXT
);
CREATE INDEX ix_findings_queue
  ON findings(project_id, status, severity, created_at);

CREATE TABLE consolidation_proposals (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  finding_id    TEXT REFERENCES findings(id) ON DELETE SET NULL,
  input_ids_json TEXT NOT NULL,            -- memories being merged
  preview_json  TEXT NOT NULL,             -- before/after for the UI
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
                  ('pending','approved','rejected','superseded')),
  created_at    TEXT NOT NULL,
  decided_at    TEXT,
  result_memory_id TEXT REFERENCES memories(id)
);

CREATE TABLE feedback (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  target_kind TEXT NOT NULL CHECK (target_kind IN
                ('memory','finding','proposal','answer','retrieval')),
  target_id   TEXT NOT NULL,
  verdict     TEXT NOT NULL CHECK (verdict IN
                ('useful','not_useful','accepted','rejected','edited')),
  note        TEXT,
  created_at  TEXT NOT NULL
);

-- Session state: purgeable, never promoted without an explicit user action.
CREATE TABLE ask_sessions (
  id         TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);
CREATE TABLE ask_turns (
  id             TEXT PRIMARY KEY,
  session_id     TEXT NOT NULL REFERENCES ask_sessions(id) ON DELETE CASCADE,
  question       TEXT NOT NULL,
  answer         TEXT NOT NULL,
  citations_json TEXT NOT NULL,
  trace_json     TEXT NOT NULL,            -- exact evidence + scores shown
  created_at     TEXT NOT NULL
);

-- ─── L4 DERIVED (disposable, rebuildable) ──────────────────────────────────
CREATE VIRTUAL TABLE memories_fts USING fts5(
  title, content, summary,
  content='memories', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  text, heading_path,
  content='chunks', content_rowid='rowid', tokenize='porter unicode61'
);

CREATE TABLE embeddings (
  target_kind TEXT NOT NULL CHECK (target_kind IN ('memory','chunk')),
  target_id   TEXT NOT NULL,
  model_id    TEXT NOT NULL,
  dim         INTEGER NOT NULL,
  vector      BLOB NOT NULL,               -- float32, L2-normalized
  built_at    TEXT NOT NULL,
  PRIMARY KEY (target_kind, target_id, model_id)
);

CREATE TABLE schema_meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
```

Deliberate choices: UUID text keys for portability over integer rowids; JSON
columns only for genuinely variable-shape payloads (previews, traces, evidence)
and never for anything that needs querying; `ON DELETE CASCADE` scoped to project
teardown, with `superseded_by` and revisions outside it so lineage survives.

## 5. Pipelines

**Scan.** `walker` → per file: gitignore → allowlist → size cap → binary sniff →
secret check → hash → `source_captures` upsert (no-op when known) →
`source_files` row → `normalize` → chunks → extractors → candidate memories →
schema validation → dedupe against existing → persist → enqueue drift check →
L4 index update. Every refusal writes a `skipped_files` row, so the UI can always
answer "why was this file not imported."

**Ask.** question → FTS5 over memories+chunks (bm25) ‖ encode + cosine top-k →
RRF fuse → filter by status/type → boost (importance, recency, source authority)
→ take evidence set → compose answer labelling evidence / inference / unknown →
persist turn with full trace. With no model adapter configured, the composer is
extractive: it returns the ranked evidence with a structured summary rather than
prose, which is honest rather than degraded.

**Drift.** on scan completion → for each `memory_source_refs.content_hash` not
matching the file's current hash → `git diff` the two blobs → hunk/line-range
overlap → `findings(stale_risk)` with severity from overlap → memory status to
`needs_review` on high severity only.

## 6. MCP surface

Four read-only tools, one process, stdio transport. Read-only is the whole point:
an agent cannot mutate the vault.

| Tool | Returns |
|---|---|
| `kernote_search_memory(query, type?, limit?)` | Ranked memories with citations and scores |
| `kernote_project_summary()` | Stack, layout, key decisions, current state |
| `kernote_get_decision(subject)` | Decision, alternatives, rationale, status, evidence |
| `kernote_build_context(task, token_budget?)` | Budgeted Markdown bundle with citations |

Writes stay in the UI behind human approval. If agent-initiated memory proposals
are wanted later, they arrive as `findings`, not as direct writes.

## 7. Security and privacy boundaries

- **Scanning is read-only.** The scanner has no write path to the project tree.
- **Secret refusal** before read: deny-list (`.env*`, `*.pem`, `*.key`, `id_rsa*`,
  `*.p12`, `credentials*`, `*.keystore`), plus an entropy heuristic on candidate
  values, plus exclusion of `node_modules`, `.venv`, `dist`, `build`, `target`,
  `.git/objects`.
- **No network by default.** No telemetry. Any remote provider is opt-in and must
  state exactly what leaves the machine before it is enabled.
- **No shell execution from content.** Git is invoked via `subprocess` with an
  argument list, never a shell string, and never with arguments derived from
  scanned content or model output.
- **No silent writes** to source files or canonical docs. Export is a file the
  user saves; it never overwrites project docs in place.
- **CORS** limited to the Vite dev origin; the API binds `127.0.0.1` only.

## 8. Risks for Windows / Linux / this machine

Target: Dell Latitude 3420, i5 11th gen, 16 GB RAM, Intel Iris Xe (**no CUDA**).

| # | Risk | Mitigation |
|---|---|---|
| R1 | `torch` CPU wheel is ~2 GB and slow to install; too heavy as a runtime dep | Runtime embeddings via `fastembed` (ONNX, no torch). `torch` lives in `requirements-ml.txt`, experiments only (ADR-0004, ADR-0011) |
| R2 | Vector extension install friction on Windows — **confirmed**, not predicted: `sqlite-vec` issues #13/#45 report the precompiled extension failing to load from Python on Win10/11, sometimes after `enable_load_extension()` succeeded | numpy brute force for MVP; any `sqlite-vec` spike starts with a native-Windows load test (ADR-0003a) |
| R3 | Node.js is **not installed** on this machine | Install Node 20 LTS before Day 3; blocker recorded in handoff |
| R4 | Windows path separators, long paths, reserved names | Internal paths are POSIX-relative strings; `pathlib` at the edges; test with a >260-char path |
| R5 | `core.autocrlf` makes Git blob hashes differ across OS for identical content | `content_hash` over raw bytes is primary; blob hash is attribution only |
| R6 | SQLite file locking / `database is locked` under concurrent scan + query | WAL, `busy_timeout`, single writer, scans batched in one transaction per file group |
| R7 | Iris Xe gives no GPU acceleration | CPU-only budgets; measure, never assume |
| R8 | Embedding a large repo exhausts RAM | Stream and batch; cap chunk count per run; report progress |
| R9 | Interrupted indexing leaves partial state | `scan_runs.status`, idempotent re-run, recovery test |
| R10 | False stale alerts destroy trust | Line-range overlap test; severity bands; every finding shows its diff |
| R11 | `tree-sitter` is a native wheel — a new install-failure surface on Windows (ADR-0012) | Prebuilt wheels for Win/Linux; code-symbol extraction degrades to "skip this language" rather than failing a scan, and the Day-18 Windows checkpoint covers it |
| R12 | Larger dependency tree from ADR-0010 widens the supply-chain and audit surface | MIT/Apache/BSD/ISC only; `pip-licenses` and `detect-secrets` in the Day-23 gate; every core-path dep states what it replaced in `TOOLING.md` |

Performance budgets to measure on the actual laptop (not guesses — these are the
targets the Day 23 benchmark checks): first scan of a ~2k-file repo under 3 min;
rescan with no changes under 10 s; ask-latency p50 under 1.5 s; DB under 200 MB
for a medium repo.

## 9. Testing strategy

- **Unit** — `domain/` scoring and rules, extractors against fixture files
  (snapshot-tested with `syrupy`, so an extractor change is a reviewable diff),
  chunk line-anchor correctness and drift overlap logic (property-tested with
  `hypothesis`, since off-by-one errors here corrupt provenance invisibly),
  secret refusal.
- **Integration** — scan a fixture repo twice and assert zero new captures;
  memory CRUD across a simulated restart; reindex equivalence; the fixed
  retrieval question set; MCP tool round-trip.
- **Fixtures** — `samples/demo-repo` plus a deliberately hostile fixture
  containing a fake `.env`, a fake private key, a binary, a 5 MB generated file
  and a CRLF file. Note these test our *wiring* of `detect-secrets`, `pathspec`
  and `identify`, not a reimplementation of them (ADR-0013).
- **Retrieval quality** — `ranx` computes Recall@k, MRR and nDCG over the
  labelled question set, plus citation correctness and abstention rate; this
  harness is also what decides ADR-0014.
- **Conflict detection** (`Must` as of ADR-0015) — fixtures with two sources
  that disagree on the same entity attribute, the same procedure step and the
  same decision subject with overlapping validity. Assert one finding holding
  **both** claims, and that no claim was dropped or auto-resolved.
- Evaluation reports against the four MemoryAgentBench axes: retention, update,
  retrieval, conflict resolution.
- **E2E** — Playwright drives the S1 restart-persistence slice, which is the
  Day-5 gate.
- Each invariant in `MEMORY_MODEL.md` §9 gets a named test.
- CI installs `requirements.txt` + `requirements-dev.txt` only — **never**
  `requirements-ml.txt`. That is the mechanism that keeps "works with no ML
  stack and no paid API" true rather than aspirational.
