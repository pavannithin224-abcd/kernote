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

## Proposed order

1. **Accent discipline** — small, mechanical, affects every screen, and is the
   single change with the best ratio of improvement to risk.
2. **Dashboard as the pilot** — lead with a KPI row, fix the panel rhythm. One
   screen, so we can judge the direction before it spreads.
3. **Everything else waits** on seeing the pilot, and on the library list.

What I will not do is a blind pass across all seven screens. They hold real
density — a review queue with forty findings, a memory with eleven source refs
— and a look that survives a phone-shot reel does not automatically survive
that.
