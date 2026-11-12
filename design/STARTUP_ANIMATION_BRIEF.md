# Startup animation — brief

**Received 2026-11-12. Not started.** The second of two agreed tracks; see
`DASHBOARD_BRIEF.md` for the first. Visual reference:
`design/refs/01-dashboard-target.png`.

---

## The brief, as given

A distinctive ASCII startup animation combining a dynamic knowledge-graph
formation with terminal-style logo assembly.

**1 · Graph formation**
Near-black `#0b0d10` with a very subtle technical grid. Small ASCII
characters, dots, symbols and nodes scattered across the centre, gradually
connected by thin animated lines, as if memories are being discovered and
linked. Electric cyan `#22e5ff` for connections, acid green `#a6ff3d` for
active nodes, violet `#a78bfa` for relationships.

**2 · Logo assembly**
Nodes and connections move inward and resolve into the wordmark `kernote_` —
`ker` in white, `note_` in cyan, the underscore blinking like a terminal
cursor.

**3 · Terminal initialisation**
```
BOOTING KERNOTE
[OK] DATABASE
[OK] MEMORY ENGINE
[OK] RETRIEVAL INDEX
[OK] LOCAL SERVICES
WORKSPACE READY
```
**These must reflect actual initialisation. Never show OK or READY before the
corresponding service is ready.**

**4 · Transition**
Fade out smoothly into the existing dashboard. No flash, no hard reload.

**Technical**
- Inspect the existing architecture and startup flow first
- Lightweight CSS animation with SVG or DOM nodes; no heavy Canvas, no excess CPU
- No unnecessary dependencies
- ~1–2s when services are already ready
- When initialisation is slower, show genuine live status — no fake progress,
  no artificial delay
- Startup or reload only, never on internal navigation
- Support reduced motion
- Works at laptop and smaller resolutions
- Preserve existing dashboard functionality, branding and palette
- Do not rebuild unrelated components

---

## The honest problem with the five status lines

The brief forbids showing `[OK]` before a service is ready. Here is what can
actually be known, which is the thing to settle before any of this is built.

| Line | Real signal? |
|---|---|
| `DATABASE` | **Yes.** `GET /health` returns `status`, `schema_version` and `db_path`, and it only answers once migrations have run. A genuine readiness gate. |
| `MEMORY ENGINE` | **No such service.** Ingestion, extraction and review are library code inside the same process. Nothing starts, so nothing can become ready. |
| `RETRIEVAL INDEX` | **Partly.** FTS5 exists the moment the schema does, so it is ready whenever the database is. Semantic search is opt-in and may legitimately be **absent** — `GET /projects/{id}/embeddings` reports that. "OK" would be wrong when embeddings are off; that is a normal state, not a failure. |
| `LOCAL SERVICES` | **Undefined.** The API answering *is* the service, and the UI cannot render before it. The MCP server is a separate process the app does not manage. |
| `WORKSPACE READY` | Fair once the above resolve and the project list has loaded. |

Three of the five have nothing truthful behind them as written. Options, to
decide together: rename the lines to things that are genuinely checked
(schema, FTS, embeddings, project list), drop the ones that are not, or let a
line read something other than OK — `off`, `none`, `n/a` — which is arguably
more interesting than five green ticks and is exactly the product's own
argument about honest status.

**A second, quieter problem:** locally `/health` answers in milliseconds, so
in the normal case the animation is paced entirely by its own duration and the
status lines are decoration that happens to be true. The live-status
requirement only does real work when something is slow or broken. Worth being
clear-eyed that this is a *startup flourish* with an honesty constraint, not a
progress indicator.

---

## Things to settle before building

1. **Which wordmark is the brand.** The mock's header is the terminal wordmark
   `kernote_` with no icon. We have a mark — the K with a broken arm
   (`design/logo/`) — currently in the sidebar header, plus a reveal animation
   and a favicon built from it. They can coexist (icon in the favicon and tab,
   wordmark in the header) but that is a decision, and this brief's animation
   resolves the graph into the *wordmark*, not the mark.
2. **Startup only, not navigation.** The app is a Vite SPA; React Router
   navigation does not remount the root. Needs a module-scope flag or
   `sessionStorage`, and a deliberate answer for what a dev-server hot reload
   should do.
3. **Reduced motion.** The established pattern in this repo is: the finished
   state is the base state, and animation runs only under
   `prefers-reduced-motion: no-preference`, so reduced motion gets the end
   frame rather than a blank one. Reuse it.
4. **Node budget.** "Lightweight" needs a number. A few dozen DOM or SVG nodes
   animated with transforms and opacity is cheap; a few hundred with animated
   line geometry is not.
5. **Order relative to the dashboard work.** This animation ends by revealing
   the dashboard, and the dashboard is being redesigned in the other track.
   Building the transition before the thing it transitions into would mean
   doing it twice.

---

## The two tracks

| Track | Brief | State |
|---|---|---|
| UI design — dashboard | `DASHBOARD_BRIEF.md` | stored, not started |
| Logo / startup animation | this file | stored, not started |

Suggested order: dashboard first, animation second, for reason 5 above.
