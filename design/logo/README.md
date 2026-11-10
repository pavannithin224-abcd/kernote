# The Kernote mark

A **K** whose two arms say what the product does.

The **upper arm is whole** — a claim still verified against its source. The
**lower arm is broken** — the same claim after the code moved under it, held
open for review rather than quietly dropped. Drift detection and conflict
review are the differentiator (ADR-0015), so they are what the mark carries,
rather than "memory" in the abstract.

## Files

| File | Use |
|---|---|
| `kernote-mark.svg` | The mark. 24px and above. |
| `kernote-mark-solid.svg` | Below 24px, where the gap goes sub-pixel. |
| `kernote-lockup.svg` | Mark plus wordmark. **Outline the text before publishing.** |
| `preview.html` | The mark at size, on both backgrounds, as a favicon tile. Open it in a browser. |
| `kernote-reveal.svg` | The animated reveal, self-contained. Will **not** animate in a GitHub README, which strips `<style>` from inline SVG — export a GIF or video for that. |
| `reveal.html` | The reveal with a replay button and a theme toggle, plus the lockup version. |
| `../../frontend/public/favicon.svg` | The tile, solid arm, accent background. |
| `../../frontend/src/components/Mark.tsx` | The in-app component; picks the variant from the size. |

## The reveal

It draws in the order the product works: the stem (the record), the upper arm
outward (the claim, verified), then the lower arm starting — stopping —
finishing. **The pause before the final segment is the whole animation.**
Without it this is a letter drawing itself. 1.5s end to end; the wordmark
arrives at 1.3s, on the pause, so the eye is already at the break when the name
lands.

It ends with a **settle** — 1.5% of scale over 0.4s, felt rather than seen.
That is the one thing worth taking from a 3D motion-design reveal that an
inline SVG can honestly offer; the rest of that look needs After Effects and
ships as video.

The finished mark is the **base** state and the animation only runs under
`prefers-reduced-motion: no-preference`, so a reader who has asked for less
motion gets the mark rather than a blank frame.

## Rules that matter

- **`currentColor` everywhere.** The mark inherits the surrounding text colour,
  so there is no light artwork and no dark artwork to keep in step.
- **Under 24px, use the solid arm.** The gap is 4 units of 48, so at 16px it is
  about 1.3px and reads as a rendering fault rather than as meaning. The React
  component switches automatically; static use must choose.
- **Butt caps, not round or square.** A cap extends half the stroke width at
  each end, which on a 5-wide stroke closes most of a 4-wide gap. The gap is two
  explicit path segments rather than a `stroke-dasharray`, so it is exact at
  every size and does not drift with the renderer.
- **Clear space:** at least the width of the stem (5 units of 48) on every side.
- **Do not** recolour the two arms differently, add a gradient, outline it,
  rotate it, or close the gap. The gap is the idea.
- In the lockup the mark **is** the K, so the word continues as `ernote`. Do not
  set "Kernote" beside it — it reads as *KKernote*.

## Deliberately not

A brain, a lightbulb, a database cylinder, a speech bubble, a memory chip, a
graph of nodes, or a generic rounded square with a letter in it — which is what
the placeholder favicon was.

## What this is not

**It is not trademark clearance.** The mark is original work and avoids the
obvious category clichés, but "nobody has used this" is a claim no amount of
design care can establish. `docs/PRODUCT_SPEC.md` §9 already flags the *name* as
provisional pending trademark, domain and registry checks; the mark needs the
same treatment — a device-mark search in the relevant classes and jurisdictions
— before any public use. A reverse-image search is a cheap first pass and not a
substitute.
