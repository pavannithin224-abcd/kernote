/**
 * Memory Pulse — a live preview of the project's actual knowledge network.
 *
 * Every dot is a real memory and every line is a relationship the database
 * already holds (`GET /projects/{id}/graph`). It is a small, honest sample of
 * the same data the Knowledge Graph screen draws in full: the most connected
 * records, which is what makes a preview worth looking at.
 *
 * Three things keep it cheap:
 *
 *  - **The layout is computed once**, in a `useMemo`, and never during
 *    animation. See `lib/graphLayout.ts`.
 *  - **Movement is declarative.** The travelling particles are SVG
 *    `<animateMotion>` on a handful of edges, and the node breathing is one
 *    CSS keyframe. There is no animation loop, no `requestAnimationFrame`,
 *    and nothing recomputes per frame.
 *  - **Reduced motion gets the end state**: the network, drawn still. Not a
 *    blank panel, and not a frozen first frame.
 *
 * The capture pulse is driven by data, not by a trigger: when the number of
 * memories actually increases, a ring expands once. Firing it on a button
 * press would be a nicer animation and a lie about what happened.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type GraphEdge, type GraphNode } from '../lib/api'
import { layout } from '../lib/graphLayout'
import { Empty, ErrorNote, PanelTitle } from './ui'

const W = 320
const H = 150

/** Enough to read as a network, few enough to stay legible at this size. */
const NODE_SAMPLE = 26
/** Particles are the most expensive thing here; a few read as flow. */
const PARTICLE_EDGES = 5

function hue(node: GraphNode): string {
  // Same meanings as everywhere else: violet marks a record in a recorded
  // relationship, green a healthy claim, amber one awaiting review.
  if (node.flagged) return 'var(--rel)'
  if (node.status === 'needs_review') return 'var(--warn)'
  return 'var(--ok)'
}

export default function MemoryPulse({ projectId }: { projectId: string }) {
  const reduced = useRef(
    typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  ).current

  const graph = useQuery({
    queryKey: ['graph', projectId],
    queryFn: () => api.graph(projectId),
  })

  // A real capture, observed rather than announced.
  const total = graph.data?.totals.memories
  const previous = useRef<number | undefined>(undefined)
  const [pulseKey, setPulseKey] = useState(0)
  useEffect(() => {
    if (total === undefined) return
    if (previous.current !== undefined && total > previous.current) {
      setPulseKey((k) => k + 1)
    }
    previous.current = total
  }, [total])

  const view = useMemo(() => {
    if (!graph.data) return null
    const { nodes, edges } = graph.data
    // The preview shows the most connected corner of the network. `nodes`
    // arrives already ranked by the server, so this is a prefix, not a
    // re-ranking with different opinions.
    const sample = nodes.slice(0, NODE_SAMPLE)
    const keep = new Set(sample.map((n) => n.id))
    const within = edges.filter((e) => keep.has(e.src) && keep.has(e.dst))
    const pos = layout(sample, within, W, H)
    return { sample, within, pos }
  }, [graph.data])

  const body = () => {
    if (graph.isLoading) {
      return (
        <div
          className="animate-pulse rounded"
          style={{ height: H, background: 'var(--chip)' }}
          aria-busy
        />
      )
    }
    if (graph.isError) return <ErrorNote error={graph.error} />
    if (!view || view.sample.length === 0) {
      return (
        <Empty
          title="No memories yet"
          hint="Scan a project to build the network."
        />
      )
    }
    if (view.within.length === 0) {
      return (
        <Empty
          title="No relationships found yet"
          hint="Run an analysis, or capture memories that cite shared files. Nothing is drawn that the database does not hold."
        />
      )
    }

    const particleEdges = reduced
      ? []
      : [...view.within]
          .sort((a, b) => b.weight - a.weight)
          .slice(0, PARTICLE_EDGES)

    return (
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: H }}
        role="img"
        aria-label={`${view.sample.length} memories and ${view.within.length} relationships`}
      >
        {view.within.map((e: GraphEdge, i) => {
          const a = view.pos.get(e.src)
          const b = view.pos.get(e.dst)
          if (!a || !b) return null
          return (
            <line
              key={i}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={e.kind === 'shares' ? 'var(--accent)' : 'var(--rel)'}
              strokeWidth={e.kind === 'shares' ? 0.5 : 1}
              opacity={e.kind === 'shares' ? 0.25 + e.weight * 0.3 : 0.75}
            />
          )
        })}

        {particleEdges.map((e, i) => {
          const a = view.pos.get(e.src)
          const b = view.pos.get(e.dst)
          if (!a || !b) return null
          return (
            <circle key={`p${i}`} r={1.5} fill="var(--accent)" opacity={0.9}>
              <animateMotion
                dur={`${3.2 + i * 0.7}s`}
                repeatCount="indefinite"
                path={`M${a.x},${a.y} L${b.x},${b.y}`}
              />
            </circle>
          )
        })}

        {view.sample.map((n) => {
          const p = view.pos.get(n.id)
          if (!p) return null
          const r = n.flagged ? 3 : 2 + Math.min(1.6, n.degree * 0.18)
          return (
            <circle
              key={n.id}
              cx={p.x} cy={p.y} r={r}
              fill={hue(n)}
              className={reduced ? undefined : 'pulse-node'}
              style={{ ['--d' as string]: `${(p.x + p.y) % 2400}ms` }}
            >
              <title>{n.title}</title>
            </circle>
          )
        })}

        {/* One ring, on a real new memory. */}
        {pulseKey > 0 && !reduced && (
          <circle
            key={pulseKey}
            cx={W / 2} cy={H / 2}
            className="capture-ring"
            fill="none"
            stroke="var(--accent)"
          />
        )}
      </svg>
    )
  }

  const t = graph.data?.totals
  const l = graph.data?.limits
  return (
    <section
      className="rounded border overflow-hidden"
      style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
    >
      <div className="px-3.5 pt-3">
        <PanelTitle
          right={
            t ? (
              <span className="mono">
                {t.connected_memories} of {t.memories} connected
              </span>
            ) : undefined
          }
        >
          Memory Pulse
        </PanelTitle>
      </div>
      <div className="px-3.5 pb-2">{body()}</div>
      <Link
        to="/graph"
        className="mono flex items-center justify-between border-t px-3.5 py-2 text-[11px]"
        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
      >
        <span>
          {l && l.omitted_memories > 0
            ? `preview · ${l.omitted_memories} more in the full graph`
            : 'preview'}
        </span>
        <span>open knowledge graph →</span>
      </Link>
    </section>
  )
}
