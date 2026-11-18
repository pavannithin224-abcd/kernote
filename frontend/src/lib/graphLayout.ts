/**
 * A deterministic force layout, computed once.
 *
 * Why not a library: the two things a graph view needs here are positions and
 * hit-testing, and both are a few dozen lines. `@xyflow/react` is not
 * installed in this project (checked: absent from package.json and
 * node_modules), and adding ~400KB to draw circles and lines would sit badly
 * beside a brief that also says to avoid unnecessary dependencies. If
 * node-dragging, minimaps or nested groups are wanted later, that is the
 * moment to take the dependency.
 *
 * **Deterministic on purpose.** Positions derive from a hash of each memory's
 * id, so the same graph lays out the same way on every visit. A layout that
 * reshuffles on each render makes a network impossible to learn, and this
 * repository prefers deterministic output everywhere else.
 *
 * Cost: O(n²) repulsion over `ITERATIONS`. At the server's 160-node cap that
 * is ~2M operations, a few milliseconds, run once inside a `useMemo` -- not
 * per frame. Nothing here runs during animation.
 */

export interface LayoutNode {
  id: string
  degree: number
}

export interface LayoutEdge {
  src: string
  dst: string
  weight: number
}

export interface Placed {
  id: string
  x: number
  y: number
}

const ITERATIONS = 90
const REPULSION = 820
const SPRING = 0.045
const GRAVITY = 0.012

/** FNV-1a. Small, fast, and stable across runs -- `Math.random()` would make
 *  the layout differ every visit, which is the thing to avoid. */
function hash(id: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0) / 0xffffffff
}

export function layout(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  width: number,
  height: number,
): Map<string, Placed> {
  const n = nodes.length
  const cx = width / 2
  const cy = height / 2
  const placed: Placed[] = nodes.map((node, i) => {
    // Golden-angle spiral from a hashed offset: an even starting spread, so
    // the relaxation below has little work to do and never has to escape a
    // pile of coincident points.
    const a = hash(node.id) * Math.PI * 2 + i * 2.39996
    const t = 0.12 + 0.38 * Math.sqrt((i + 1) / n)
    return {
      id: node.id,
      x: cx + Math.cos(a) * t * width,
      y: cy + Math.sin(a) * t * height,
    }
  })

  const index = new Map(placed.map((p, i) => [p.id, i]))
  const links = edges
    .map((e) => ({ a: index.get(e.src), b: index.get(e.dst), w: e.weight }))
    .filter((l): l is { a: number; b: number; w: number } => l.a !== undefined && l.b !== undefined)

  const vx = new Float64Array(n)
  const vy = new Float64Array(n)

  // The simulation is run in a space normalised to the viewport, so the
  // equilibrium shape is an ellipse matching the box rather than a circle
  // sitting inside it. Without this a wide, short panel wastes most of its
  // width: the 320x150 dashboard preview settled into a 64px-wide column with
  // 128px of dead space on either side. Scaling at the end instead would fill
  // the box by stretching, which distorts the only thing a position means
  // here -- how far apart two records are.
  const ax = height / width

  for (let step = 0; step < ITERATIONS; step++) {
    vx.fill(0)
    vy.fill(0)

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = (placed[i].x - placed[j].x) * ax
        let dy = placed[i].y - placed[j].y
        let d2 = dx * dx + dy * dy
        if (d2 < 0.01) {
          // Identical positions have no direction to push apart along; nudge
          // deterministically rather than with a random jitter.
          dx = (i - j) * 0.01
          dy = 0.01
          d2 = dx * dx + dy * dy
        }
        const f = REPULSION / d2
        const d = Math.sqrt(d2)
        // Undo the normalisation on the way out, so the push is applied in
        // viewport units.
        vx[i] += (dx / d / ax) * f
        vy[i] += (dy / d) * f
        vx[j] -= (dx / d / ax) * f
        vy[j] -= (dy / d) * f
      }
    }

    for (const l of links) {
      const dx = placed[l.b].x - placed[l.a].x
      const dy = placed[l.b].y - placed[l.a].y
      // A stronger relationship pulls harder, so specific links cluster and
      // weak ones stay loose. This is the only place edge weight affects
      // what is drawn rather than what is reported.
      const f = SPRING * (0.4 + l.w)
      vx[l.a] += dx * f
      vy[l.a] += dy * f
      vx[l.b] -= dx * f
      vy[l.b] -= dy * f
    }

    const cool = 1 - step / ITERATIONS
    for (let i = 0; i < n; i++) {
      vx[i] += (cx - placed[i].x) * GRAVITY * ax * ax
      vy[i] += (cy - placed[i].y) * GRAVITY
      placed[i].x += Math.max(-18, Math.min(18, vx[i])) * cool
      placed[i].y += Math.max(-18, Math.min(18, vy[i])) * cool
    }
  }

  // Fit to the viewport with a margin, so a sparse graph is not a dot in the
  // middle and a dense one is not clipped.
  const pad = 22
  const xs = placed.map((p) => p.x)
  const ys = placed.map((p) => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const sx = (width - pad * 2) / Math.max(1, maxX - minX)
  const sy = (height - pad * 2) / Math.max(1, maxY - minY)
  // One scale for both axes, so the shape of the network is not distorted to
  // fill the box -- an aspect-stretched graph misrepresents distance, which
  // is the only thing position means here.
  const s = Math.min(sx, sy)

  // Centre the scaled result. Anchoring at `pad` instead left a graph whose
  // aspect differs from the viewport's pinned to one corner: on the real
  // 160-node graph it occupied x 22-508 of 900, with the right 43% empty.
  const offsetX = (width - (maxX - minX) * s) / 2
  const offsetY = (height - (maxY - minY) * s) / 2

  return new Map(
    placed.map((p) => [
      p.id,
      { id: p.id, x: offsetX + (p.x - minX) * s, y: offsetY + (p.y - minY) * s },
    ]),
  )
}
