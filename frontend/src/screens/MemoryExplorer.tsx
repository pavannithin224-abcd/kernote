import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { TYPE_LABEL, api, citationOf, type MemoryType } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Citation, Empty, ErrorNote, Panel } from '../components/ui'

const TYPES: MemoryType[] = [
  'project_fact', 'architecture', 'decision', 'procedure',
  'convention', 'gotcha', 'current_state',
]

export default function MemoryExplorer() {
  const qc = useQueryClient()
  const { projectId } = useProject()
  const [type, setType] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [q, setQ] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)

  const memories = useQuery({
    queryKey: ['memories', projectId, type, status],
    queryFn: () => api.listMemories(projectId!, type || undefined, status || undefined),
    enabled: !!projectId,
  })
  const detail = useQuery({
    queryKey: ['memory', openId],
    queryFn: () => api.getMemory(openId!),
    enabled: !!openId,
  })
  const archive = useMutation({
    mutationFn: (id: string) => api.archiveMemory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memories'] })
      qc.invalidateQueries({ queryKey: ['memory', openId] })
    },
  })

  const rows = (memories.data ?? []).filter(
    (m) => !q || (m.title + m.content).toLowerCase().includes(q.toLowerCase()),
  )

  if (!projectId) {
    return <Empty title="No project selected" hint="Register one on the Dashboard first." />
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Memory Explorer</h1>
        <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
          Every record shows where it came from and why it ranks where it does.
        </p>
      </header>

      <div className="flex flex-col sm:flex-row gap-2">
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by text…"
          className="flex-1 rounded-md border px-2 py-1.5 text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)', color: 'var(--text)' }}
        />
        <select
          value={type} onChange={(e) => setType(e.target.value)}
          className="rounded-md border px-2 py-1.5 text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)', color: 'var(--text)' }}
        >
          <option value="">All types</option>
          {TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
        </select>
        <select
          value={status} onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border px-2 py-1.5 text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)', color: 'var(--text)' }}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="needs_review">Needs review</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {memories.isError && <ErrorNote error={memories.error} />}

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title={`Memories (${rows.length})`}>
          {rows.length === 0 ? (
            <Empty title="Nothing matches" hint="Clear the filters, or run a scan on the Dashboard." />
          ) : (
            <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {rows.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => setOpenId(m.id)}
                    className="w-full text-left py-2.5 px-1 rounded"
                    style={{ background: openId === m.id ? 'var(--accent-soft)' : 'transparent' }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[13px] font-medium">{m.title}</span>
                      <span className="mono text-[11px] tabular-nums shrink-0" style={{ color: 'var(--muted)' }}>
                        {m.importance.toFixed(2)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <Badge tone="accent">{TYPE_LABEL[m.type]}</Badge>
                      {m.status !== 'active' && <Badge tone="warn">{m.status.replace('_', ' ')}</Badge>}
                      {m.source_refs[0] && <Citation>{citationOf(m.source_refs[0])}</Citation>}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="space-y-4">
          {!openId ? (
            <Panel title="Evidence"><Empty title="Select a memory" hint="Its sources, scores and history appear here." /></Panel>
          ) : detail.isError ? (
            <ErrorNote error={detail.error} />
          ) : detail.data ? (
            <>
              <Panel
                title={detail.data.memory.title}
                right={
                  <button
                    onClick={() => archive.mutate(detail.data!.memory.id)}
                    disabled={archive.isPending || detail.data.memory.status === 'archived'}
                    className="rounded border px-2 py-0.5 text-[11px] disabled:opacity-40"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    {detail.data.memory.status === 'archived' ? 'Archived' : 'Archive'}
                  </button>
                }
              >
                <pre
                  className="mono whitespace-pre-wrap text-[12px] leading-relaxed max-h-56 overflow-auto"
                  style={{ color: 'var(--text)' }}
                >
                  {detail.data.memory.content}
                </pre>
              </Panel>

              <Panel title="Provenance">
                {detail.data.memory.source_refs.map((r, i) => (
                  <div key={i} className="mb-2 space-y-1 text-[12px]">
                    <Citation>{citationOf(r)}</Citation>
                    {r.content_hash && (
                      <div className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
                        content sha256 {r.content_hash.slice(0, 16)}…
                      </div>
                    )}
                    <div className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
                      git blob {r.git_blob_hash ? r.git_blob_hash.slice(0, 12) + '…' : 'none (untracked)'}
                    </div>
                    {r.user_note && <div style={{ color: 'var(--muted)' }}>{r.user_note}</div>}
                  </div>
                ))}
                <div className="mt-2 pt-2 border-t text-[11px] space-y-1" style={{ borderColor: 'var(--border)' }}>
                  <div>
                    <span style={{ color: 'var(--muted)' }}>extracted by </span>
                    <span className="mono">{detail.data.memory.extraction_method}</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)' }}>claim is </span>
                    <Badge tone={detail.data.memory.claim_kind === 'source_fact' ? 'ok' : 'warn'}>
                      {detail.data.memory.claim_kind === 'source_fact' ? 'source fact' : 'interpretation'}
                    </Badge>
                  </div>
                </div>
              </Panel>

              <Panel title="Why these scores">
                <div className="space-y-2 text-[12px]">
                  <div>
                    <div className="font-medium">Importance {detail.data.memory.importance.toFixed(2)}</div>
                    <div style={{ color: 'var(--muted)' }}>{detail.data.memory.importance_reason}</div>
                  </div>
                  <div>
                    <div className="font-medium">Confidence {detail.data.memory.confidence.toFixed(2)}</div>
                    <div style={{ color: 'var(--muted)' }}>{detail.data.memory.confidence_reason}</div>
                  </div>
                </div>
              </Panel>

              <Panel title={`History (${detail.data.revisions.length})`}>
                <ol className="space-y-1.5 text-[12px]">
                  {detail.data.revisions.map((r) => (
                    <li key={r.id} className="flex items-start gap-2">
                      <Badge>{r.actor}</Badge>
                      <div className="min-w-0">
                        <div>{r.change_reason}</div>
                        <div className="mono text-[11px]" style={{ color: 'var(--muted)' }}>{r.created_at}</div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Panel>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
