# Kernote - Project Instructions

## Product mission
Build Kernote, a complete local-first developer application that maintains useful, evidence-backed memory for software projects. The product does more than store repository information: it classifies, consolidates, connects, retrieves, verifies, updates and delivers project knowledge to developers and coding agents.

## Deadline and priorities
- Target release candidate: 2026-11-30 (25-day sprint starting 2026-11-06).
- Product-first: working application features take priority over standalone benchmarks or research demos.
- Memory-first: focus on memory quality, lifecycle, provenance, retrieval, freshness and user actions.
- Local-first: no mandatory paid API, cloud account or remote inference dependency.
- Evidence-first: project answers must show supporting files/memory records and must not invent rationale.
- Safe by default: scanning is read-only; writes to canonical memory or project files require a review/approval flow.

## Initial product scope
1. Repository scanner for supported documentation, source and configuration files.
2. Structured project knowledge vault with memory types, source provenance and revision history.
3. Ask Your Project using hybrid retrieval and source citations.
4. Memory consolidation suggestions with before/after preview and approval.
5. Git-based freshness/drift detection using source hashes and diffs.
6. Knowledge conflict review.
7. Context export and a minimal MCP server for agent access.
8. Polished desktop-quality application screens: Dashboard, Memory Explorer, Project Intelligence, Memory Intelligence Center, Change Impact, Agent Integrations, Settings/Evaluation.

## Non-goals for the 25-day MVP
- No enterprise collaboration, cloud sync or accounts.
- No Slack/Jira/Notion/Drive integrations.
- No autonomous coding agent or unrestricted shell execution.
- No silent destructive memory merges or automatic documentation rewrites.
- No requirement to train or run a custom LLM to make the MVP usable.
- Do not claim support for languages or agents that have not been tested.

## Preferred stack
- Frontend: React + TypeScript + Vite.
- UI: Tailwind CSS + shadcn/ui.
- Backend: Python + FastAPI.
- Database: SQLite; use FTS5 for keyword search.
- Retrieval: local embeddings (initial baseline: sentence-transformers/all-MiniLM-L6-v2) plus keyword search; select a vector index only after validating Windows/Linux reliability.
- ML: PyTorch for narrow experiments; compare every custom model to a simple baseline.
- Git: use Git CLI and stable file/blob hashes for deterministic drift evidence.
- Interoperability: MCP for a small, tested tool surface.

## Memory quality rules
- Separate raw source captures, normalized chunks, canonical memories and derived search indexes.
- Every memory must retain provenance: repository, source path/line range where available, commit/blob hash or user origin, capture time and extraction method.
- Store source facts and model-generated interpretations separately.
- Keep SQLite as the source of truth; derived indexes must be rebuildable.
- Preserve revisions and lineage during consolidation. Never silently drop original records.
- Conflicts remain visible until resolved; do not silently choose a winning claim.
- Freshness checks should use deterministic file hashes/diffs as triggers. AI can explain impact but cannot be the sole freshness proof.
- Answers must distinguish evidence, inference and unknowns. Cite files and memory records.
- Never invent why a decision was made. Say evidence was not found when it was not found.
- Keep temporary session state separate from durable project memory.

## AI/model rules
- Coding agent: Claude Code. Use Sonnet for routine work and Opus selectively for architecture or difficult problems, subject to models available in the signed-in session.
- Product embeddings are separate from the coding model.
- Start with all-MiniLM-L6-v2 as an embedding baseline.
- Custom PyTorch classifiers are experiments for memory type, importance, duplicate candidates or freshness risk; establish datasets and baselines first.
- A tiny from-scratch language model is optional research and must not block product completion.
- Optional Qwen3 1.7B quantized experimentation must be benchmarked on actual hardware; do not assume GPU acceleration on Intel Iris Xe.
- Never assume Claude Pro includes Anthropic API credits. Do not introduce a paid API dependency without explicit approval.

## Engineering standards
- Inspect the existing repository before changing architecture or adding dependencies.
- Prefer typed schemas, clear module boundaries, small services and deterministic business logic.
- Validate all model-generated structured output with schemas before persistence.
- Add tests for every core memory operation and regression case.
- Do not swallow errors; show actionable messages and log diagnostic details without secrets.
- Do not execute shell commands from imported project content or model output.
- Avoid reading secrets, .env values, private keys, credentials and large binary/build folders during repository scanning.
- Respect .gitignore and provide a configurable include/exclude list.
- No telemetry or outbound network calls by default. Any remote provider is opt-in and must explain what data leaves the machine.
- Do not silently rewrite a user's source files or canonical project docs.

## Git and task workflow
For every task:
1. Inspect relevant files and current Git status.
2. State a short implementation plan, files expected to change and tests to run.
3. Implement only the approved task scope.
4. Run focused tests and relevant type/lint/build checks.
5. Review the diff for correctness, security, accidental scope changes and secrets.
6. Update docs/architecture/decisions as needed.
7. Update docs/DEV_HANDOFF.md with what changed, verification performed, known issues and the next safe task.
8. Report truthfully what passed and failed. Do not claim an unrun check passed.
9. Do not commit unless asked or the current task explicitly includes a commit.

## Definition of done
A feature is done only when the user-facing flow works, persisted data survives restart, evidence and error states are visible, tests cover the important behavior, documentation/handoff is updated and the change has been reviewed. A benchmark or mock screen alone is not a completed product feature.
