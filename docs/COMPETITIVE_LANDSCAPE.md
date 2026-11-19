# Kernote — Competitive Landscape

Status: draft for Day 2 decision · Researched 2026-11-07 · Owner: Pavan

The kickoff guide's §1 was a **name-availability screen**, not a competitive
analysis. It asked "is this name taken?" and never asked "does this product
already exist?" This document asks the second question. Every claim below is
sourced; where a source is a vendor's own page it is marked as such.

**Headline: the category is crowded, the agent-memory lane is commodity, and
the lane Kernote should occupy is narrower than the kickoff guide assumes but
is genuinely under-served.** Recommended scope changes are in §6.

---

## 1. The four lanes

| Lane | What they do | Representative players | Threat to Kernote |
|---|---|---|---|
| A. Agent memory servers | Persist decisions/context, serve over MCP to Cursor/Claude Code/Codex | projectmem, Codified Context, agentmemory, AI-Memory, ByteRover, Basic Memory, mem0, Zep/Graphiti, Letta, MemMachine, cognee | **Severe.** Crowded, mostly free/OSS, some with thousands of stars |
| B. Repo wiki / cited Q&A | Auto-generate a navigable wiki and answer questions with references | DeepWiki (Cognition), Google Code Wiki, Greptile, Unblocked, Dosu, DeepWiki-Open | **High** on Q&A specifically; all cloud + big-LLM backed |
| C. Doc-drift detection | Compare code changes to docs, flag or draft fixes | Mintlify automations, Swimm, DocDrift (GH Action), TechniDox, moxiedocs, a "Docs Drift" Claude Skill | **Moderate.** Targets published docs, not a memory vault |
| D. Native agent memory | The coding tool remembers by itself | Claude Code memory + `/doctor prompt-audit`, Cursor rules (Memories *removed* in 2.1) | **Platform risk.** Free, bundled, moving |

## 2. The closest thing to Kernote already exists, twice

**`projectmem`** — arXiv:2606.12329, June 2026, University of Utah. Described as
"an open-source, **local-first** memory and judgment layer for AI coding
agents": append-only plain-text typed event log (issues, attempts, fixes,
decisions, notes), deterministically projected into AI-readable summaries served
over MCP, **fully offline with no telemetry**, immutable log as a provenance
trail. Ships as a three-dependency Python package with 14 MCP tools, 19 CLI
commands, 37 tests.

Read that against Kernote's pitch — local-first, typed memory, provenance,
deterministic, MCP, no telemetry — and the overlap is most of the sentence.

**`Codified Context`** — cited in that paper as the closest prior system:
plain-text, file-based, **no vector database**, served over MCP, a Markdown
"hot-memory constitution" of conventions plus on-demand spec documents retrieved
by keyword, **and a drift detector**. Same motivating observation we have:
agents "lose coherence across sessions, forget project conventions, and repeat
known mistakes."

This is the single most important finding in this document. Neither was known to
the kickoff guide.

### Where they are genuinely weaker

| | projectmem / Codified Context | Kernote's opening |
|---|---|---|
| Drift granularity | Codified Context's detector fires **at session start from git-commit divergence** (per the paper) | Per-memory source refs with content hash **plus diff-hunk/line-range overlap** — a finding points at the lines that moved |
| Human interface | CLI + MCP tools; agent-facing by design | Seven-screen review workspace; the developer is the user, not the agent |
| Curation | Append-only log, automatic capture | Explicit consolidation proposals, before/after preview, approval, lineage |
| Conflicts | Not a first-class concern | Both claims held open with sources and dates until a human resolves |
| Evidence surfacing | Log is the audit trail | Evidence/inference/unknown labelling per claim, with abstention |

Their strength is the agent-side gate ("warn before repeating a failed fix").
Ours would be the **human-side review product**. Those are different products
that share a substrate.

## 3. Evidence that the hard part is still unsolved

The projectmem paper cites a benchmark finding that **no current memory
architecture masters all of accurate retrieval, test-time learning, long-range
understanding, and conflict resolution** — and calls this "independent evidence
that the design space remains unsaturated."

`MemoryAgentBench` (Hu, Wang, McAuley) targets exactly four competencies:
**retention, update, retrieval, and conflict resolution.**

So the two capabilities the field has *not* solved — **update (freshness) and
conflict resolution** — are precisely the two the kickoff guide labels F5
(`Must`) and F8 (**`Should`**). That priority assignment is backwards, and §6
recommends fixing it.

Corroboration from a commercial player: Unblocked's engine "reconciles
information across sources, including sources that contradict each other," and
when a conflict cannot be settled it **presents both sources rather than
dropping one** (vendor blog). Independent arrival at Kernote's conflict rule —
which validates the design and warns that a funded team is already there.

## 4. Platform risk: the agents are growing memory themselves

- **Claude Code** ships a memory tool, a per-project memory directory, and
  `/doctor prompt-audit`, which looks for "references to files or commands that
  don't exist, and files that contradict each other" (Claude Code docs). That
  last one overlaps Kernote's conflict detection for instruction files.
- Its docs also concede the project contract is "context, not enforced configuration" and
  that "if two instructions contradict each other, Claude may pick one
  arbitrarily" — which is an argument *for* an external, reviewed memory.
- **Cursor removed its Memories feature in v2.1 (Nov 2025)**, advising users to
  export to a rules file. A platform tried this and retreated: the need is real,
  the in-IDE implementation was not good enough.

Conclusion: do not build anything whose only value proposition is "your agent
remembers." That floor is free, bundled, and shifting under us.

## 5. Monetization signal

| Product | Price |
|---|---|
| Pieces for Developers (local-first dev memory) | Free tier / **$18.99/mo** |
| ByteRover | Free tier + paid tiers |
| DeepWiki | Free at low effort; ~5–10 ACUs/wiki at medium, subscription-gated |
| Lane A OSS (agentmemory, AI-Memory, mem0, projectmem) | Free |

There is demonstrated willingness to pay roughly $9–19/month for local-first
developer memory. There is also a strong free floor. A paid product must be
clearly better than free, not merely present.

## 6. Changes to the plan — ACCEPTED 2026-11-07 (ADR-0015)

All six recommendations below were accepted and applied to `PRODUCT_SPEC.md`,
`ROADMAP.md`, `README.md` and `ARCHITECTURE.md` on 2026-11-07. They are kept in
the original recommendation voice as the record of why.

**6.1 Reposition.** Drop "project memory for coding agents" as the headline —
that is lane A and it is commodity. Lead instead with:

> **Reviewable project memory.** Every fact carries its evidence, every change
> to the code tells you which facts to re-check, and nothing enters or leaves
> the vault without you seeing why.

The product is an **audit and review workspace** for project knowledge. Agent
delivery (MCP) is an *output*, not the pitch.

**6.2 Promote F8 Knowledge Conflict Detection from `Should` to `Must`.**
Benchmarks say conflict resolution is unmastered; the nearest competitors treat
it as an afterthought; it is cheap to build on the `findings` table we already
designed. This is the clearest wedge we have and it is currently optional.

**6.3 Demote F3 "Ask Your Project" from hero feature to supporting.** It is the
most commoditized capability in the landscape (DeepWiki, Greptile, Unblocked,
Dosu), and all of them answer with frontier LLMs while ADR-0006 commits us to a
deterministic, extractive composer with no LLM. We will lose that comparison on
answer fluency. Keep it, scope it honestly as *cited evidence retrieval* rather
than a chat competitor, and stop calling it the Project Brain.

**6.4 Keep drift as the technical centrepiece, and make the granularity the
claim.** Hash + hunk-overlap per memory source ref is measurably finer than
Codified Context's session-start commit divergence. This is demonstrable in the
Day 25 demo and is the one place our determinism is an advantage rather than a
limitation.

**6.5 Adopt MemoryAgentBench's four competencies as the evaluation axes** —
retention, update, retrieval, conflict resolution — replacing the ad-hoc
dimensions in `PRODUCT_SPEC.md` §7. It gives us a defensible, externally
recognized frame for the Day 23–24 evaluation.

**6.6 Re-run the name screen against the new names found here** before any
public use: projectmem, Codified Context, agentmemory, AI-Memory, Basic Memory,
EverOS/evermind, MemMachine, Memanto. None is "Kernote", so the name itself
still looks clear.

**6.7 Study, do not re-derive.** `projectmem` is open source and its paper
documents a two-month self-study over 10 projects. Read its event schema and its
MCP tool surface before finalizing ours (ADR-0010 applies: borrow the solved
parts).

## 7. Honest risk statement

If the goal is a venture-scale product, this market is contested by funded teams
(Cognition, Google, Unblocked, Pieces) above and free OSS below, and Kernote has
no LLM in the core loop by design.

If the goal is a genuinely useful, portfolio-grade, locally-run tool that does
one under-served thing well — **keeping project knowledge honest, with visible
evidence and human review** — the research says that specific thing is still
unsolved, and the 25-day plan can reach it.

The plan does not need to be abandoned. It needs its headline moved from the
crowded claim to the under-served one.

## 8. Sources

- PROJECTMEM — arXiv:2606.12329v1, 10 Jun 2026, CC BY 4.0 — https://arxiv.org/html/2606.12329v1
- Codified Context — as characterized in the above paper's §2
- MemoryAgentBench — "Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions" — https://openreview.net/forum?id=DT7JyQC3MR
- Claude Code memory docs — https://code.claude.com/docs/en/memory
- Claude memory tool — https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Cursor Memories removal in 2.1 — https://unabyss.com/blog/claude-code-cursor-shared-context
- Unblocked context engine / drift — https://getunblocked.com/answers/documentation-drift-between-repos-and-docs-for-ai-agents/
- Mintlify drift automations — https://www.mintlify.com/library/how-to-stop-documentation-drift
- DeepWiki — https://cognition.com/blog/deepwiki · https://docs.devin.ai/work-with-devin/deepwiki
- Google Code Wiki — https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/
- agentmemory — https://agent-memory.dev/ · https://github.com/rohitg00/agentmemory
- ByteRover pricing — https://www.byterover.dev/pricing
- Pieces pricing — https://pieces.app/ (tier figure via evermind.ai comparison)
- Awesome-Agent-Memory survey — https://github.com/TeleAI-UAGI/Awesome-Agent-Memory
