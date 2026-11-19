import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, ScreenHeader, Stat, NoProject } from '../components/ui'

export default function ChangeImpact() {
  const { projectId } = useProject()
  const [base, setBase] = useState('HEAD~1')
  const [head, setHead] = useState('HEAD')
  const [range, setRange] = useState<{ base: string; head: string } | null>({
    base: 'HEAD~1',
    head: 'HEAD',
  })

  const commits = useQuery({
    queryKey: ['commits', projectId],
    queryFn: () => api.commits(projectId!),
    enabled: !!projectId,
  })

  const report = useQuery({
    queryKey: ['impact', projectId, range?.base, range?.head],
    queryFn: () => api.impact(projectId!, range!.base, range!.head),
    enabled: !!projectId && !!range,
  })

  if (!projectId) {
    return <NoProject />
  }

  const data = report.data
  const direct = data?.affected.filter((a) => a.overlap === 'direct') ?? []
  const nearby = data?.affected.filter((a) => a.overlap === 'same_file') ?? []

  return (
    <div className="space-y-4">
      <ScreenHeader title="Change Impact">
        Which memories a commit range may have invalidated. A memory is{' '}
        <strong>directly affected</strong> only when the changed lines overlap the
        lines it cites — not merely because its file appears in the diff.
      </ScreenHeader>

      <Panel title="Commit range">
        <form
          className="flex flex-col sm:flex-row gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            setRange({ base: base.trim() || 'HEAD~1', head: head.trim() || 'HEAD' })
          }}
        >
          <input
            aria-label="Base git ref"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="base ref"
            className="mono rounded-md border px-2 py-1.5 text-[13px] sm:w-44"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
          <input
            aria-label="Head git ref"
            value={head}
            onChange={(e) => setHead(e.target.value)}
            placeholder="head ref"
            className="mono rounded-md border px-2 py-1.5 text-[13px] sm:w-44"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
          <Button primary type="submit">
            Analyse
          </Button>
        </form>

        {(commits.data ?? []).length > 0 && (
          <div className="mt-3 space-y-1">
            <div className="text-[11px]" style={{ color: 'var(--muted)' }}>
              Recent commits — click to use as the base
            </div>
            {commits.data!.slice(0, 6).map((c) => (
              <button
                key={c.sha}
                onClick={() => {
                  setBase(c.sha)
                  setRange({ base: c.sha, head: head.trim() || 'HEAD' })
                }}
                className="block w-full text-left text-[12px] hover:underline"
              >
                <span className="mono" style={{ color: 'var(--chip-text)' }}>{c.sha}</span>{' '}
                <span style={{ color: 'var(--muted)' }}>{c.date}</span> {c.subject.slice(0, 68)}
              </button>
            ))}
          </div>
        )}
      </Panel>

      {report.isError && <ErrorNote error={report.error} />}

      {data && !data.resolved && (
        <Panel title="Could not analyse that range">
          <p className="text-[12px]">{data.note}</p>
        </Panel>
      )}

      {data?.resolved && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Stat label="Files changed" value={data.changed_files.length} />
            <Stat
              label="Directly affected"
              value={direct.length}
              hint="cited lines moved"
            />
            <Stat
              label="Same file only"
              value={nearby.length}
              hint="likely unaffected"
            />
            <Stat label="Files with memories" value={data.files_with_memories.length} />
          </div>

          {data.note && (
            <p className="text-[12px]" style={{ color: 'var(--muted)' }}>{data.note}</p>
          )}

          {direct.length > 0 ? (
            <Panel title={`Review these (${direct.length})`}>
              <ul className="space-y-2.5">
                {direct.map((a) => (
                  <li key={`${a.memory_id}-${a.rel_path}`} className="space-y-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone="warn">{a.memory_type.replace('_', ' ')}</Badge>
                      <span className="text-[13px] font-medium">{a.title}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Citation>{a.citation}</Citation>
                      <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
                        changed {a.changed_lines.map((l) => `${l[0]}-${l[1]}`).join(', ')}
                      </span>
                    </div>
                    <div className="text-[12px]" style={{ color: 'var(--muted)' }}>{a.reason}</div>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : (
            <Panel title="Nothing directly affected">
              <Empty
                title="No cited lines moved in this range"
                hint={
                  nearby.length > 0
                    ? `${nearby.length} memories live in the changed files but their cited lines did not move.`
                    : 'No memory references any file in this range.'
                }
              />
            </Panel>
          )}

          {nearby.length > 0 && (
            <Panel title={`Same file, cited lines unchanged (${nearby.length})`}>
              <ul className="space-y-1">
                {nearby.slice(0, 20).map((a) => (
                  <li key={`${a.memory_id}-${a.rel_path}`} className="flex flex-wrap items-center gap-1.5 text-[12px]">
                    <Citation>{a.citation}</Citation>
                    <span className="truncate">{a.title}</span>
                  </li>
                ))}
                {nearby.length > 20 && (
                  <li className="text-[11px]" style={{ color: 'var(--muted)' }}>
                    …and {nearby.length - 20} more
                  </li>
                )}
              </ul>
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
