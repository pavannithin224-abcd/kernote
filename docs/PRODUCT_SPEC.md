# Kernote — Product Specification

Status: draft for Day 1–2 approval · Last updated 2026-11-06 · Owner: Pavan

Derived from `Kernote_Project_Kickoff_Guide.pdf` and the project contract. Where this
document and the project contract disagree, the project contract wins and this file is a bug.

---

## 1. Problem

Project knowledge is spread across source files, READMEs, Markdown docs,
configuration, Git history and AI coding sessions. These sources drift apart as
the code changes. The recurring costs are:

- **Rediscovery.** "Why is it built this way?" is re-answered from scratch, often
  by guessing.
- **Silent staleness.** A setup step or an architecture note stays confidently
  wrong for months after the code moved.
- **Context re-entry.** Every new coding-agent session is re-briefed by hand, and
  the hand-maintained instruction files contradict each other.

Existing tools mostly solve *storage* and *document search*. The gap is
**maintenance**: keeping project knowledge useful, current and verifiable.

## 2. Product

Kernote is a local-first, per-project memory and intelligence workspace. It
builds a structured, evidence-backed model of a repository, keeps that model
honest as the code changes, and serves the relevant parts to a developer or a
coding agent on demand.

**One-line descriptor:** Kernote — Project Memory and Intelligence for Developers.

### Positioning (ADR-0015)

> **Reviewable project memory.** Every fact carries its evidence, every change to
> the code tells you which facts to re-check, and nothing enters or leaves the
> vault without you seeing why.

Kernote is an **audit and review workspace** for project knowledge. Agent
delivery over MCP is an *output of* the product, not the pitch.

**Guardrails:**

- Not "another RAG chatbot." Retrieval is a means; maintained memory is the product.
- Not "a place to save notes." Notes without provenance and freshness checks are
  what Kernote exists to replace.
- **Not an agent memory server.** That lane (projectmem, Codified Context,
  agentmemory, mem0, ByteRover, Zep, Letta …) is crowded and mostly free, and the
  coding tools are growing native memory. Competing there on "your agent
  remembers" is competing with free and with the platform.
- The two capabilities the field has *not* solved are **knowledge update** and
  **conflict resolution** (MemoryAgentBench). Those are the pitch.

See `docs/COMPETITIVE_LANDSCAPE.md` for who occupies each lane and the evidence
behind this positioning.

## 3. Users

| User | Situation | What they need from Kernote |
|---|---|---|
| Individual developer, several repos | Context-switches across projects and coding agents | Fast re-entry into a project; one source of agent context |
| Student / independent builder | One long-running project over months | Durable decision history; recoverable setup procedures |
| Small team (2–5) | Wants project memory, not an enterprise KM platform | Shared, reviewable facts with visible evidence |

Out of scope as a user class for the MVP: enterprise orgs needing SSO,
permissions and hosted collaboration.

## 4. Success criteria (qualitative)

A build is on target when all four are demonstrable on a real repository:

1. Changing a module surfaces exactly which memories and docs may now be wrong,
   each with the **diff hunk** that triggered it — not merely "something changed
   in this repo since your last session."
2. When two sources disagree, both claims stay visible with their origins and
   dates until a human resolves it. Kernote never silently picks a winner.
3. Asking why an architectural decision was made returns the supporting source,
   or an explicit "no evidence found" — never a plausible invention.
4. A newcomer reaches working-knowledge of structure, setup and key decisions
   faster than by reading the repo.
5. A coding agent can pull approved, relevant context without a separate
   hand-maintained instruction file.

## 5. Features

Priority labels are the scope-control lever: cut `Later` first, then `Should`.
`Must` items are not negotiable without changing this document.

F5 and F8 are the **differentiators** (ADR-0015): knowledge update and conflict
resolution are the capabilities no existing system masters. F3 is `Must` but
supporting — it is the most commoditized capability in the landscape, so it is
scoped as cited evidence retrieval rather than as a chat competitor.

| # | Feature | User value | Priority |
|---|---|---|---|
| F1 | Repository Knowledge Scanner | Imports structure, Markdown, allowlisted source and config, Git metadata | Must |
| F2 | Project Knowledge Vault | Typed memory records with provenance and revision history | Must |
| F3 | Cited Evidence Retrieval | Returns the files and memory records supporting a question, or states that evidence was not found | Must (supporting) |
| F4 | Memory Consolidation | Duplicate/related proposals with before-after preview and approval | Must |
| F5 | Memory Freshness / Drift | Hash- and diff-triggered review findings | Must |
| F6 | Decision Recall | Decision, alternatives, rationale, status, evidence | Must |
| F7 | Smart Context Builder | Packaged approved context for a task or new agent session | Must |
| F8 | Knowledge Conflict Detection | Contradictions held open for human resolution | **Must** |
| F9 | MCP / Agent Integration | Read-only tool surface for agents | Should |
| F10 | Proactive Recommendations | Suggested reviews, missing docs, related decisions | Later |

### Feature detail — the five that carry the product

Ordered by what makes Kernote different, not by feature number.

**F5 Freshness — the technical centrepiece.** A memory's source references pin a
file path, a line range and a content hash. On rescan, a changed hash on a
referenced file produces a `stale_risk` finding only when the changed **diff
hunks overlap the referenced line range** — this overlap test is both the main
defence against false positives and the measurable difference from prior art,
whose drift checks fire at session start on whole-commit divergence. The finding
shows the triggering diff. AI may explain impact; it may never be the sole proof
of staleness.

**F8 Conflict Detection — the wedge.** Both claims are stored with their sources
and dates and held in `needs_review` until a human resolves them. Detection
signals: contradictory values for the same entity attribute, mutually exclusive
procedure steps for the same task, and decisions on the same subject with
overlapping validity windows. Kernote never picks a winner silently. This is a
`Must` as of ADR-0015 because it is the capability benchmarks show is unmastered
and competitors treat as an afterthought.

**F1 Scanner.** Read-only. Walks a project directory under an include/exclude
allowlist that respects `.gitignore` by default. Skips secrets, `.env`, key
material, binaries and build output. Records every file as a content-addressed
capture so a repeat scan of unchanged files creates no new rows. Collects Git
metadata (HEAD commit, blob hashes, recent diffs) when the directory is a repo,
and degrades gracefully to content hashes when it is not.

**F3 Cited Evidence Retrieval.** Hybrid keyword + semantic retrieval over
canonical memories and normalized chunks, fused and re-ranked, then composed into
a response that labels every claim as **evidence**, **inference** or **unknown**.
Every evidence claim carries a citation to a file+line range or a memory record.
Abstention is a first-class, correct outcome.

Scoped deliberately (ADR-0015): with no LLM in the core loop (ADR-0006) the
composer is **extractive** — ranked evidence plus a structured summary, not
generated prose. We do not claim to beat frontier-LLM codebase chat on fluency.
We claim the citations are correct and the abstentions are honest, and those are
what the acceptance criteria measure.

**F7 Context Builder.** Selects approved, relevant, current memories for a stated
task, renders them as a Markdown bundle with citations, and reports its token
budget and what it dropped.

## 6. Screens

| Screen | Core content |
|---|---|
| Dashboard | Project selector, memory health, recently changed files, recent memories, review queue, alerts |
| Memory Explorer | List, type/status filters, search, detail pane, evidence, version history, relationships |
| Project Intelligence | Q&A, sources panel, citations, follow-ups |
| Memory Intelligence Center | Stale findings, conflicts, duplicates, consolidation proposals, approvals |
| Change Impact | Git change summary, linked memories/docs, why each is affected, review actions |
| Agent Integrations | MCP status, generated instructions, connected clients, context preview |
| Settings & Evaluation | Repo settings, privacy controls, model selection, import/export, metrics, logs |

Interface direction: polished dark-mode-capable desktop workspace; compact
readable typography; evidence panels; visible review state. **No decorative
analytics with no working data behind them** — a chart ships only when its
numbers are real.

## 7. Acceptance criteria (Day 25 gate)

| Area | Definition of done |
|---|---|
| Ingestion | A test repo scans repeatedly without duplicating unchanged source records |
| Provenance | Every canonical memory shows its origin and the source revision that supported it |
| Memory edits | Create/update/archive persist across restart and preserve revision history |
| Retrieval | A fixed question set retrieves expected evidence. Measured as **citation correctness** and **useful-abstention rate**, not answer fluency |
| Consolidation | Duplicates proposed with lineage; no destructive silent merge |
| **Conflict** | Two contradicting sources produce a finding holding **both** claims with their origins and dates; resolution is human and audited |
| Freshness | A file change triggers a deterministic finding with hash/diff evidence, and the finding names the **overlapping hunk** |
| Safety | Scanning is read-only; no command or project-file write runs without explicit approval |
| Product quality | Launches locally, shows errors clearly, key flows work with no paid external API |
| Testing | Unit/integration coverage of ingestion, memory CRUD, retrieval, stale detection, conflict detection, MCP basics |

**Evaluation axes (ADR-0015).** The Day 23–24 evaluation reports against
MemoryAgentBench's four competencies — **retention, update, retrieval, conflict
resolution** — rather than ad-hoc dimensions. Published results show no current
architecture masters all four, so the frame is externally recognized and forces
honesty about where we are strong and weak.

## 8. Non-goals (25-day MVP)

- Slack / Jira / Notion / Google Drive integrations
- Multi-user collaboration, cloud sync, enterprise permissions, accounts
- Automatic writes to project documentation without approval
- Autonomous coding or unrestricted shell execution
- Support for every language and every coding agent — only what is tested is claimed
- Training a production LLM, or depending on a local 1.7B model for core reasoning

## 9. Naming

`Kernote` is a provisional internal working name. The 2026-11-06 screen found no
obvious competing developer-memory product under the exact name, but that is not
a trademark opinion. Before any public promotion: trademark registers (India plus
intended export markets), company names, GitHub org/repo collisions, package
registries, app stores, domains. Rename on a material conflict. Avoided names and
why: `ContextDock`, `RepoMemo`, `RepoLore`, `CodeRecall`, `MemNest`, `Nodary`,
`Memrail` — see §12 of the kickoff guide. The 2026-11-07 competitive scan adds
these to re-screen before any public use: `projectmem`, `Codified Context`,
`agentmemory`, `AI-Memory`, `Basic Memory`, `MemMachine`, `Memanto`,
`EverOS`/`evermind`. None collides with "Kernote".

## 10. Open questions

*All six are now closed. Q1 closed because its stated default held and
nothing else was built; Q4 was closed that way too, then reopened and
answered properly on 2026-11-14 — recorded as closed-by-default rather than decided, so
the distinction stays visible. Q2, Q3, Q5 and Q6 were each settled by a measured
result or a verification run, with the evidence linked.*

| # | Question | Needed by | Default if unanswered |
|---|---|---|---|
| ~~Q1~~ | Is a local generative model in MVP scope at all, or is extraction fully deterministic? | Day 6 | **Closed by outcome: fully deterministic.** The default held — no generative model ships, and the model adapter was never needed (ADR-0006, refined by ADR-0016). The dashboard states it plainly: *language model: none · extraction is deterministic.* |
| ~~Q2~~ | Which real repos are the evaluation set? Guide names Faultiva and CellWise-X | Day 14 | **Closed 2026-11-09: neither.** The real-repository corpus is **IVForge** (`eval/questions-ivforge.json`; the corpus itself is not in this repository) alongside the synthetic fixture. See `EVALUATION.md` §*A real repository*. It immediately caught two faults the synthetic corpus could not see, which is the whole reason for having it. |
| ~~Q3~~ | Is Windows a Day 25 release target or best-effort? | Day 3 | **Closed 2026-11-09: supported, verified, not assumed** (ADR-0009a, which supersedes ADR-0009). Native Windows 3.12.10 AMD64 on an NTFS path: full suite run, three product bugs found and fixed. Two environmental limits stand — **Git is not installed there**, so Change Impact is unverified, and there is no Node, so the frontend build is untested. Both are stated rather than papered over. |
| ~~Q4~~ | Packaging: dev-script startup, or a real installer? | Day 21 | **Reopened and answered 2026-11-14: single process first, installer undecided.** The API now serves the built UI itself (`just app`), so running Kernote is one command on one port with no Node at runtime and no CORS, because there is only one origin. Two processes remain the *development* arrangement, for hot reload. A packaged installer is a separate decision, deliberately not taken yet — see the desktop note in `DEV_HANDOFF.md`. |
| ~~Q5~~ | Can a semantically-retrieved record with no lexical overlap be *asserted* as evidence? | Day 24 | **Closed 2026-11-09: no** (ADR-0032). Measured: the relaxations that would allow it change no verdict alone, and together they halve useful abstention and double wrongly-asserted answers. Leads are ordered by meaning instead. |
| ~~Q6~~ | Can term weighting tell a question's *subject* from an incidental rare word? | after RC | **Closed 2026-11-09: yes, by title agreement** (ADR-0035). Measured against three alternatives; *position in the question*, the signal this question proposed, is actively harmful. A term in a record's own title now counts 2.0 toward the overlap bar and the share. False abstention 28% to 20% on the fixture with the abstention guarantee unchanged. |
