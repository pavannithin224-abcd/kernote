/**
 * The Knowledge Graph — the project's real relationships, at full size.
 *
 * Everything drawn here is a row in the database. An edge is an explicit
 * link, a finding naming two memories, or a shared entity rare enough to mean
 * something (ADR-0039); it carries the reason it exists, and selecting a node
 * shows that reason for each of its neighbours. Nothing is inferred to make
 * the picture fuller, and what the server left out is stated at the bottom
 * rather than quietly absent.
 *
 * Rendered with React Flow, adopted after a side-by-side comparison against
 * an SVG implementation; the reasoning and the measured cost are in ADR-0039.
 * React Flow does **not** lay out graphs — it takes
 * positions — so `lib/graphLayout.ts` is still ours and still does the work.
 * What the library provides is dragging, pan/zoom with inertia, the minimap,
 * and `NodeToolbar`, which keeps the popup glued to its node through both.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  NodeToolbar,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, type GraphEdge, type GraphNode } from '../lib/api'
import { layout } from '../lib/graphLayout'
import { useProject } from '../lib/useProject'
import { Badge, Empty, ErrorNote, PanelTitle } from '../components/ui'

/** The layout space. Larger than the viewport on purpose: React Flow's
 *  `fitView` scales it down, and a roomy space keeps dots from overlapping at
 *  the zoom levels people actually use. */
const SPACE_W = 1600
const SPACE_H = 1000

type DotData = {
  label: string
  type: string
  status: string
  degree: number
  importance: number | null
  flagged: boolean
  delay: number
}

/** One hue, one meaning — the same legend as everywhere else in the app. */
function hueOf(d: { flagged: boolean; status: string }): string {
  if (d.flagged) return 'var(--rel)'
  if (d.status === 'needs_review') return 'var(--warn)'
  return 'var(--ok)'
}

function MemoryDot({ data, selected }: NodeProps) {
  const d = data as DotData
  const neon = hueOf(d)
  // Degree drives size, so the shape of the network is readable before
  // anything is clicked.
  const size = d.flagged ? 11 : 7 + Math.min(5, d.degree * 0.4)

  return (
    <div
      className={`rf-dot-wrap${selected ? ' rf-selected' : ''}`}
      style={{ ['--neon' as string]: neon }}
    >
      <NodeToolbar isVisible={selected} position={Position.Top} offset={18}>
        <div className="rf-popup mono text-[11px] leading-[1.45]" style={{ ['--neon' as string]: neon }}>
          <div className="mb-1 font-semibold break-words" style={{ color: 'var(--text)' }}>
            {d.label}
          </div>
          <div className="flex gap-1.5" style={{ color: 'var(--muted)' }}>
            <span style={{ color: neon }}>{d.type}</span>
            <span>{d.status.replace('_', ' ')}</span>
          </div>
          <div className="flex gap-1.5" style={{ color: 'var(--muted)' }}>
            <span>{d.degree} connection{d.degree === 1 ? '' : 's'}</span>
            {d.importance != null && <span>· importance {d.importance.toFixed(2)}</span>}
          </div>
          {d.flagged && (
            <div className="mt-1" style={{ color: 'var(--rel)' }}>named by a finding</div>
          )}
        </div>
      </NodeToolbar>

      {/* The circling loop, on the selected record only. */}
      {selected && (
        <>
          <span className="rf-orbit" />
          <span className="rf-orbit-particle" />
        </>
      )}

      {/* React Flow attaches edges to handles, not to the node box: a custom
          node without them logs error #008 and the edge is silently dropped.
          Both sit invisible at the centre of the dot. */}
      <Handle type="target" position={Position.Top} isConnectable={false} className="!opacity-0 !w-px !h-px !min-w-0 !min-h-0 !border-0 !top-1/2 !left-1/2" />
      <Handle type="source" position={Position.Bottom} isConnectable={false} className="!opacity-0 !w-px !h-px !min-w-0 !min-h-0 !border-0 !top-1/2 !left-1/2" />

      <div
        className="rf-dot rf-breathe"
        style={{ ['--size' as string]: `${size}px`, ['--d' as string]: `${d.delay}ms` }}
      />
    </div>
  )
}

const nodeTypes = { memory: MemoryDot }

export default function KnowledgeGraph() {
  const { projectId } = useProject()
  const navigate = useNavigate()
  const [selected, setSelected] = useState<string | null>(null)

  const graph = useQuery({
    queryKey: ['graph', projectId],
    queryFn: () => api.graph(projectId!),
    enabled: !!projectId,
  })

  const built = useMemo(() => {
    if (!graph.data) return { nodes: [] as Node[], edges: [] as Edge[] }
    const pos = layout(graph.data.nodes, graph.data.edges, SPACE_W, SPACE_H)
    return {
      nodes: graph.data.nodes.map<Node>((n: GraphNode) => {
        const p = pos.get(n.id)!
        return {
          id: n.id,
          type: 'memory',
          position: { x: p.x, y: p.y },
          data: {
            label: n.title,
            type: n.type,
            status: n.status,
            degree: n.degree,
            importance: n.importance,
            flagged: n.flagged,
            delay: Math.round((p.x + p.y) % 2400),
          } satisfies DotData,
        }
      }),
      edges: graph.data.edges.map<Edge>((e, i) => ({
        id: `e${i}`,
        source: e.src,
        target: e.dst,
        style: {
          stroke: e.kind === 'shares' ? 'var(--accent)' : 'var(--rel)',
          strokeWidth: e.kind === 'shares' ? 0.6 : 1.8,
          opacity: e.kind === 'shares' ? 0.28 + e.weight * 0.35 : 0.9,
        },
        animated: e.kind !== 'shares',
      })),
    }
  }, [graph.data])

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  useEffect(() => {
    setNodes(built.nodes)
    setEdges(built.edges)
  }, [built, setNodes, setEdges])

  const detail = useQuery({
    queryKey: ['memory', selected],
    queryFn: () => api.getMemory(selected!),
    enabled: !!selected,
  })

  // Turning a suggestion into a judgement, or saying it is wrong. Both
  // invalidate the graph, because both change what it should draw.
  const qc = useQueryClient()
  const curate = useMutation({
    // Returns void so the three differently-shaped responses do not have to
    // be unified into one type nobody reads.
    mutationFn: async ({
      other,
      verb,
    }: {
      other: string
      verb: 'confirm' | 'dismiss' | 'remove'
    }): Promise<void> => {
      if (verb === 'confirm') await api.confirmLink(projectId!, selected!, other)
      else if (verb === 'dismiss') await api.dismissLink(projectId!, selected!, other)
      else await api.removeLink(projectId!, selected!, other)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['graph', projectId] }),
  })

  const allEdges = graph.data?.edges
  const neighbours = useMemo(() => {
    if (!selected || !allEdges) return []
    const out: { id: string; e: GraphEdge }[] = []
    for (const e of allEdges) {
      if (e.src === selected) out.push({ id: e.dst, e })
      else if (e.dst === selected) out.push({ id: e.src, e })
    }
    return out
  }, [selected, allEdges])

  const titleOf = useCallback(
    (id: string) => graph.data?.nodes.find((n) => n.id === id)?.title ?? id,
    [graph.data],
  )

  if (!projectId) {
    return <Empty title="No project selected" hint="Choose a project to see its network." />
  }
  if (graph.isError) return <ErrorNote error={graph.error} />
  if (graph.isLoading || !graph.data) {
    return (
      <div
        className="animate-pulse rounded border"
        style={{ height: 560, background: 'var(--chip)', borderColor: 'var(--border)' }}
        aria-busy
      />
    )
  }

  const { nodes: raw, edges: rawEdges, totals, limits } = graph.data
  if (raw.length === 0) {
    return <Empty title="No memories yet" hint="Scan this project to build its memory." />
  }
  if (rawEdges.length === 0) {
    return (
      <Empty
        title="No relationships recorded yet"
        hint={
          `${totals.memories} memories, none of them linked. Relationships appear when an ` +
          `analysis finds a conflict or duplicate, when a memory supersedes another, or when ` +
          `two memories cite the same specific file. Nothing is drawn that the database does not hold.`
        }
      />
    )
  }

  const node = raw.find((n) => n.id === selected)

  return (
    <div className="space-y-3">
      {/* Every screen needs one. Visually it is the panel title; this is the
          document structure a screen reader navigates by. */}
      <h1 className="sr-only">Knowledge Graph</h1>
      <div
        className="rounded border overflow-hidden"
        style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
      >
        <div className="px-3.5 pt-3">
          <PanelTitle
            right={
              <span className="mono">
                {raw.length} nodes · {rawEdges.length} edges · click a dot
              </span>
            }
          >
            Knowledge Graph
          </PanelTitle>
        </div>

        <div className="rf-canvas" style={{ height: 'min(64vh, 620px)' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, n) => setSelected(n.id)}
            onPaneClick={() => setSelected(null)}
            fitView
            minZoom={0.08}
            proOptions={{ hideAttribution: false }}
          >
            <Background color="var(--grid)" gap={32} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => hueOf(n.data as DotData)}
              maskColor="color-mix(in srgb, var(--bg) 80%, transparent)"
            />
          </ReactFlow>
        </div>

        {/* What is not on screen, said out loud (ADR-0039). */}
        <div
          className="mono border-t px-3.5 py-2 text-[11px]"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          showing {raw.length} of {totals.memories} memories
          {limits.omitted_memories > 0 && ` · ${limits.omitted_memories} not shown`}
          {limits.omitted_edges > 0 && ` · ${limits.omitted_edges} edges beyond the cap`}
          {limits.entities_too_common > 0 &&
            ` · ${limits.entities_too_common} entities too common to be a link`}
        </div>
      </div>

      <div
        className="rounded border px-3.5 py-3"
        style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
      >
        {!selected || !node ? (
          <p className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
            Select a memory to inspect it. Drag to rearrange, scroll to zoom.
          </p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <Badge tone={node.flagged ? 'rel' : 'neutral'}>{node.type}</Badge>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] leading-snug" style={{ color: 'var(--text)' }}>
                  {node.title}
                </div>
                <div className="mono mt-0.5 text-[11px]" style={{ color: 'var(--muted)' }}>
                  {node.status.replace('_', ' ')} · {node.degree} connection
                  {node.degree === 1 ? '' : 's'}
                  {node.importance != null && ` · importance ${node.importance.toFixed(2)}`}
                </div>

                {detail.isLoading ? (
                  <div className="mono mt-1 text-[11px]" style={{ color: 'var(--muted)' }}>
                    loading the record…
                  </div>
                ) : detail.isError ? (
                  <div className="mt-1"><ErrorNote error={detail.error} /></div>
                ) : (
                  <>
                    <p className="mt-1 text-[12px]" style={{ color: 'var(--muted)' }}>
                      {detail.data?.memory.content.slice(0, 320)}
                      {(detail.data?.memory.content.length ?? 0) > 320 ? '…' : ''}
                    </p>
                    {detail.data?.citations?.length ? (
                      <p className="mono mt-1 text-[11px]" style={{ color: 'var(--muted)' }}>
                        cites {detail.data.citations.slice(0, 3).join(', ')}
                      </p>
                    ) : null}
                  </>
                )}
              </div>
              <button
                className="mono shrink-0 rounded border px-2 py-1 text-[11px]"
                style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                onClick={() => navigate(`/explorer?memory=${selected}`)}
              >
                open record →
              </button>
            </div>

            <div>
              <div
                className="mono mb-1 text-[10px] uppercase tracking-[0.12em]"
                style={{ color: 'var(--muted)' }}
              >
                {neighbours.length} connection{neighbours.length === 1 ? '' : 's'}
              </div>
              <ul className="space-y-1">
                {neighbours.slice(0, 8).map(({ id, e }) => (
                  <li key={id + e.kind} className="flex items-baseline gap-2 text-[12px]">
                    <Badge tone={e.origin === 'suggested' ? 'neutral' : 'rel'}>{e.kind}</Badge>
                    <button
                      className="min-w-0 flex-1 truncate text-left"
                      style={{ color: 'var(--text)' }}
                      onClick={() => setSelected(id)}
                    >
                      {titleOf(id)}
                    </button>
                    <span className="mono shrink-0 text-[10px]" style={{ color: 'var(--muted)' }}>
                      {e.reason.slice(0, 40)}
                    </span>

                    {/* A suggestion is a heuristic until somebody answers it.
                        A confirmed link can be withdrawn; one a merge wrote
                        cannot, and is undone by undoing the merge. */}
                    {e.origin === 'suggested' && (
                      <span className="flex shrink-0 gap-1">
                        <button
                          className="mono rounded border px-1.5 text-[10px]"
                          style={{ borderColor: 'var(--rel)', color: 'var(--rel)' }}
                          disabled={curate.isPending}
                          onClick={() => curate.mutate({ other: id, verb: 'confirm' })}
                        >
                          confirm
                        </button>
                        <button
                          className="mono rounded border px-1.5 text-[10px]"
                          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                          disabled={curate.isPending}
                          onClick={() => curate.mutate({ other: id, verb: 'dismiss' })}
                        >
                          dismiss
                        </button>
                      </span>
                    )}
                    {e.origin === 'user' && (
                      <button
                        className="mono shrink-0 rounded border px-1.5 text-[10px]"
                        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                        disabled={curate.isPending}
                        onClick={() => curate.mutate({ other: id, verb: 'remove' })}
                      >
                        withdraw
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
