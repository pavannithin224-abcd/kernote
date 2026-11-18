# Visual pass — reading the reference reels

Eight reels, supplied 2026-11-10 as a document with captions and visual
descriptions. This records what I took from them, **what I rejected and why**,
and what I propose to change. Nothing here has been implemented yet.

ADR-0016 applies: reference material, never a template.

---

## The one rule worth adopting

**Reel 6 — @diego.a.does.** *"Two base colours do 90% of the work. The weird
one only goes on the button you want pressed."*

This is the most useful sentence in the whole set, and we currently break it.

`--accent` appears in **12 places** across every screen:

| Where | What it is |
|---|---|
| `App.tsx` | active nav item |
| `Dashboard`, `ProjectIntelligence` ×2, `MaintenanceCenter`, `ChangeImpact`, `AgentIntegrations` | primary buttons |
| `ChangeImpact`, `AgentIntegrations` | inline file paths and tool names |
| `ui.tsx` | the `accent` badge tone, and every `<Citation>` |
| `MaintenanceCenter` | a panel border |

A colour doing nine jobs signals none of them. On the Maintenance Center the
accent is simultaneously the nav state, the Analyze button, a panel border and
every citation — so nothing on that screen says "press me".

**Proposal.** Reserve `--accent` for **the primary action on a screen, and
nothing else**. Everything currently using it moves to:

- citations and inline paths → `--muted` on `--accent-soft` (they are
  reference, not action)
- the active nav item → `--text` on `--accent-soft` (position, not action)
- badges → their own tones, which already exist (`ok`, `warn`)
- the panel border → `--border`

That is a real reduction in visual noise and it costs nothing structurally.
It is also testable: after the change, exactly one element per screen should
carry the accent.

---

## What I am taking from the dashboard reels

**Reels 5 and 7 — @code.xr.** Admin dashboard templates, teal/finance and
purple/white, React + Framer Motion.

Worth taking:

- **A KPI row as the top of a screen.** Four stat cards across, each a number,
  a label and a one-line hint. We already have a `Stat` component doing exactly
  this; the Dashboard just does not lead with it.
- **A consistent panel rhythm** — one rounded container, one border weight, one
  padding step. Ours is close but drifts between screens.
- **Icon-only nav at narrow widths.** Our sidebar hides entirely below `sm`,
  which loses navigation rather than compressing it.

Worth rejecting, with reasons:

- **Glassmorphism over gradients.** Translucent panels on a coloured gradient
  is the defining look of both reels, and it is wrong here. Our screens carry
  `docs/adr/0002-redis-queue.md:10-13`, hunk headers, and hashes. Those need
  maximum contrast against a flat background. Translucency costs legibility to
  buy depth we do not need.
- **The teal and purple palettes themselves.** They read as consumer SaaS. This
  is a review tool for a developer's own repository.
- **Framer Motion.** A real dependency for animation we do not have a use for.
  The one animation in the product is the logo reveal, and that is 40 lines of
  CSS. Revisit if a screen earns it.

---

## What I am rejecting outright

**Reel 1 — @marcelodesignxh**, dark hero sections with a neon accent bar.
**Reel 2 — @ux.rao**, eight print treatments: risograph, dithering, CRT
distortion, infrared, embossing, wireframe render, topographic lines, fisheye.

These are **marketing-page and poster** techniques. Kernote has no hero
section; it has a sidebar and seven dense screens. Dithering and CRT distortion
actively damage small text, and emboss/deboss relies on shadow directions that
invert between light and dark themes.

They would be legitimate for a **landing page** if the project ever has one,
and Reel 2's emboss is a plausible treatment for the logo on a dark splash.
Neither belongs in the application.

**Reels 3 and 4** are pitches rather than references — "comment for the link",
"comment for the skill". See the gap below.

---

## The logo reveal

**Reel 8 — @francois_dvr**, a compilation of After Effects logo reveals: 3D
morphing shapes, soft studio lighting, premium product-render look.

We already have a reveal (`design/logo/reveal.html`), and what makes that reel
work is the same thing ours does: **a beat before the payoff**. Ours is the
pause before the lower arm finishes.

What I am **not** doing is chasing the 3D render. It needs After Effects, it
ships as video rather than as a 48-byte SVG, and a developer tool that opens
with a glossy 3D logo animation is making a promise about itself that the rest
of the product does not keep. The one thing worth borrowing is the *settle* —
a reveal should come to rest, not stop dead. That is a two-line addition.

---

## The gap: the visual library is still missing

Reel 3 says *"comment UI for link to all UI libraries"* and Reel 4 says
*"comment 'design' to get the skill"*. **Both lists are gated behind commenting
on the post**, so neither is in the document, and the reels themselves do not
name a single library.

Reel 3's actual claim is worth repeating though, because it is the argument
behind this whole exercise: *LLMs reach for the official framework docs and the
generic libraries — Tailwind, Bootstrap — and that is what makes output look
generic.* That critique lands. It is why this file exists.

**To close the gap, either:** comment on the post and paste me what arrives, or
name any library you want considered and I will read its documentation
directly. Component-library sites are ordinary web pages; I can fetch those.

---

## Done: accent discipline (2026-11-10)

`var(--accent)` now appears in **exactly one place in the codebase** — the
`Button` component — and every screen with an action has exactly one
`<Button primary>`. The rule is a repo invariant checked by
`backend/tests/unit/test_accent_is_reserved.py`, because it was true once
before and drifted.

What moved:

| Was accent | Now | Why |
|---|---|---|
| six primary buttons | `<Button primary>` | the rule, in one component |
| every `<Citation>` | `--chip` / `--chip-text` | you read a citation, you do not press it |
| inline file paths, MCP tool names | `--chip-text` | reference, not action |
| the memory-type badge (`tone="accent"`) | `tone="info"` on the chip | a category is not a control |
| the Maintenance Center panel border | `--border` / `--chip` | a container is not an action |
| the active nav item's text | `--text` on `--accent-soft` | position, not action |

Two things this turned up that were not in the brief:

**The Ask screen had two primary buttons** — "Ask" and "Download 90 MB and
index". The download is an opt-in, so it is secondary now.

**A contrast failure in dark mode.** The primary button was `text-white` on
`var(--accent)`, and the dark accent is a *light* blue: white on `#8ba2ff`
measures **2.41:1**, below even the 3:1 floor for interface elements. It had
been there since the buttons were written. There is now an
`--accent-contrast` token — white in light, near-black in dark — which takes
it to **7.69:1**. A third test asserts every theme block defines every token,
because a token present in one theme and missing from another is invisible
until someone switches.

## Done: the Dashboard pilot (2026-11-10)

**It now leads with the numbers**, where it previously led with a project
selector and a registration form and buried the figures at position four.

The tiles changed as well as their position. `Captures` and `Scans` were two of
the four headline numbers, and both are plumbing. **`Needs review` replaces
`Scans`** — it reads `counts.open_findings`, which the API has always returned
and the Dashboard has never shown, despite `PRODUCT_SPEC.md` §6 listing a review
queue and despite the review flow being the differentiator. The tile links to
the Maintenance Center and turns `--warn` when it is not zero: a figure telling
you something needs attention without saying where is half a feature. The scan
count moved into the project line, which is where context belongs.

**Registration is a setup task and no longer holds second place for ever.** It
shows expanded only when no project is registered; after that it is a collapsed
`Register another project` at the foot of the screen.

`Stat` gained `to` and `tone` to support this. `tone="warn"` is the warn colour,
which carries its own meaning — not the accent, which still marks only the one
action a screen is for.

Measured against this repository: Memories 546, **Needs review 3**, Source files
149, Captures 137.

## Done: the dashboard redesign (2026-11-14)

Built to `design/DASHBOARD_BRIEF.md` against the supplied mock. Four panels,
every number read from the API: Intelligence Queue (findings + proposals, with
Review / Resolve / Merge wired through), Project Memory Ledger, Local System,
Recent Activity. Nothing is a placeholder — where a figure does not exist the
panel says so rather than inventing one. The brief's "freshness %" tile is
still absent for that reason: there is no defined denominator yet.

### The accent rule was re-expressed, not deleted

The brief predicted this collision, and it landed. The approved identity makes
cyan the *brand* hue — the `note_` of the wordmark, the rule beside a section
heading, the line marking the active nav item — while `test_accent_is_reserved`
forbade any file but `ui.tsx` from naming `--accent` at all. Both could not
stand.

What made the old accent useless was never *naming* it; it was **filling** nine
different surfaces with it, so nothing read as pressable. So the rule now says
exactly that: cyan may draw a line or set type anywhere, but only `Button` may
fill a surface with it. All six remaining uses are a text colour, a border or an
`inset` box-shadow; the only fill in the app is the Capture Memory button. The
new rule was checked by planting `background: 'var(--accent)'` in a screen and
confirming the test caught it. The two companion assertions — one primary action
per screen, every theme defines every token — are unchanged.

### 1366px

Verified by arithmetic, not by eye: the Chrome extension was not reachable, so
this was not seen rendered at that width. At a 1366px viewport the sidebar is
`lg:w-60` (240px), leaving 1126px; `lg:px-6` takes 48px, so the content track is
1078px. The dashboard's `xl` two-column grid engages (1366 > 1280) with a right
rail of `clamp(260px, 24vw, 340px)` = 328px and a 12px gap, leaving 738px on the
left. The ledger's four columns need about 440px, so there is room.

One real defect surfaced while doing that sum. The project-name cell carried
`truncate max-w-[180px]`, which is **inert on an auto-layout table cell** —
browsers ignore `overflow: hidden` there — so a long name would have widened the
column and pushed the panel past its track at exactly this width. The table is
now `table-fixed` with an explicit `colgroup`, and the name truncates inside a
block span. It is the only table in the app.

## Done: the three held-back tiles (2026-11-14)

The brief asked for a freshness %, a database size and per-project freshness
bars. All three were left out of the redesign because none could be computed
without inventing a number; all three are now in. The reasoning is ADR-0037 —
freshness is **three states**, and "never checked" is one of them, because the
naive percentage reads 100% for a project nobody has analyzed.

Visually this cost one ledger column (a 40px bar plus the figure, 116px) and one
Local System row. The bar is `--ok` when nothing is flagged and `--stale` when
something is, which is the first use of the stale red outside a finding badge —
appropriate, since that is exactly what it is reporting. A never-checked project
gets a muted dot and words, no bar: there is no proportion to draw.

## Done: the neon treatment (2026-11-14)

The first build was correct and under-lit: it used the mock's palette but not
its *treatment*. Closing that gap, driven by a side-by-side with the reference
crop.

**The mechanism is one pair of tokens, not a pile of shadows.** `--glow-alpha`
and `--glow-blur` are theme values: 45% / 9px in the dark, **0% / 0px in
daylight**. Three classes consume them — `.neon-outline`, `.neon-bar`,
`.neon-text` — and an element opts in by naming its hue, `style={{ '--neon':
'var(--rel)' }}`. In the light theme `color-mix` at 0% yields transparent, so
every glow rule becomes a no-op rather than something that needs overriding.
Glow on white reads as a printing fault; this way the light theme never has to
fight it.

**What changed visually**

- **Badges are outlined and lit, not filled.** A filled chip at 10px reads as a
  button; an outline reads as a state. `neutral` and `info` stay flat, because
  they label things rather than ask for anything.
- **The queue header counts carry their own hues**, so the header is a legend
  for the rows under it.
- **Record ids glow in the relationship violet.** On a conflict or duplicate
  row the two ids *are* the content.
- **Freshness bars are thicker (5px), lit, and share one `Bar` primitive** with
  everything else that draws a proportion.
- **A ledger summary line**: total memories, aggregate freshness, pending index.

**The summary line obeys ADR-0037.** It averages only projects that have been
checked, and prints "(n unchecked)" beside the figure rather than quietly
folding unchecked projects in at 100%. With no checked project it reads
"freshness not checked". Pending index only appears where semantic search is
actually on.

**Contrast was computed, not eyeballed** — necessary because transparent badges
lose the soft background that was previously doing some of the work. All five
hues clear 4.5:1 against both the panel and the page in both themes, at the
10px badge size: dark ok 14.83, warn 10.39, accent 11.97, rel 6.73, stale 6.55;
light 5.42 to 7.10.

**A guard hole opened and was closed in the same change.** `.neon-bar` fills
with whatever `--neon` names, so binding `--neon` to the accent would fill a
surface with the action colour without the word `background` appearing
anywhere. `test_accent_is_reserved` now rejects that binding too. A guard a
refactor can walk around is worse than no guard, because it still reads as
enforcement.

**Not taken from the mock:** its numbers (2,481 memories, 94% fresh, `PR #482`)
are invented, and the `sort: freshness ↓` control is not wired to anything.
Real data stays; a sort control can be added when it actually sorts.

## Done: the startup reveal (2026-11-14)

Built to `design/STARTUP_ANIMATION_BRIEF.md`; the five questions that brief
left open are answered at the end of it, and the status lines — the one real
argument in the whole feature — are ADR-0038.

The thing worth repeating here: **the sequence prints three lines, not five**,
and on this machine the middle one reads `[ OFF ] SEMANTIC INDEX  opt-in, not
enabled`, because embeddings are switched off. The brief asked for five green
ticks. Two of the five had no service behind them at all. A boot screen that
printed `[OK] MEMORY ENGINE` over library code would be Kernote doing, in its
first second on screen, exactly the thing it exists to stop.

Visually it reuses what is already here: the grid background, the terminal
wordmark with its blinking cursor, the three palette hues for nodes (cyan
connections, green active, violet relationships), and the glow tokens, so the
nodes are lit in the dark and flat in daylight like everything else.

## Remaining order

1. ~~Accent discipline~~ — done, above.
2. ~~Dashboard pilot~~ — done, above.
3. ~~Dashboard redesign~~ — done, above. Never checked at 1366px in a browser;
   the arithmetic stands in for it.
4. ~~The three held-back tiles~~ — done, above. Also unseen.
5. ~~The neon treatment~~ — done, and **confirmed by the user in the running
   app**. The dashboard track is closed.
6. ~~The logo reveal animation~~ — done, and **confirmed by the user in the
   running app**. Both tracks are closed.
7. **Everything else waits** on seeing the pilot, and on the library list.

What I will not do is a blind pass across all seven screens. They hold real
density — a review queue with forty findings, a memory with eleven source refs
— and a look that survives a phone-shot reel does not automatically survive
that.
