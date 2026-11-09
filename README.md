# Kernote

**Project Memory and Intelligence for Developers.** Local-first.

**Reviewable project memory.** Every fact carries its evidence, every change to
the code tells you which facts to re-check, and nothing enters or leaves the
vault without you seeing why.

Kernote builds a structured, evidence-backed model of a software project, keeps
that model honest as the code changes, and serves the relevant parts to
developers and coding agents on demand. It is an audit and review workspace, not
an agent memory server — see
[docs/COMPETITIVE_LANDSCAPE.md](docs/COMPETITIVE_LANDSCAPE.md).

> Storage is only the first step. The product earns its value by maintaining,
> connecting, retrieving, validating and applying project memory. A feature is
> not complete just because it can save a record.

`Kernote` is a **provisional working name** pending trademark, domain and
registry clearance — see `docs/PRODUCT_SPEC.md` §9.

---

## Status

**Release candidate — all 9 stages complete** (Day 4 of a 25-day build
targeting 2026-11-30), each stage followed by a defect sweep against real data.

`scripts/demo.py` runs the whole product end to end and is the release gate:
scan, idempotent rescan, a cited answer, an honest refusal, a planted
contradiction held open, drift detected down to the overlapping hunk, a human
resolution, a budgeted context bundle, the read-only MCP surface, the measured
evaluation, and a real process restart. It is verified from a clean clone.

The app runs end to end: register a local project, scan it read-only, browse
typed memories with line-exact provenance and revision history, ask questions
and get cited evidence or an explicit "evidence not found", review drift and
conflict findings, approve a consolidation with lineage preserved, and serve
the result to a coding agent over a read-only MCP surface. All of it survives
a restart.

Retrieval quality is measured against a labelled question set rather than
asserted — see [docs/EVALUATION.md](docs/EVALUATION.md). Read
`docs/DEV_HANDOFF.md` for exactly where things stand, what is verified and
what is not.

## What it does (planned MVP)

- **Scans** a repository read-only, under an allowlist that refuses secrets,
  binaries and build output, and explains every file it skipped.
- **Stores** typed memory records — facts, architecture, decisions, procedures,
  conventions, gotchas, current state — each with provenance down to file, line
  range and content hash, plus full revision history.
- **Notices** when a Git change may have invalidated a memory, and shows the
  **overlapping diff hunk** that triggered the concern — not just "the repo
  changed."
- **Holds conflicts open.** When two sources disagree, both claims stay visible
  with their origins and dates until you resolve it. Kernote never silently picks
  a winner.
- **Answers** project questions with citations, labelling every claim as
  evidence, inference or unknown, and saying "evidence not found" when that is
  the truth.
- **Proposes** consolidation of duplicates with a before/after preview and
  nothing merged without approval.
- **Serves** approved context to coding agents over a read-only MCP surface.

## Principles

| | |
|---|---|
| Local-first | No mandatory paid API, cloud account or remote inference |
| Evidence-first | Answers cite sources; rationale is never invented |
| Safe by default | Scanning is read-only; canonical writes need approval |
| Memory-first | Quality, lifecycle, provenance, freshness — not just ingestion |

No telemetry. No outbound network calls by default. Any remote provider is
opt-in and must state what leaves the machine.

## Planned stack

React + TypeScript + Vite · Tailwind + shadcn/ui · FastAPI · SQLite with FTS5 ·
local MiniLM embeddings via onnxruntime · Git CLI for deterministic drift
evidence · MCP for agent access. PyTorch is used only for optional, clearly
separated experiments.

## Documentation

| Document | What is in it |
|---|---|
| [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) | Problem, users, features with priorities, screens, acceptance criteria, open questions |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Process shape, module boundaries, repo structure, API surface, full SQLite schema, pipelines, security boundaries, platform risks |
| [docs/MEMORY_MODEL.md](docs/MEMORY_MODEL.md) | The four data layers, nine lifecycle stages, record design, provenance, intelligence behaviours, invariants |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones with dates, vertical slices, per-milestone definition of done, scope-control order |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADRs with alternatives and consequences |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Measured retrieval quality: citation correctness, abstention, Recall@k, nDCG |
| [docs/COMPETITIVE_LANDSCAPE.md](docs/COMPETITIVE_LANDSCAPE.md) | Who else ships this, where the real gap is, platform risk, pricing signal, recommended scope changes |
| [docs/TOOLING.md](docs/TOOLING.md) | What we build vs borrow, every dependency and what it replaces, prior-art repos to study, license policy |
| [docs/DEV_HANDOFF.md](docs/DEV_HANDOFF.md) | Current state, verification performed, known blockers, next safe task |
| [CLAUDE.md](CLAUDE.md) | The project contract for Claude Code — authoritative over every document above |

## Setup

Requires Python 3.12+, Node 20 LTS and Git 2.40+.

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt
```

```bash
npm --prefix frontend install
```

Run both processes together, then open http://localhost:5173:

```bash
backend/.venv/bin/honcho start
```

With [`just`](https://github.com/casey/just) installed, `just dev` does the same,
and `just ci` runs lint, tests and the frontend build. Without `just` or honcho,
`./scripts/dev.sh` is a plain-bash fallback.

### Choosing what gets scanned

Kernote reads a project's documentation, source and configuration under a
built-in allowlist, honours `.gitignore`, and explains every file it skipped.
To adjust it, commit a `.kernote.toml` to the repository root:

```toml
[scan]
include = ["data/schemas/**/*.json", "deploy/*.yaml"]
exclude = ["vendor/**", "docs/generated/**"]
```

`include` widens the allowlist — use it for meaningful files Kernote does not
recognise by name. `exclude` skips paths regardless. A `.kernoteignore` file is
read as additional exclude patterns. Patterns are `.gitignore` syntax.

Four rules worth knowing, because the asymmetry is deliberate:

- **Exclude always beats include.** The safe direction wins.
- **Include widens only the allowlist** — the question "is this a kind of file
  Kernote reads?"
- **Include cannot override** a secret refusal, `.gitignore`, the size limit or
  the binary check. A config file inside a repository is untrusted input and
  must not be able to talk Kernote into reading a private key.
- **`.gitignore` is always respected** and there is deliberately no switch to
  disable it.

Settings & Evaluation shows the effective configuration with its provenance,
and holds a machine-local override — the equivalent of `.git/info/exclude` next
to a shared `.gitignore`. Kernote never writes into your repository.

The API serves `127.0.0.1:8787` and the web app proxies `/api` to it, so the
browser only ever talks to one origin. The database lives in your platform data
directory (`just where` prints the path); override it with `KERNOTE_DATA_DIR`.

### Verify

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Then run the end-to-end demo, which exercises every feature against the real
API and exits non-zero if any step fails:

```bash
backend/.venv/bin/python scripts/demo.py
```

It starts its own API on a free port, works on a **copy** of
`samples/eval-repo` in a temporary directory, and uses a temporary data
directory — so it never edits your files and its fixture memories never enter
your vault. With `just`, `just demo`.

`requirements-ml.txt` is optional and is **never** installed by CI or by the
commands above — that is what keeps "works with no ML stack and no paid API"
true rather than aspirational.

## Known limitations (kept honest from day one)

- "Desktop-quality" describes UI craft, not a packaged desktop binary — the MVP
  runs as a localhost app (ADR-0001).
- Extraction is deterministic and rule-based by default, so recall is lower than
  an LLM pipeline would give; a model adapter is optional and additive (ADR-0006).
- **Tested languages**: code symbols are extracted for Python, TypeScript, TSX
  and JavaScript. Markdown, and `pyproject.toml` / `package.json` /
  `requirements.txt` manifests, are parsed everywhere. Anything else is stored
  as text without symbol extraction, and nothing further is claimed.
- **Tested agent**: the MCP surface is verified against a real client over
  stdio. Claude Code is the only agent it has been driven from.
- **Linux only, so far.** Everything here was verified on Linux (WSL2). The
  native wheels (`tree-sitter-language-pack`, `fastembed`/onnxruntime) have
  **not** been verified on native Windows, and ADR-0009 is still `proposed`.
- Retrieval answers are **extractive**, not generated prose. Kernote does not
  compete with frontier-LLM codebase chat on fluency; it competes on whether the
  citations are correct and the abstentions are honest. Measured on our own
  31-question labelled set: **citation correctness 52%**, **useful abstention
  83%**, Recall@5 0.74 — and on a real sibling repository it declines on
  **4 of 4** unanswerable questions. The known weakness is the opposite error — on 24% of
  answerable questions it finds the right document and declines to call it an
  answer, because a paraphrased question shares no words with the source it
  needs (28% on the fixture, 11% on the real repository). When it cannot assert an answer it returns leads ordered by meaning,
  and the right document is first in 67% of those cases.
  `docs/EVALUATION.md` has the numbers; ADR-0032 explains why assertion stays
  lexical and ADR-0030 why the remaining gap is a centrality problem.
- **Approval has no undo.** A consolidation merge preserves full lineage and
  nothing is ever silently dropped, so the information survives — but there is
  no one-click reverse of an approval.
- **The UI is functional, not finished.** It shows real data and real error
  states throughout, and a visual pass is deliberately still outstanding.
- The agent-memory space is crowded and partly free. Kernote's claim is narrow
  and specific: knowledge **update** and **conflict resolution**, the two
  competencies published benchmarks show no system masters.
