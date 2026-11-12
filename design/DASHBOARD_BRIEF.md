# Dashboard redesign — brief

**Received 2026-11-11. Not started.** One of two agreed tracks; the other is
`STARTUP_ANIMATION_BRIEF.md`. This one is suggested first, because the
animation ends by revealing the dashboard.

Reference: `design/refs/01-dashboard-target.png` (1918×946). That image is the
primary visual reference and takes precedence over this prose where the two
disagree.

---

## The brief, as given

Implement the Kernote dashboard using the attached preview as the primary
visual reference. First inspect the existing codebase and architecture, then
modify the dashboard **without breaking existing functionality, APIs or backend
logic**.

**Keep**
- Dark charcoal palette `#0b0d10`, `#11151a`
- Cyan `#22e5ff`, neon green `#a6ff3d`, violet `#a78bfa`
- Subtle borders, monospace typography, ASCII symbols, terminal-style details,
  faint grid background
- The compact sidebar, workspace header, Intelligence Queue, Project Memory
  Ledger, Local System panel, Recent Activity layout
- The overall developer-workbench identity

**Change / improve**
- Responsive layout, **especially 1366px laptop screens**
- Refine spacing, alignment, readability
- Neon glow **selective, not everywhere**
- Make navigation, search, Capture Memory, Review and Resolve **functional**
- Replace hardcoded demo values with **real backend data wherever available**
- **Never invent system statuses or memory statistics**
- Handle loading, empty and error states properly

**Constraints**
- Use the existing React + TypeScript + Tailwind setup
- Reuse installed local libraries; **no new dependencies, external APIs, CDNs or
  hosted fonts**
- Do not redesign into a generic SaaS dashboard; do not change the approved
  visual identity
- Prioritise a polished, usable implementation closely matching the preview

---

## What the mock shows that we do not have

Recorded now, while the brief is fresh, because *"never invent system statuses
or memory statistics"* and *"replace hardcoded demo values with real backend
data wherever available"* are in direct tension with parts of the image. Each
of these needs a decision next session: **derive it, build it, or drop the
tile.** None of them should be faked.

### Local System panel — mostly not real
| Mock shows | Reality |
|---|---|
| `model · llama-3.1-8b-q4 · 4.6 GB · loaded` | **There is no LLM.** ADR-0006 keeps generation out of the core loop and nothing in the product loads a chat model. |
| `embeddings · bge-small · 384d · 2,443 vec` | We use **all-MiniLM-L6-v2**, also 384d, via fastembed. Vector count is derivable from the `embeddings` table. Model name must say what is actually loaded. |
| `indexing · 38 docs · 12 docs/s`, `queue 58%`, `eta 00:03` | No throughput, queue-depth or ETA metric exists anywhere. `vector.build_index` is synchronous. |
| `database · kernote.db · 184 MB · WAL` | Path and WAL are real; size is a `stat` away. Fine. |
| `offline · 0 bytes out` | Defensible — the product makes no outbound calls by default — but it would be a **claim**, so it needs to be true by construction, not asserted. |

### Project Memory Ledger
| Mock shows | Reality |
|---|---|
| `94% fresh`, per-project freshness bars | **No freshness metric exists.** Derivable from source refs whose pinned hash still matches, but that is a definition to agree, not a number to invent. |
| `38 pending index` / `24 queued` | Derivable from rows lacking a current embedding. |
| `last write 2m ago` | Derivable from `updated_at`. |
| Per-project memory counts in the sidebar | `GET /projects` does not include counts; `GET /projects/{id}` does. Either N calls or a new list-with-counts endpoint. |

### Navigation
`Timeline`, `Query Console`, `Models` and `Sync & Export` **do not exist**.
Our screens are Dashboard, Memory Explorer, Project Intelligence, Memory
Intelligence, Change Impact, Agent Integrations, Settings & Evaluation. Decide
whether to map, stub honestly, or drop.

---

## What already works and can simply be wired

| Mock element | Endpoint |
|---|---|
| Review / Resolve a finding | `POST /findings/{id}/resolve` |
| Merge duplicates | `POST /proposals/{id}/approve` |
| Intelligence Queue contents | `GET /projects/{id}/findings`, `GET /projects/{id}/proposals` |
| Capture Memory | `POST /projects/{id}/memories` |
| Search | no quick-search endpoint; `POST /projects/{id}/ask` is retrieval with evidence. FTS5 exists underneath, so a light search endpoint is small — but it is **backend work**, which the brief says not to break, not that it cannot be added. |
| Counts for the ledger | `GET /projects/{id}` → `counts` |
| Recent Activity | **No activity feed exists.** Closest: scan runs, revisions, findings by `created_at`. Needs a definition. |

---

## Conflicts with decisions already taken

1. **The palette replaces our token set.** Current accent is `#3b5bdb` /
   `#8ba2ff`. The new one is cyan, neon green and violet on near-black, and the
   mock has no light theme. Our CSS defines three theme blocks and a test
   asserts every block defines every token.
2. **Accent discipline (ADR-0035 work, `test_accent_is_reserved.py`).** The mock
   uses cyan for the Capture Memory button *and* the active nav *and* the
   queue rule, plus green and violet elsewhere. The guard test currently allows
   `var(--accent)` in one file only. Either the rule is re-expressed in terms of
   the new palette, or the test is updated deliberately — **not quietly
   deleted.**
3. **Monospace throughout** is a real shift; we currently use mono for paths and
   numbers only.
4. **Light theme.** The mock is dark-only. Dropping light mode is a decision,
   not an oversight — say so either way.

---

## Suggested order for next session

1. Inspect, confirm the gaps above, and agree what each unreal tile becomes.
2. Palette and tokens first, with the theme question settled.
3. Layout shell: sidebar, header, the three panel regions, at 1366px first.
4. Wire the actions that already have endpoints.
5. Derive the metrics we agreed to derive; omit the rest.
6. Loading, empty and error states for every panel.
