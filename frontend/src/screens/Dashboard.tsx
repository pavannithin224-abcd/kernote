import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Finding, type Freshness, type Proposal } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Bar, Button, Dot, Empty, ErrorNote, Neon, PanelTitle } from '../components/ui'
import MemoryPulse from '../components/MemoryPulse'

/* ── small helpers ─────────────────────────────────────────────────────── */

const card = 'rounded-md border'
const cardStyle = { borderColor: 'var(--border)', background: 'var(--panel)' } as const

/** "2m ago". Deliberately coarse: a precise age implies a precision we do not have. */
function bytes(n: number | undefined): string {
  if (n === undefined) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

function ago(iso: string | null | undefined): string {
  if (!iso) return '—'
  const then = Date.parse(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  if (Number.isNaN(then)) return '—'
  const s = Math.max(0, (Date.now() - then) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function clock(iso: string | null | undefined): string {
  if (!iso) return '--:--'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return Number.isNaN(d.getTime())
    ? '--:--'
    : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** The most recent write across a project's memories. */
function latestWrite(memories: { updated_at: string }[] | undefined): string | undefined {
  if (!memories?.length) return undefined
  return memories.reduce((a, m) => (m.updated_at > a ? m.updated_at : a), memories[0].updated_at)
}

/** What the queue calls each kind of finding, and what you do about it. */
const QUEUE_KIND: Record<string, { label: string; tone: 'stale' | 'rel' | 'warn'; action: string }> = {
  stale_risk: { label: 'OUTDATED', tone: 'stale', action: 'Review' },
  conflict: { label: 'CONFLICT', tone: 'rel', action: 'Resolve' },
  duplicate: { label: 'DUPLICATE', tone: 'rel', action: 'Merge' },
  missing_source: { label: 'MISSING', tone: 'warn', action: 'Review' },
}

/* ── panels ────────────────────────────────────────────────────────────── */

function IntelligenceQueue({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const [acting, setActing] = useState<string | null>(null)

  const findings = useQuery({
    queryKey: ['findings', projectId],
    queryFn: () => api.findings(projectId),
  })
  const proposals = useQuery({
    queryKey: ['proposals', projectId],
    queryFn: () => api.proposals(projectId),
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['findings', projectId] })
    qc.invalidateQueries({ queryKey: ['proposals', projectId] })
    qc.invalidateQueries({ queryKey: ['project', projectId] })
  }
  const resolve = useMutation({
    mutationFn: (id: string) => api.resolveFinding(projectId, id, 'resolved'),
    onSettled: () => { setActing(null); refresh() },
  })
  const merge = useMutation({
    mutationFn: (id: string) => api.approveProposal(projectId, id),
    onSettled: () => { setActing(null); refresh() },
  })

  const items = findings.data ?? []
  const byKind = items.reduce<Record<string, number>>((acc, f) => {
    acc[f.kind] = (acc[f.kind] ?? 0) + 1
    return acc
  }, {})
  const proposalFor = (f: Finding): Proposal | undefined =>
    (proposals.data ?? []).find((p) => p.finding_id === f.id)

  // Each count carries the hue of the thing it counts, so the header reads as
  // a legend for the rows beneath it rather than as decoration.
  const summary = Object.entries(byKind).map(([k, n]) => ({
    key: k,
    n,
    label: (QUEUE_KIND[k]?.label ?? k).toLowerCase(),
    tone: QUEUE_KIND[k]?.tone ?? ('warn' as const),
  }))

  return (
    <section className={card} style={cardStyle}>
      <div className="px-3.5 pt-3 pb-1 border-l-2" style={{ borderColor: 'var(--accent)' }}>
        <PanelTitle
          right={
            findings.isLoading ? (
              'loading…'
            ) : summary.length ? (
              <span className="mono">
                [{' '}
                {summary.map((c, i) => (
                  <span key={c.key}>
                    {i > 0 && <span style={{ color: 'var(--muted)' }}> · </span>}
                    <Neon tone={c.tone}>
                      {c.n} {c.label}
                    </Neon>
                  </span>
                ))}{' '}
                ]
              </span>
            ) : undefined
          }
        >
          Intelligence Queue{' '}
          <span style={{ color: 'var(--muted)' }}>
            {findings.isLoading ? '' : `${items.length} pending`}
          </span>
        </PanelTitle>
      </div>

      {findings.isError ? (
        <div className="px-3.5 pb-3"><ErrorNote error={findings.error} /></div>
      ) : findings.isLoading ? (
        <ul className="px-3.5 pb-3 space-y-2" aria-busy>
          {[0, 1, 2].map((i) => (
            <li key={i} className="h-11 rounded animate-pulse" style={{ background: 'var(--chip)' }} />
          ))}
        </ul>
      ) : items.length === 0 ? (
        <div className="px-3.5 pb-3">
          <Empty title="Nothing waiting" hint="Run an analysis after a scan to look for drift, conflicts and duplicates." />
        </div>
      ) : (
        <ul>
          {items.map((f) => {
            const kind = QUEUE_KIND[f.kind] ?? { label: f.kind.toUpperCase(), tone: 'warn' as const, action: 'Review' }
            const proposal = proposalFor(f)
            const busy = acting === f.id
            return (
              <li
                key={f.id}
                className="flex items-start gap-3 px-3.5 py-2.5 border-t"
                style={{ borderColor: 'var(--border)' }}
              >
                <Badge tone={kind.tone}>{kind.label}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] leading-snug" style={{ color: 'var(--text)' }}>
                    {f.explanation}
                  </div>
                  <div
                    className="mono mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]"
                    style={{ color: 'var(--muted)' }}
                  >
                    {/* The record ids are lit in the relationship hue: on a
                        conflict or duplicate they are the two things being
                        compared, which is the whole content of the row. */}
                    {f.memory_id && <Neon tone="rel">mem_{f.memory_id.slice(0, 4)}</Neon>}
                    {f.other_id && (
                      <span>
                        <span style={{ color: 'var(--rel)' }}>⇄</span>{' '}
                        <Neon tone="rel">mem_{f.other_id.slice(0, 4)}</Neon>
                      </span>
                    )}
                    <span>·</span>
                    <Neon tone={kind.tone}>{f.severity}</Neon>
                    <span>·</span>
                    <span>{ago(f.created_at)}</span>
                  </div>
                </div>
                <Button
                  className="shrink-0"
                  disabled={busy || resolve.isPending || merge.isPending}
                  onClick={() => {
                    setActing(f.id)
                    if (proposal) merge.mutate(proposal.id)
                    else resolve.mutate(f.id)
                  }}
                >
                  {busy ? '…' : proposal ? 'Merge' : kind.action}
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      {(resolve.isError || merge.isError) && (
        <div className="px-3.5 pb-3">
          <ErrorNote error={resolve.error ?? merge.error} />
        </div>
      )}
    </section>
  )
}

function FreshnessBar({ f }: { f: Freshness | undefined }) {
  // Three states, and the third is the point. `checked_at === null` means
  // nobody has looked: that is reported as unchecked, never as fresh. A
  // project whose memories cite no files has nothing to verify, which is also
  // not the same as being fresh.
  if (!f) return <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>…</span>

  if (f.checked_at === null) {
    return (
      <span className="mono inline-flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--muted)' }}>
        <Dot tone="muted" /> never checked
      </span>
    )
  }
  if (f.verifiable === 0) {
    return (
      <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
        nothing cited
      </span>
    )
  }

  const pct = Math.round((f.verified / f.verifiable) * 100)
  const tone = f.flagged === 0 ? 'ok' : 'stale'
  return (
    <span
      className="inline-flex items-center gap-2"
      title={`${f.verified} of ${f.verifiable} cited memories verified against the files on disk; checked ${ago(f.checked_at)}`}
    >
      <Bar pct={pct} tone={tone} />
      <span className="mono text-[11px] tabular-nums" style={{ color: `var(--${tone})` }}>
        {pct}%
      </span>
    </span>
  )
}

function LedgerRow({ id, name, onSelect, selected }: {
  id: string; name: string; onSelect: () => void; selected: boolean
}) {
  const detail = useQuery({ queryKey: ['project', id], queryFn: () => api.getProject(id) })
  const emb = useQuery({ queryKey: ['embeddings', id], queryFn: () => api.embeddingStatus(id) })
  const memories = useQuery({
    queryKey: ['memories', id, 'latest'],
    queryFn: () => api.listMemories(id),
  })

  const counts = detail.data?.counts
  const indexed = (emb.data?.indexed_memories ?? 0)
  const pending = Math.max(0, (counts?.memories ?? 0) - indexed)

  return (
    <tr
      onClick={onSelect}
      className="cursor-pointer border-t"
      style={{ borderColor: 'var(--border)', background: selected ? 'var(--accent-soft)' : undefined }}
    >
      <td className="px-3.5 py-2">
        <span className="mono block truncate text-[12px]">{name}</span>
      </td>
      <td className="mono px-2 py-2 text-[12px] tabular-nums text-right">
        {detail.isLoading ? '…' : (counts?.memories ?? 0)}
      </td>
      <td className="px-2 py-2 text-[11px]">
        {emb.isLoading ? (
          <span style={{ color: 'var(--muted)' }}>…</span>
        ) : !emb.data?.usable ? (
          <span style={{ color: 'var(--muted)' }}>semantic off</span>
        ) : pending === 0 ? (
          <span className="inline-flex items-center gap-1.5" style={{ color: 'var(--ok)' }}>
            <Dot tone="ok" /> indexed
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5" style={{ color: 'var(--warn)' }}>
            <Dot tone="warn" /> {pending} queued
          </span>
        )}
      </td>
      <td className="px-2 py-2">
        <FreshnessBar f={detail.isLoading ? undefined : detail.data?.freshness} />
      </td>
      <td className="mono px-3.5 py-2 text-[11px] text-right" style={{ color: 'var(--muted)' }}>
        {memories.isLoading ? '…' : ago(latestWrite(memories.data))}
      </td>
    </tr>
  )
}

function LedgerSummary({ ids }: { ids: string[] }) {
  // Same query keys as the rows below, so this shares their cache and issues
  // no extra requests.
  const details = useQueries({
    queries: ids.map((id) => ({ queryKey: ['project', id], queryFn: () => api.getProject(id) })),
  })
  const embs = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['embeddings', id],
      queryFn: () => api.embeddingStatus(id),
    })),
  })

  if (details.some((d) => d.isLoading)) {
    return <div className="h-5 w-64 animate-pulse rounded" style={{ background: 'var(--chip)' }} />
  }

  // Keep each project's two queries together by position in `ids`, which both
  // `useQueries` calls were built from. Filtering the two result arrays
  // independently and then indexing one by the other's position pairs a
  // project's embedding status with a *different* project's memory count the
  // moment any project is missing from either list -- semantic search off, or
  // a failed detail fetch. That produced an invented "pending index" figure,
  // which is exactly what ADR-0037 forbids.
  const rows = ids.map((id, i) => ({ id, detail: details[i]?.data, emb: embs[i]?.data }))
  const loaded = rows.flatMap((r) => (r.detail ? [{ ...r, detail: r.detail }] : []))
  const failed = ids.length - loaded.length
  const memories = loaded.reduce((n, r) => n + (r.detail.counts.memories ?? 0), 0)

  // Only projects that have actually been checked may contribute to a
  // freshness figure. Averaging an unchecked project in as 100% is the same
  // lie the per-project tile refuses to tell (ADR-0037), so unchecked
  // projects are excluded and counted out loud instead.
  const checked = loaded.filter((r) => r.detail.freshness.checked_at !== null)
  const verifiable = checked.reduce((n, r) => n + r.detail.freshness.verifiable, 0)
  const verified = checked.reduce((n, r) => n + r.detail.freshness.verified, 0)
  const unchecked = loaded.length - checked.length
  const pct = verifiable > 0 ? Math.round((verified / verifiable) * 100) : null

  // Pending index only means something where semantic search is switched on,
  // and each project is compared against its own counts.
  const usable = loaded.filter((r) => r.emb?.usable)
  const pending = usable.reduce(
    (n, r) => n + Math.max(0, (r.detail.counts.memories ?? 0) - (r.emb?.indexed_memories ?? 0)),
    0,
  )

  return (
    <div className="mono flex flex-wrap items-baseline gap-x-5 gap-y-1 px-3.5 pb-2.5 text-[11px]">
      <span>
        <span className="text-[15px] tabular-nums" style={{ color: 'var(--text)' }}>
          {memories.toLocaleString()}
        </span>{' '}
        <span style={{ color: 'var(--muted)' }}>memories</span>
      </span>

      <span>
        {pct === null ? (
          <span style={{ color: 'var(--muted)' }}>
            {loaded.length === 0 ? 'no projects' : 'freshness not checked'}
          </span>
        ) : (
          <>
            <span className="text-[15px] tabular-nums">
              <Neon tone={verified === verifiable ? 'ok' : 'stale'}>{pct}%</Neon>
            </span>{' '}
            <span style={{ color: 'var(--muted)' }}>fresh</span>
          </>
        )}
        {unchecked > 0 && (
          <span style={{ color: 'var(--muted)' }}>
            {' '}
            ({unchecked} unchecked)
          </span>
        )}
      </span>

      {failed > 0 && (
        <span style={{ color: 'var(--warn)' }}>
          {failed} project{failed === 1 ? '' : 's'} unreadable · totals incomplete
        </span>
      )}

      {usable.length > 0 && (
        <span>
          <span className="text-[15px] tabular-nums">
            {pending === 0 ? (
              <span style={{ color: 'var(--muted)' }}>0</span>
            ) : (
              <Neon tone="warn">{pending.toLocaleString()}</Neon>
            )}
          </span>{' '}
          <span style={{ color: 'var(--muted)' }}>pending index</span>
        </span>
      )}
    </div>
  )
}

function MemoryLedger() {
  const { projects, projectId, select } = useProject()
  const rows = projects.data ?? []

  return (
    <section className={card} style={cardStyle}>
      <div className="px-3.5 pt-3">
        <PanelTitle right={`${rows.length} project${rows.length === 1 ? '' : 's'}`}>
          Project Memory Ledger
        </PanelTitle>
      </div>
      {rows.length > 0 && <LedgerSummary ids={rows.map((p) => p.id)} />}
      {projects.isError ? (
        <div className="px-3.5 pb-3"><ErrorNote error={projects.error} /></div>
      ) : rows.length === 0 ? (
        <div className="px-3.5 pb-3">
          <Empty title="No projects registered" hint="Add a local folder to begin." />
        </div>
      ) : (
        <table className="w-full table-fixed">
          {/* table-fixed so a long project name truncates instead of widening
              the column and pushing the panel past its track at 1366px. */}
          <colgroup>
            <col />
            <col className="w-[84px]" />
            <col className="w-[124px]" />
            <col className="w-[116px]" />
            <col className="w-[104px]" />
          </colgroup>
          <thead>
            <tr className="mono text-[10px] uppercase tracking-[0.12em]" style={{ color: 'var(--muted)' }}>
              <th className="px-3.5 py-1.5 text-left font-normal">Project</th>
              <th className="px-2 py-1.5 text-right font-normal">Memories</th>
              <th className="px-2 py-1.5 text-left font-normal">Index</th>
              <th className="px-2 py-1.5 text-left font-normal">Freshness</th>
              <th className="px-3.5 py-1.5 text-right font-normal">Last write</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <LedgerRow
                key={p.id} id={p.id} name={p.name}
                selected={p.id === projectId} onSelect={() => select(p.id)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function LocalSystem({ projectId }: { projectId: string | null }) {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const emb = useQuery({
    queryKey: ['embeddings', projectId],
    queryFn: () => api.embeddingStatus(projectId!),
    enabled: !!projectId,
  })

  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>{label}</span>
      <span className="mono text-[11px] text-right min-w-0 truncate">{children}</span>
    </div>
  )

  return (
    <section className={card} style={cardStyle}>
      <div className="px-3.5 pt-3">
        <PanelTitle right="all services local">Local System</PanelTitle>
      </div>
      <div className="px-3.5 pb-3">
        {health.isError ? (
          <ErrorNote error={health.error} />
        ) : (
          <>
            <Row label="database">
              {health.isLoading ? '…' : (
                <span className="inline-flex items-center gap-2">
                  {health.data?.db_path.split(/[/\\]/).pop()} · schema v{health.data?.schema_version} ·{' '}
                  {bytes(health.data?.db_bytes)}
                  <Dot tone="ok" />
                </span>
              )}
            </Row>
            <Row label="embeddings">
              {!projectId ? <span style={{ color: 'var(--muted)' }}>no project</span>
                : emb.isLoading ? '…'
                : !emb.data?.usable ? (
                  <span className="inline-flex items-center gap-2" style={{ color: 'var(--muted)' }}>
                    off · opt-in <Dot tone="muted" />
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    {emb.data.model_id.split('/').pop()} · {emb.data.dim}d ·{' '}
                    {emb.data.indexed_memories + emb.data.indexed_chunks} vec
                    <Dot tone="ok" />
                  </span>
                )}
            </Row>
            <Row label="language model">
              <span style={{ color: 'var(--muted)' }}>none · extraction is deterministic</span>
            </Row>
            <Row label="network">
              <span className="inline-flex items-center gap-2" style={{ color: 'var(--ok)' }}>
                offline by default <Dot tone="ok" />
              </span>
            </Row>
          </>
        )}
      </div>
    </section>
  )
}

function RecentActivity({ projectId }: { projectId: string }) {
  // Derived from what the vault actually records: memories by `updated_at`,
  // findings and proposals by `created_at`. There is no activity log, so this
  // is the real history rather than a feed invented for the panel.
  const [memories, findings, proposals] = useQueries({
    queries: [
      { queryKey: ['memories', projectId, 'recent'], queryFn: () => api.listMemories(projectId) },
      { queryKey: ['findings', projectId], queryFn: () => api.findings(projectId) },
      { queryKey: ['proposals', projectId], queryFn: () => api.proposals(projectId) },
    ],
  })

  const loading = memories.isLoading || findings.isLoading || proposals.isLoading
  const events = [
    ...(memories.data ?? []).map((m) => ({
      at: m.updated_at, glyph: m.created_at === m.updated_at ? '+' : '~',
      text: `${m.created_at === m.updated_at ? 'Captured' : 'Updated'} “${m.title}”`,
      tone: 'ok' as const,
    })),
    ...(findings.data ?? []).map((f) => ({
      at: f.created_at, glyph: f.kind === 'duplicate' ? '⧉' : '⇄',
      text: `${(QUEUE_KIND[f.kind]?.label ?? f.kind).toLowerCase()} detected`,
      tone: 'rel' as const,
    })),
    ...(proposals.data ?? []).map((p) => ({
      at: p.created_at, glyph: '✓', text: 'Consolidation proposed', tone: 'rel' as const,
    })),
  ]
    .filter((e) => e.at)
    .sort((a, b) => (a.at < b.at ? 1 : -1))
    .slice(0, 8)

  return (
    <section className={card} style={cardStyle}>
      <div className="px-3.5 pt-3">
        <PanelTitle right={events[0] ? ago(events[0].at) : undefined}>Recent Activity</PanelTitle>
      </div>
      <div className="px-3.5 pb-3">
        {loading ? (
          <ul className="space-y-1.5" aria-busy>
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="h-4 rounded animate-pulse" style={{ background: 'var(--chip)' }} />
            ))}
          </ul>
        ) : events.length === 0 ? (
          <Empty title="Nothing yet" hint="Scan a project to start building its history." />
        ) : (
          <ul className="space-y-1.5">
            {events.map((e, i) => (
              <li key={i} className="flex items-baseline gap-2.5 text-[12px]">
                <span className="mono tabular-nums text-[11px]" style={{ color: 'var(--accent)' }}>
                  {clock(e.at)}
                </span>
                <span className="mono text-[11px]" style={{ color: `var(--${e.tone})` }}>{e.glyph}</span>
                <span className="min-w-0 flex-1 truncate">{e.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

/* ── the screen ────────────────────────────────────────────────────────── */

export default function Dashboard() {
  const { projects, projectId } = useProject()

  if (projects.isError) return <ErrorNote error={projects.error} />
  if (!projectId) {
    return (
      <div className="space-y-4">
        <MemoryLedger />
        <div className={card} style={cardStyle}>
          <div className="px-3.5 py-6">
            <Empty
              title="No project selected"
              hint="Register a local folder from the Memory Explorer, or pick one above."
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_clamp(260px,24vw,340px)] items-start">
      <h1 className="sr-only">Overview</h1>
      <div className="min-w-0 space-y-3">
        <IntelligenceQueue projectId={projectId} />
        <MemoryLedger />
      </div>
      <div className="min-w-0 space-y-3">
        <MemoryPulse projectId={projectId} />
        <LocalSystem projectId={projectId} />
        <RecentActivity projectId={projectId} />
        <div className="mono text-[11px] px-1" style={{ color: 'var(--muted)' }}>
          <Link to="/maintenance" className="hover:underline">open the review queue →</Link>
        </div>
      </div>
    </div>
  )
}
