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

**Day 1 of a 25-day build (2026-11-06 → 2026-11-30). Planning only — no
application code yet.** Read `docs/DEV_HANDOFF.md` for exactly where things
stand and what the next safe task is.

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
| [docs/COMPETITIVE_LANDSCAPE.md](docs/COMPETITIVE_LANDSCAPE.md) | Who else ships this, where the real gap is, platform risk, pricing signal, recommended scope changes |
| [docs/TOOLING.md](docs/TOOLING.md) | What we build vs borrow, every dependency and what it replaces, prior-art repos to study, license policy |
| [docs/DEV_HANDOFF.md](docs/DEV_HANDOFF.md) | Current state, verification performed, known blockers, next safe task |
| [CLAUDE.md](CLAUDE.md) | The project contract for Claude Code — authoritative over every document above |

## Setup

Not yet available — there is no runnable code. Setup instructions arrive with the
Day 3–5 application foundation. Prerequisites being targeted: Python 3.12+,
Node 20 LTS, Git 2.40+.

## Known limitations (kept honest from day one)

- "Desktop-quality" describes UI craft, not a packaged desktop binary — the MVP
  runs as a localhost app (ADR-0001).
- Extraction is deterministic and rule-based by default, so recall is lower than
  an LLM pipeline would give; a model adapter is optional and additive (ADR-0006).
- Only tested languages and agents will be claimed as supported. Nothing is
  claimed as supported yet.
- Retrieval answers are **extractive**, not generated prose. Kernote does not
  compete with frontier-LLM codebase chat on fluency; it competes on whether the
  citations are correct and the abstentions are honest.
- The agent-memory space is crowded and partly free. Kernote's claim is narrow
  and specific: knowledge **update** and **conflict resolution**, the two
  competencies published benchmarks show no system masters.
