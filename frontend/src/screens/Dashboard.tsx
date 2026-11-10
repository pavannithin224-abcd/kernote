import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type ScanResult } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, Stat } from '../components/ui'

const REASON_TEXT: Record<string, string> = {
  secret_suspected: 'refused as possible secret — never read',
  gitignored: 'excluded by .gitignore',
  not_allowlisted: 'file type not in the Stage 2 allowlist',
  binary: 'binary content',
  too_large: 'over the size cap',
  excluded: 'excluded (symlink or exclude list)',
  unreadable: 'could not be read',
}

export default function Dashboard() {
  const qc = useQueryClient()
  const { projects, projectId, select } = useProject()
  const [name, setName] = useState('')
  const [path, setPath] = useState('')
  const [scan, setScan] = useState<ScanResult | null>(null)

  const detail = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: !!projectId,
  })
  const memories = useQuery({
    queryKey: ['memories', projectId],
    queryFn: () => api.listMemories(projectId!),
    enabled: !!projectId,
  })

  const register = useMutation({
    mutationFn: () => api.registerProject(name.trim(), path.trim()),
    onSuccess: (p) => {
      setName(''); setPath(''); select(p.id)
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
  const runScan = useMutation({
    mutationFn: () => api.scan(projectId!),
    onSuccess: (r) => {
      setScan(r)
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      qc.invalidateQueries({ queryKey: ['memories', projectId] })
    },
  })

  const hasProjects = (projects.data?.length ?? 0) > 0
  const counts = detail.data?.counts
  const recent = (memories.data ?? []).slice(0, 6)

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Dashboard</h1>
        <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
          Scanning is read-only. Nothing is written to your project.
        </p>
      </header>

      {projects.isError && <ErrorNote error={projects.error} />}

      {counts && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Stat label="Memories" value={counts.memories} hint="active, not archived" />
          <Stat
            label="Needs review"
            value={counts.open_findings ?? 0}
            hint={counts.open_findings ? 'open findings — go and look' : 'nothing waiting'}
            tone={counts.open_findings ? 'warn' : 'neutral'}
            to="/maintenance"
          />
          <Stat label="Source files" value={counts.source_files} hint="current revision" />
          <Stat label="Captures" value={counts.captures} hint="content-addressed" />
        </div>
      )}

      <Panel
        title="Project"
        right={
          projectId && (
            <Button primary onClick={() => runScan.mutate()} disabled={runScan.isPending}>
              {runScan.isPending ? 'Scanning…' : 'Scan now'}
            </Button>
          )
        }
      >
        {projects.data && projects.data.length > 0 ? (
          <div className="space-y-2">
            <select
              value={projectId ?? ''}
              onChange={(e) => { select(e.target.value); setScan(null) }}
              className="w-full rounded-md border px-2 py-1.5 text-[13px]"
              style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
            >
              {projects.data.map((p) => (
                <option key={p.id} value={p.id}>{p.name} — {p.root_path}</option>
              ))}
            </select>
            {detail.data && (
              <div className="flex flex-wrap items-center gap-2 text-[12px]" style={{ color: 'var(--muted)' }}>
                <span className="mono">{detail.data.project.root_path}</span>
                {detail.data.project.is_git_repo
                  ? <Badge tone="ok">git repo</Badge>
                  : <Badge tone="warn">not a git repo — drift limited to file hashes</Badge>}
                <span>
                  {counts?.scans ?? 0} scan{counts?.scans === 1 ? '' : 's'}
                </span>
              </div>
            )}
          </div>
        ) : (
          <Empty title="No project registered yet" hint="Add a local folder below to begin." />
        )}
      </Panel>

      {!hasProjects && (
        <Panel title="Register a local project">
                <form
                  className="flex flex-col sm:flex-row gap-2"
                  onSubmit={(e) => { e.preventDefault(); register.mutate() }}
                >
                  <input
                    value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="Name" required
                    className="rounded-md border px-2 py-1.5 text-[13px] sm:w-44"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
                  />
                  <input
                    value={path} onChange={(e) => setPath(e.target.value)}
                    placeholder="/absolute/path/to/repo" required
                    className="mono flex-1 rounded-md border px-2 py-1.5 text-[13px]"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
                  />
                  <button
                    type="submit" disabled={register.isPending}
                    className="rounded-md border px-3 py-1.5 text-[12px] font-medium disabled:opacity-50"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    {register.isPending ? 'Adding…' : 'Add project'}
                  </button>
                </form>
                {register.isError && <div className="mt-2"><ErrorNote error={register.error} /></div>}
        </Panel>
      )}

      {runScan.isError && <ErrorNote error={runScan.error} />}

      {scan && (
        <Panel title="Last scan">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
            <Stat label="Files read" value={scan.files_seen} />
            <Stat label="New captures" value={scan.captures_created} hint="0 means nothing changed" />
            <Stat label="New memories" value={scan.memories_created} />
            <Stat label="Skipped" value={scan.files_skipped} hint="each with a reason" />
          </div>
          {scan.skipped.length > 0 && (
            <div className="space-y-1">
              <div className="text-[12px] font-medium">Why files were not imported</div>
              {scan.skipped.slice(0, 12).map((s) => (
                <div key={s.rel_path} className="flex items-center gap-2 text-[12px]">
                  <span className="mono">{s.rel_path}</span>
                  <Badge tone={s.reason === 'secret_suspected' ? 'warn' : 'neutral'}>
                    {REASON_TEXT[s.reason] ?? s.reason}
                  </Badge>
                </div>
              ))}
              {scan.skipped.length > 12 && (
                <div className="text-[11px]" style={{ color: 'var(--muted)' }}>
                  …and {scan.skipped.length - 12} more
                </div>
              )}
            </div>
          )}
        </Panel>
      )}

      <Panel title="Recent memories">
        {memories.isError ? <ErrorNote error={memories.error} />
          : recent.length === 0
            ? <Empty title="No memories yet" hint="Run a scan to extract memories from your docs and config." />
            : (
              <ul className="space-y-2">
                {recent.map((m) => (
                  <li key={m.id} className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-[13px] font-medium">{m.title}</div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                        <Badge>{m.type.replace('_', ' ')}</Badge>
                        {m.source_refs[0]?.rel_path && (
                          <Citation>
                            {m.source_refs[0].rel_path}
                            {m.source_refs[0].line_start
                              ? `:${m.source_refs[0].line_start}-${m.source_refs[0].line_end}` : ''}
                          </Citation>
                        )}
                      </div>
                    </div>
                    <span className="mono text-[11px] tabular-nums" style={{ color: 'var(--muted)' }}>
                      {m.importance.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
      </Panel>

      {hasProjects && (
        <details className="rounded-md border" style={{ borderColor: 'var(--border)' }}>
          <summary className="cursor-pointer px-3 py-2 text-[12px] font-medium">
            Register another project
          </summary>
          <div className="px-3 pb-3">
                  <form
                    className="flex flex-col sm:flex-row gap-2"
                    onSubmit={(e) => { e.preventDefault(); register.mutate() }}
                  >
                    <input
                      value={name} onChange={(e) => setName(e.target.value)}
                      placeholder="Name" required
                      className="rounded-md border px-2 py-1.5 text-[13px] sm:w-44"
                      style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
                    />
                    <input
                      value={path} onChange={(e) => setPath(e.target.value)}
                      placeholder="/absolute/path/to/repo" required
                      className="mono flex-1 rounded-md border px-2 py-1.5 text-[13px]"
                      style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
                    />
                    <button
                      type="submit" disabled={register.isPending}
                      className="rounded-md border px-3 py-1.5 text-[12px] font-medium disabled:opacity-50"
                      style={{ borderColor: 'var(--border)' }}
                    >
                      {register.isPending ? 'Adding…' : 'Add project'}
                    </button>
                  </form>
                  {register.isError && <div className="mt-2"><ErrorNote error={register.error} /></div>}
          </div>
        </details>
      )}
    </div>
  )
}
