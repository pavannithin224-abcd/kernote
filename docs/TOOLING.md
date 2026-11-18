# Kernote — Tooling, Dependencies and Prior Art

Status: draft for Day 1–2 approval · Last updated 2026-11-06

**Standing principle (ADR-0010).** Kernote is a real product, not a research
demo. Anything that is not Kernote's differentiated core gets taken from a
proven, maintained open-source project — even for small tasks. Hand-rolling a
gitignore matcher or a diff parser is not engineering, it is a bug factory with
a 25-day deadline attached.

The flip side matters as much: a dependency is a liability we accept
deliberately. Admission criteria are in §5.

---

## 1. What we build, and what we borrow

The moat is the **memory lifecycle** — provenance, drift evidence, review flows,
grounded answers. That is where the hand-written code belongs. Everything that
merely gets us to that line is borrowed.

| Build ourselves (the product) | Borrow (solved problems) |
|---|---|
| The four-layer memory model and schema | File walking, ignore semantics, type detection |
| Drift detection and the line-range overlap test | Diff *parsing* |
| Findings / review / resolution lifecycle | Secret detection rules |
| Consolidation with lineage preservation | Code symbol parsing |
| Grounded answer composer (evidence/inference/unknown) | Embedding runtime |
| Importance & confidence scoring *with reasons* | Retrieval metrics |
| Context bundle selection policy | Token-budget fitting algorithm (study Aider) |
| The seven screens and review UX | Diff rendering, graph rendering, tables, toasts |
| MCP tool semantics | MCP protocol plumbing |

## 2. Backend dependency map

### Runtime — `backend/requirements.txt`

| Need | Package | Why this one | Replaces |
|---|---|---|---|
| API | `fastapi`, `uvicorn[standard]` | Per `CLAUDE.md` | — |
| Models / settings | `pydantic` v2, `pydantic-settings` | Schema validation of all structured output is a contract requirement | — |
| Embeddings | **`fastembed`** | Qdrant's ONNX runtime wrapper: MiniLM at 384-d, **no torch**, batched, model hash-pinned. This *is* ADR-0004 already implemented and maintained | ~150 lines of hand-written `onnxruntime` + `tokenizers` glue |
| Code symbols | **`tree-sitter`** + **`tree-sitter-language-pack`** | One package, 300+ grammars, returns symbols/imports/structure **with byte and line ranges** — exactly what provenance needs | per-language regex parsers (weeks of work, permanently wrong) |
| Markdown | **`markdown-it-py`** + `mdit-py-plugins` | CommonMark-strict, and `token.map` gives `[line_start, line_end]` per token — provenance for free. Front-matter plugin for ADR metadata | regex heading/fence parsing |
| Ignore rules | **`pathspec`** | Correct gitignore semantics: negation, `**`, dir-only, precedence. Used by pre-commit and black | a hand-rolled matcher that silently mishandles `!` |
| File typing | **`identify`** | pre-commit's filename/content → tag mapping, incl. `binary` vs `text` | hand-rolled extension lists and binary sniffing |
| Secrets | **`detect-secrets`** | Yelp's plugin-based scanner with a maintained rule corpus and entropy plugins | my "deny-list plus an entropy heuristic", which would miss most real keys |
| Diff hunks | **`unidiff`** | Parses unified diff into hunks with source/target line ranges — the input to the overlap test | a hand-written `@@ -a,b +c,d @@` parser |
| Paths | **`platformdirs`** | Correct per-OS data/config dirs; removes a whole class of Windows bugs | hand-rolled `%APPDATA%` guessing |
| Logging | **`structlog`** | Structured diagnostics without secrets, per contract | — |
| CLI | **`typer`** | `scan`, `reindex`, `export` scripts | argparse boilerplate |
| Vector math | `numpy` | ADR-0003 | — |
| MCP | **`mcp`** (official SDK, FastMCP) | Never hand-roll JSON-RPC framing and the handshake | — |

Git stays on the **Git CLI via `subprocess` with argument lists**, as
`CLAUDE.md` requires. We borrow the *parsing* (`unidiff`), not the invocation.
`pygit2`/`GitPython` were rejected: a native dependency is exactly the Windows
friction ADR-0003 and ADR-0004 exist to avoid.

### Optional — `backend/requirements-ml.txt`

`torch`, `scikit-learn`, `sentence-transformers`, `datasets`, `model2vec`.
Installed only for classifier and embedding experiments. **CI runs without this
file**, which is how we guarantee the product works with no ML stack.

### Dev / test — `backend/requirements-dev.txt`

| Need | Package | Why |
|---|---|---|
| Tests | `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` | — |
| Extractor regression | **`syrupy`** | Snapshot-test extractor output against fixtures; an extractor change becomes a reviewable diff |
| Invariants | **`hypothesis`** | Property tests for chunk line-anchor arithmetic and drift overlap — the two places off-by-one errors would corrupt provenance invisibly |
| Retrieval metrics | **`ranx`** | Recall@k, MRR, nDCG for the `PRODUCT_SPEC` evaluation plan |
| Lint / format | **`ruff`** | Replaces black + isort + flake8 in one fast tool |
| Types | `mypy` | — |
| Hooks | `pre-commit` | Runs ruff, mypy and `detect-secrets` on every commit — the contract's "no secrets in the diff" rule, enforced by machine |

## 3. Frontend dependency map

| Need | Package | Why |
|---|---|---|
| Core | `react`, `react-router`, `@tanstack/react-query` | Per `CLAUDE.md` |
| UI | `tailwindcss`, **shadcn/ui** (copy-in), `lucide-react` | shadcn is itself the borrow-the-code model |
| Tables | **`@tanstack/react-table`** | Memory Explorer needs sorting/filtering/virtualization |
| **Diff rendering** | **`react-diff-viewer-continued`** | Drift evidence and consolidation before/after previews. Hand-rolling side-by-side diff UI is days of work and a core screen |
| Relationship graph | **`@xyflow/react`** | Memory relationships; also lets us cut the graph view cleanly if we fall behind |
| Typed API client | **`openapi-typescript`** + **`openapi-fetch`** | Generate the client from FastAPI's OpenAPI. A hand-written client drifts from the backend silently |
| Command palette | `cmdk` | Project/memory switching |
| Toasts | `sonner` | Review-action feedback |
| Lint / format | **`biome`** | One fast tool for eslint + prettier |
| Tests | `vitest`, `@testing-library/react`, **`msw`**, **`playwright`** | Playwright carries the S1 restart-persistence E2E, which is the Day-5 gate |

Dev orchestration: a `justfile` plus `honcho` with a `Procfile`, rather than a
hand-written `dev.sh` juggling two processes and signal handling.

## 4. Prior art to study (read, don't necessarily depend on)

| Repo | What to take | License |
|---|---|---|
| **`Aider-AI/aider`** → `aider/repomap.py`, `aider/queries/*.scm` | Personalized-PageRank ranking over a tree-sitter symbol graph, and binary-search fitting of a map into a token budget. Directly applicable to `architecture` importance scoring (F2) and the context bundle (F7). The `.scm` tag queries are a ready-made per-language extraction spec | Apache-2.0 |
| **`cased/kit`** | `queries/<lang>/tags.scm` architecture: adding a language is a query file, not core-logic surgery. Adopt this shape for `ingest/extract/code_symbols.py` | MIT |
| **`github-linguist/linguist`** | `vendor.yml`, `documentation.yml`, `languages.yml` — a curated corpus of vendored/generated-path patterns and language heuristics. These become the scanner's exclude defaults, instead of me inventing them | MIT |
| **`Yelp/detect-secrets`** / `gitleaks/gitleaks` | Rule corpus and the audit-workflow concept | Apache-2.0 / MIT |
| **`simonw/sqlite-utils`**, `datasette` | Production FTS5 patterns: porter tokenizer, `rebuild`, bm25 ranking, triggers for external-content tables | Apache-2.0 |
| **`modelcontextprotocol/python-sdk`** | Server shape, tool schemas, stdio lifecycle | MIT |
| **`asg017/sqlite-vec`** | The spike target if ADR-0003 is revisited. Issues #13 and #45 document the exact Windows extension-load failures that justify deferring it | Apache-2.0/MIT |
| **`minishlab/model2vec`** | Static embeddings; `potion-base-8M` reaches **91.96%** of all-MiniLM-L6-v2 on MTEB at a fraction of the CPU cost (ADR-0014) | MIT |
| **`qdrant/fastembed`** | ONNX embedding packaging done right | Apache-2.0 |
| **`npryce/adr-tools`** | The de-facto ADR file conventions the `rule:adr` extractor should recognize | MIT |
| **`continuedev/continue`**, `cline/cline` | How real coding agents actually consume project context — shapes the F7 bundle format and the F9 tool surface so we match what agents expect | Apache-2.0 / MIT |

**License hygiene.** Only MIT / Apache-2.0 / BSD / ISC enter `requirements.txt`
or `package.json`. GPL/AGPL projects may be *read* for approach but never
vendored or linked. Every borrowed snippet carries a comment naming the source
repo, file and license. `pip-licenses` runs in the Day-23 release check.

## 5. When a dependency is *not* the answer

Reuse is the default, not a reflex. A package is rejected when any of these hold:

1. **It owns our core.** A framework that wants to own the memory model, the
   review flow or the answer composer is a competitor, not a dependency.
2. **It drags in a native build or a GPU stack** for a core path — the
   `sqlite-vec` and `torch` cases (ADR-0003, ADR-0004).
3. **It is unmaintained** — no release or substantive commit in ~12 months, for
   anything on a core path.
4. **It is a one-liner.** RRF fusion is ten lines; a package for it is pure risk.
5. **It cannot be tested offline.** Core-path tests must run with no network.
6. **Its license is incompatible** (§4).

Every new dependency on a core path gets one line in this file saying what it
replaced. If it replaced nothing, it does not belong here.

## Packaging (2026-11-18)

```bash
just package      # -> dist/kernote/ , run dist/kernote/kernote
```

A PyInstaller bundle of the API, the built UI and the extractors: **211 MB**,
dominated by `onnxruntime` (69 MB) and `numpy` (41 MB).

**What is in it.** The migrations, the tree-sitter query files, the built
frontend and the evaluation question set — all five source-relative paths now
resolve through `kernote/resources.py`, which knows about `sys._MEIPASS`.
Without that pairing the bundle starts, fails to find its migrations and dies
with a traceback a user cannot act on; that was the first build's behaviour.

**What is deliberately not in it.** The embedding model. It is a ~90 MB
download, opt-in by design (ADR-0023), and bundling it would both treble the
installer and switch on a feature the product keeps off. It is fetched at
first use into the user's cache, exactly as when running from source.

**Verified on the built binary**, not just the build log: schema migrated to
v10 in a fresh data directory, the UI served from inside the bundle, a scan
of `samples/eval-repo` producing 51 memories, analysis running every
detector, and a question answered through FTS5.

**Not done.** No code signing, so macOS and Windows will warn on first run;
no installer wrapper (it is a directory you run from); and the build is
per-platform — this one is Linux x86-64.
