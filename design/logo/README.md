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
| `../../frontend/public/favicon.svg` | The tile, solid arm, accent background. |
| `../../frontend/src/components/Mark.tsx` | The in-app component; picks the variant from the size. |

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
