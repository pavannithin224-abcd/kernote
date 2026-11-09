import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Citation, Empty, ErrorNote, Panel, Stat } from '../components/ui'

export default function AgentIntegrations() {
  const { projectId } = useProject()
  const [task, setTask] = useState('')
  const [budget, setBudget] = useState(4000)
  const [copied, setCopied] = useState(false)

  const mcp = useQuery({
    queryKey: ['mcp', projectId],
    queryFn: () => api.mcpInfo(projectId!),
    enabled: !!projectId,
  })

  const bundle = useMutation({
    mutationFn: () => api.buildBundle(projectId!, task.trim() || null, budget),
  })

  if (!projectId) {
    return <Empty title="No project selected" hint="Register one on the Dashboard first." />
  }

  function copySnippet(text: string) {
    navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 2000)
      },
      () => setCopied(false),
    )
  }

  function download(markdown: string) {
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'kernote-context.md'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Agent Integrations</h1>
        <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
          Hand this project's reviewed memory to a coding agent — as a file, or over
          MCP. Both surfaces are read-only.
        </p>
      </header>

      {mcp.isError && <ErrorNote error={mcp.error} />}

      {mcp.data && (
        <Panel
          title="MCP server"
          right={
            <Badge tone={mcp.data.writable ? 'warn' : 'ok'}>
              {mcp.data.writable ? 'writable' : 'read-only'}
            </Badge>
          }
        >
          <p className="text-[12px] mb-2">{mcp.data.note}</p>

          <div className="space-y-1.5 mb-3">
            {mcp.data.tools.map((t) => (
              <div key={t.name} className="text-[12px]">
                <span className="mono" style={{ color: 'var(--accent)' }}>{t.name}</span>
                <span style={{ color: 'var(--muted)' }}> — {t.description}</span>
              </div>
            ))}
          </div>

          <div className="text-[11px] mb-1" style={{ color: 'var(--muted)' }}>
            Register it with Claude Code ({mcp.data.transport} transport)
          </div>
          <pre
            className="mono text-[11px] whitespace-pre-wrap rounded-md border p-2 overflow-auto"
            style={{ borderColor: 'var(--border)' }}
          >
            {mcp.data.claude_code_snippet}
          </pre>
          <button
            onClick={() => copySnippet(mcp.data!.claude_code_snippet)}
            className="mt-2 rounded-md border px-2.5 py-1 text-[12px]"
            style={{ borderColor: 'var(--border)' }}
          >
            {copied ? 'Copied' : 'Copy command'}
          </button>
        </Panel>
      )}

      <Panel title="Context bundle">
        <p className="text-[12px] mb-2" style={{ color: 'var(--muted)' }}>
          A Markdown file of approved memory, every claim cited. It states its token
          estimate and lists what it dropped — a silently truncated context is worse
          than a short one.
        </p>
        <form
          className="flex flex-col sm:flex-row gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            bundle.mutate()
          }}
        >
          <input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Task (optional) — ranks by relevance"
            className="flex-1 rounded-md border px-2 py-1.5 text-[13px]"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
          <input
            type="number"
            value={budget}
            min={200}
            max={32000}
            step={500}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="mono rounded-md border px-2 py-1.5 text-[13px] sm:w-28"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
          <button
            type="submit"
            disabled={bundle.isPending}
            className="rounded-md px-3 py-1.5 text-[12px] font-medium text-white disabled:opacity-50"
            style={{ background: 'var(--accent)' }}
          >
            {bundle.isPending ? 'Building…' : 'Build bundle'}
          </button>
        </form>
        {bundle.isError && <div className="mt-2"><ErrorNote error={bundle.error} /></div>}
      </Panel>

      {bundle.data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <Stat
              label="Tokens"
              value={`~${bundle.data.tokens_used}`}
              hint={`of ${bundle.data.token_budget} budget`}
            />
            <Stat label="Included" value={bundle.data.included} hint="memories" />
            <Stat
              label="Dropped"
              value={bundle.data.dropped.length}
              hint="over budget"
            />
          </div>

          {bundle.data.note && (
            <p className="text-[12px]" style={{ color: 'var(--warn)' }}>{bundle.data.note}</p>
          )}

          <Panel
            title="Bundle"
            right={
              <button
                onClick={() => download(bundle.data!.markdown)}
                className="rounded border px-2 py-0.5 text-[11px]"
                style={{ borderColor: 'var(--border)' }}
              >
                Download .md
              </button>
            }
          >
            <pre
              className="mono whitespace-pre-wrap text-[11px] max-h-96 overflow-auto"
              style={{ color: 'var(--text)' }}
            >
              {bundle.data.markdown}
            </pre>
          </Panel>

          {bundle.data.dropped.length > 0 && (
            <Panel title={`Did not fit (${bundle.data.dropped.length})`}>
              <ul className="space-y-1">
                {bundle.data.dropped.slice(0, 25).map((d) => (
                  <li key={d.citation + d.title} className="flex flex-wrap items-center gap-1.5 text-[12px]">
                    <Citation>{d.citation}</Citation>
                    <span className="truncate">{d.title}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
